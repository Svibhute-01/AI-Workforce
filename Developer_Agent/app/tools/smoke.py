"""After the tests pass, start the app and check that it answers on "/"."""

import socket
import time
import urllib.error
import urllib.request


def find_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def probe(url: str, timeout: float = 3) -> int | None:
    """HTTP status of a GET, or None when nothing is listening yet."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as exc:   # the server answered, with an error status
        return exc.code
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        return None


def wait_until_up(handle, port: int, stack, seconds: float = 30) -> str | None:
    """None when the app answers acceptably, otherwise a message that explains why not."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not handle.alive():
            return f"The app exited right after it started:\n{handle.log_tail()}"
        status = probe(f"http://127.0.0.1:{port}/")
        if status is not None:
            if stack.probe_ok(status):
                return None
            return f"GET / answered {status}, which is not acceptable for this stack:\n{handle.log_tail()}"
        time.sleep(0.5)
    return f"The app did not answer on port {port} within {int(seconds)} seconds:\n{handle.log_tail()}"


def smoke_check(runner, stack) -> str | None:
    if not stack.start:
        return None
    port = find_free_port()
    try:
        handle = runner.start_app(port)
    except (OSError, RuntimeError) as exc:
        return f"Smoke check failed. The app could not be started: {exc}"
    try:
        problem = wait_until_up(handle, port, stack)
    finally:
        handle.stop()
    return f"Smoke check failed. {problem}" if problem else None
