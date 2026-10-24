"""HTTP client for the Developer Agent service."""

import httpx

from ..config import Settings, get_settings


class DeveloperServiceError(RuntimeError):
    """The Developer Agent service failed or is unreachable."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class DeveloperAgentClient:
    def __init__(self, settings: Settings | None = None, transport: httpx.BaseTransport | None = None):
        settings = settings or get_settings()
        headers = {"X-Service-Key": settings.developer_agent_key} if settings.developer_agent_key else {}
        self._http = httpx.Client(
            base_url=settings.developer_agent_url.rstrip("/"),
            headers=headers,
            timeout=settings.developer_agent_timeout_seconds,
            transport=transport,
        )
        self._command_timeout = settings.developer_agent_command_timeout_seconds

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise DeveloperServiceError(503, "The Developer Agent service is not reachable.") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            # 401 means our own configuration is wrong: do not leak it to the browser as an auth error
            status = 503 if response.status_code in (401, 502, 503, 504) else response.status_code
            raise DeveloperServiceError(status, str(detail))
        return response.json()

    def list_files(self, workspace: str) -> list[str]:
        return self._request("GET", f"/projects/{workspace}/files")["files"]

    def read_file(self, workspace: str, path: str) -> str:
        return self._request("GET", f"/projects/{workspace}/file", params={"path": path})["content"]

    def start_task(self, workspace: str, task: str, tech_stack: str, stack: str | None = None) -> dict:
        body = {"task": task, "tech_stack": tech_stack, "stack": stack}
        return self._request("POST", f"/projects/{workspace}/tasks", json=body)

    def get_stack(self, workspace: str) -> dict:
        return self._request("GET", f"/projects/{workspace}/stack")

    def get_app(self, workspace: str) -> dict:
        return self._request("GET", f"/projects/{workspace}/app")

    def start_app(self, workspace: str) -> dict:
        return self._request("POST", f"/projects/{workspace}/app/start", timeout=90)

    def stop_app(self, workspace: str) -> dict:
        return self._request("POST", f"/projects/{workspace}/app/stop")

    def get_job(self, workspace: str, job_id: str) -> dict:
        return self._request("GET", f"/projects/{workspace}/jobs/{job_id}")

    def run_command(self, workspace: str, command: str) -> dict:
        return self._request("POST", f"/projects/{workspace}/run", json={"command": command}, timeout=self._command_timeout)


def get_developer_client() -> DeveloperAgentClient:
    """FastAPI dependency so tests can substitute a fake service."""
    return DeveloperAgentClient()
