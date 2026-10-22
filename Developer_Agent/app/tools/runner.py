import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


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


# Seconds each command may run. Installing is the slow one (many packages, cold cache).
TIMEOUTS = {"create_venv": 120, "install": 600, "check_imports": 60, "test": 300}
DEFAULT_TIMEOUT = 180


def _text(value) -> str:
    """subprocess hands back bytes (or None) in TimeoutExpired even when text=True was used."""
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


class LocalRunner:
    """Runs allowlisted commands inside one workspace folder."""

    def __init__(self, root: Path):
        self.root = root
        self.venv_dir = root / ".venv"

    def _venv_python(self) -> str:
        # Windows uses Scripts\python.exe, Mac/Linux use bin/python
        if sys.platform == "win32":
            return str(self.venv_dir / "Scripts" / "python.exe")
        return str(self.venv_dir / "bin" / "python")

    def _commands(self) -> dict[str, list[str]]:
        """The allowlist: name -> real command."""
        py = self._venv_python()
        return {
            "create_venv": [sys.executable, "-m", "venv", str(self.venv_dir)],
            # --prefer-binary avoids compiling packages from source, which is slow and often fails
            "install": [py, "-m", "pip", "install", "--prefer-binary", "--disable-pip-version-check",
                        "--no-input", "-r", "requirements.txt"],
            "check_imports": [py, "-c", "import app.main"],
            "test": [py, "-m", "pytest", "-x", "-q"],
        }

    def run(self, name: str, timeout: int | None = None) -> CommandResult:
        commands = self._commands()
        if name not in commands:
            raise ValueError(f"Command not allowed: {name!r}")
        timeout = timeout or TIMEOUTS.get(name, DEFAULT_TIMEOUT)

        try:
            result = subprocess.run(
                commands[name],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return CommandResult(name, result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired as exc:
            # Keep what the command printed so far: it usually shows what was taking so long.
            return CommandResult(name, -1, _text(exc.stdout), f"{_text(exc.stderr)}\nTimed out after {timeout}s")
        except FileNotFoundError as e:
            return CommandResult(name, -1, "", f"Executable not found: {e}")