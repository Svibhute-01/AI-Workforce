"""Runs a stack's allowlisted commands inside one project folder.

LocalRunner runs them on this machine. DockerRunner runs each one in a throw-away container with only
the project folder mounted. Both take their commands from the stack profile, resolve its tokens, and
return the same CommandResult, so nothing else in the service cares which one is used.
"""

import os
import shutil
import signal
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.config import DOCKER_CPUS, DOCKER_MEMORY, RUNNER_MODE

# Per-command time limits in seconds. Installing is the slow one (many packages, cold cache).
TIMEOUTS = {"install": 600, "check_imports": 60, "test": 300}
SETUP_TIMEOUT = 120
DEFAULT_TIMEOUT = 180

# Child processes get only these variables. The service's own environment holds the Gemini key and the
# service key, and AI-written code (and its tests) must never be able to read them.
SAFE_ENV_NAMES = (
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP", "TMPDIR",
    "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
    "LANG", "LC_ALL", "TZ", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS", "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_CERT",
    "NPM_CONFIG_REGISTRY",
)


def safe_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {name: os.environ[name] for name in SAFE_ENV_NAMES if name in os.environ}
    env.setdefault("PYTHONUTF8", "1")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra or {})
    return env


@dataclass
class CommandResult:
    name: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def summary(self, max_chars: int = 3000) -> str:
        """Short text to show a human or feed back to Gemini."""
        text = (self.stdout + "\n" + self.stderr).strip()
        return text[-max_chars:]  # keep the END, where errors usually are


def _text(value) -> str:
    """subprocess hands back bytes (or None) in TimeoutExpired even when text=True was used."""
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


class AppHandle:
    """A started app: can be asked whether it is alive, for its log, and be stopped."""

    def alive(self) -> bool: raise NotImplementedError
    def log_tail(self, max_chars: int = 3000) -> str: raise NotImplementedError
    def stop(self) -> None: raise NotImplementedError


class LocalAppHandle(AppHandle):
    def __init__(self, process: subprocess.Popen, log_path: Path):
        self.process, self.log_path = process, log_path

    def alive(self) -> bool:
        return self.process.poll() is None

    def log_tail(self, max_chars: int = 3000) -> str:
        try:
            return self.log_path.read_text(encoding="utf-8", errors="replace")[-max_chars:]
        except OSError:
            return ""

    def stop(self) -> None:
        if self.process.poll() is not None:
            return
        try:
            if sys.platform == "win32":  # kill the whole process tree (npm/uvicorn start children)
                subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"], capture_output=True)
            else:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            self.process.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            self.process.kill()


class DockerAppHandle(AppHandle):
    def __init__(self, name: str):
        self.name = name

    def alive(self) -> bool:
        result = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", self.name], capture_output=True, text=True)
        return result.returncode == 0 and result.stdout.strip() == "true"

    def log_tail(self, max_chars: int = 3000) -> str:
        result = subprocess.run(["docker", "logs", "--tail", "200", self.name], capture_output=True, text=True)
        return (result.stdout + result.stderr)[-max_chars:]

    def stop(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)


class BaseRunner:
    def __init__(self, root: Path, stack=None):
        from app.stacks import get_stack
        self.root = Path(root)
        self.stack = stack or get_stack(None)

    # --- pieces the two runners fill in differently -------------------------------------------
    def tokens(self, port: int | None = None) -> dict[str, str]:
        raise NotImplementedError

    def _execute(self, name: str, command: list[str], timeout: int) -> CommandResult:
        raise NotImplementedError

    def start_app(self, port: int, log_path: Path | None = None, env: dict[str, str] | None = None) -> AppHandle:
        raise NotImplementedError

    # --- shared ----------------------------------------------------------------------------------
    def _fill(self, template: list[str], port: int | None = None) -> list[str]:
        tokens = self.tokens(port)
        return [part.format(**tokens) if "{" in part else part for part in template]

    def _commands(self) -> dict[str, list[str]]:
        """The allowlist: name -> real command."""
        return {name: self._fill(template) for name, template in self.stack.commands.items()}

    @property
    def venv_dir(self) -> Path:
        return self.root / ".venv"

    def env_ready(self) -> bool:
        return not self.stack.needs_env or (self.root / self.stack.needs_env).exists()

    def setup(self) -> CommandResult | None:
        """Create the project's own environment once (a virtual environment for Python)."""
        if not self.stack.setup or self.env_ready():
            return None
        return self._execute("setup", self._fill(self.stack.setup), SETUP_TIMEOUT)

    def run(self, name: str, timeout: int | None = None) -> CommandResult:
        if name == "create_venv" and self.stack.setup:   # name kept for older callers
            return self._execute(name, self._fill(self.stack.setup), SETUP_TIMEOUT)
        commands = self._commands()
        if name not in commands:
            raise ValueError(f"Command not allowed: {name!r}")
        return self._execute(name, commands[name], timeout or TIMEOUTS.get(name, DEFAULT_TIMEOUT))


class LocalRunner(BaseRunner):
    """Runs commands on this machine, with a scrubbed environment."""

    def _venv_python(self) -> str:
        # Windows uses Scripts\python.exe, Mac/Linux use bin/python
        return str(self.venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python"))

    def tokens(self, port: int | None = None) -> dict[str, str]:
        return {
            "py": self._venv_python(),
            "host_python": sys.executable,
            "node": shutil.which("node") or "node",
            "npm": shutil.which("npm") or "npm",   # resolves npm.cmd on Windows
            "host": "127.0.0.1",
            "port": str(port or ""),
        }

    def _execute(self, name: str, command: list[str], timeout: int) -> CommandResult:
        try:
            result = subprocess.run(
                command, cwd=self.root, env=safe_env(self.stack.check_env), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout,
            )
            return CommandResult(name, result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired as exc:
            # Keep what the command printed so far: it usually shows what was taking so long.
            return CommandResult(name, -1, _text(exc.stdout), f"{_text(exc.stderr)}\nTimed out after {timeout}s")
        except FileNotFoundError as exc:
            return CommandResult(name, -1, "", f"Executable not found: {exc}")

    def start_app(self, port: int, log_path: Path | None = None, env: dict[str, str] | None = None) -> AppHandle:
        command = self._fill(self.stack.start, port)
        log_path = log_path or (self.root.parent / f".{self.root.name}.app.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = open(log_path, "wb")
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32" else {"start_new_session": True}
        process = subprocess.Popen(
            command, cwd=self.root, env=safe_env({**self.stack.check_env, **(env or {}), "PORT": str(port), "HOST": "127.0.0.1"}),
            stdout=log, stderr=subprocess.STDOUT, **options,
        )
        log.close()
        return LocalAppHandle(process, log_path)


class DockerRunner(BaseRunner):
    """Runs each command in a throw-away container. Needs Docker Desktop (or an engine) to be running."""

    def tokens(self, port: int | None = None) -> dict[str, str]:
        return {"py": ".venv/bin/python", "host_python": "python", "node": "node", "npm": "npm",
                "host": "0.0.0.0", "port": str(port or "")}   # 0.0.0.0 inside; only published on 127.0.0.1

    def _base_args(self, name: str, network: bool, extra_env: dict[str, str] | None = None) -> list[str]:
        args = ["docker", "run", "--name", name, "-v", f"{self.root}:/workspace", "-w", "/workspace",
                "--memory", DOCKER_MEMORY, "--cpus", DOCKER_CPUS, "--pids-limit", "512",
                "-e", "HOME=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONUTF8=1"]
        if hasattr(os, "getuid"):   # keep files in the project folder owned by the current user on Linux/macOS
            args += ["--user", f"{os.getuid()}:{os.getgid()}"]
        if not network:
            args += ["--network", "none"]
        for key, value in (extra_env or {}).items():
            args += ["-e", f"{key}={value}"]
        return args

    def docker_args(self, name: str, command: list[str], *, network: bool, detach: bool = False,
                    port: int | None = None, env: dict[str, str] | None = None) -> list[str]:
        extra = {**self.stack.check_env, **(env or {}), **({"PORT": str(port), "HOST": "0.0.0.0"} if port else {})}
        args = self._base_args(name, network, extra)
        args.insert(2, "-d" if detach else "--rm")
        if port:
            args += ["-p", f"127.0.0.1:{port}:{port}"]
        return args + [self.stack.image] + command

    def _execute(self, name: str, command: list[str], timeout: int) -> CommandResult:
        container = f"devagent-{self.root.name}-{uuid.uuid4().hex[:8]}"
        # Installing needs the network. Everything else runs offline, which also enforces
        # the rule that tests must not need the network.
        args = self.docker_args(container, command, network=name in ("install", "setup", "create_venv"))
        try:
            result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
            return CommandResult(name, result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired as exc:
            subprocess.run(["docker", "rm", "-f", container], capture_output=True)   # the CLI exiting does not stop it
            return CommandResult(name, -1, _text(exc.stdout), f"{_text(exc.stderr)}\nTimed out after {timeout}s")
        except FileNotFoundError:
            return CommandResult(name, -1, "", "Docker is not installed or not on PATH. Start Docker Desktop, or set RUNNER_MODE=local.")

    def start_app(self, port: int, log_path: Path | None = None, env: dict[str, str] | None = None) -> AppHandle:
        container = f"devagent-app-{self.root.name}-{uuid.uuid4().hex[:8]}"
        # The container needs no outbound network to serve the app.
        args = self.docker_args(container, self._fill(self.stack.start, port), network=False, detach=True, port=port, env=env)
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Could not start the container: {(result.stderr or result.stdout).strip()}")
        return DockerAppHandle(container)


def make_runner(root: Path, stack=None) -> BaseRunner:
    return DockerRunner(root, stack) if RUNNER_MODE == "docker" else LocalRunner(root, stack)
