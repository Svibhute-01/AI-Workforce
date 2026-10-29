"""Retry the model call when the network drops, instead of crashing the whole job.

A code-writing call can run for minutes, and long requests are the ones most often cut by a flaky
connection, a VPN/proxy, an antivirus or the server ("[WinError 10054] connection forcibly closed",
timeouts, 429 / 503 from a busy service). Those are temporary, so the same call is simply tried again.
Real mistakes (a wrong API key, a bad request) are NOT retried and fail at once with their own message.
"""

import os
import re
import time
from collections.abc import Callable

# Error class names (from httpx, httpcore, google, openai and others) that mean "try again".
TRANSIENT_NAMES = {
    "ReadError", "WriteError", "ConnectError", "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout",
    "TimeoutException", "RemoteProtocolError", "ProtocolError", "NetworkError", "TransportError",
    "APIConnectionError", "APITimeoutError", "RateLimitError", "InternalServerError",
    "ServerError", "ServiceUnavailable", "ResourceExhausted", "DeadlineExceeded", "TooManyRequests",
}
TRANSIENT_TEXT = re.compile(
    r"10054|forcibly closed|connection reset|connection aborted|server disconnected|remote end closed|"
    r"timed out|temporarily unavailable|overloaded|rate limit|resource_exhausted|\b(?:429|502|503|504)\b|"
    r"\bunavailable\b",
    re.IGNORECASE,
)
DEFAULT_DELAYS = (3, 8, 20)   # seconds to wait before the 2nd, 3rd, ... call


def attempts_from_env() -> int:
    """Total tries per model call (LLM_CALL_ATTEMPTS, default 3, between 1 and 6). 1 turns retrying off."""
    try:
        return max(1, min(6, int(os.getenv("LLM_CALL_ATTEMPTS", "3"))))
    except ValueError:
        return 3


def is_transient(error: BaseException) -> bool:
    """True when `error`, or anything it was raised from, looks like a temporary network or capacity problem."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (ConnectionError, TimeoutError)) or type(current).__name__ in TRANSIENT_NAMES:
            return True
        # Wording is only trusted on network-style errors. A ValueError family error (pydantic validation,
        # an output-parsing failure) quotes the model's own answer, which could contain any of these words.
        if not isinstance(current, ValueError) and TRANSIENT_TEXT.search(str(current)[:400]):
            return True
        current = current.__cause__ or current.__context__
    return False


def call_with_retries(
    call: Callable[[], object],
    attempts: int | None = None,
    delays: tuple[int, ...] = DEFAULT_DELAYS,
    on_retry: Callable[[int, int, BaseException, int], None] | None = None,
):
    """Run `call()`. A temporary failure is retried after a pause; anything else is raised straight away.

    `on_retry(failed_attempt, attempts, error, delay)` is told before each pause (used for the job log).
    """
    attempts = attempts or attempts_from_env()
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception as error:  # noqa: BLE001 - classified below; non-temporary errors are re-raised unchanged
            if not is_transient(error):
                raise
            if attempt >= attempts:
                if attempts == 1:
                    raise
                raise RuntimeError(
                    f"The model service could not be reached after {attempts} attempts "
                    f"({type(error).__name__}: {error}). Check the internet connection, VPN/proxy and "
                    "antivirus/firewall, then run the task again."
                ) from error
            delay = delays[min(attempt - 1, len(delays) - 1)]
            if on_retry:
                on_retry(attempt, attempts, error, delay)
            time.sleep(delay)
