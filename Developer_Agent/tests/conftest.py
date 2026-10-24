"""Test setup: point the service at throw-away folders BEFORE the app is imported."""

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="developer-agent-tests-")
os.environ["GOOGLE_API_KEY"] = "test-key"          # config refuses to import without one
os.environ["WORKSPACES_DIR"] = f"{_TMP}/workspaces"
os.environ["JOBS_DIR"] = f"{_TMP}/jobs"
os.environ["DEVELOPER_SERVICE_KEY"] = "secret-key"
os.environ["SMOKE_CHECK"] = "false"                # unit tests use fake projects that cannot be served
os.environ["APPS_DIR"] = f"{_TMP}/apps"
os.environ["PROJECTS_DIR"] = f"{_TMP}/projects"
