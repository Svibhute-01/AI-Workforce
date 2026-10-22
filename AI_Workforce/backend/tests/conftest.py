"""Shared fixtures for API-level tests.

SAFETY: the environment is pointed at a throw-away SQLite file *before* the app is
imported, and a fixture refuses to run if the engine is anything but SQLite. Tests
must never drop or create tables on a real PostgreSQL database.
"""

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="ai-workforce-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["CHROMA_PERSIST_DIRECTORY"] = f"{_TMP}/chroma"
os.environ["UPLOAD_DIRECTORY"] = f"{_TMP}/uploads"

import itertools  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api.project_manager import get_llm_provider  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.llm.base import LLMProvider  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    AcceptanceCriteria,
    AgentRun,
    Ambiguity,
    Constraint,
    Dependency,
    NonFunctionalRequirement,
    Requirement,
    UserStory,
)

SRC = [{"document": "SRS.pdf", "page": 1, "source": "SRS.pdf page 1"}]
SRC2 = [{"document": "SRS.pdf", "page": 2, "source": "SRS.pdf page 2"}]


class ScriptedProvider(LLMProvider):
    """Deterministic stand-in for the LLM.

    Each response is a ``ProjectPlan``, an ``Exception`` to raise, or a callable
    receiving the requirements payload (so ids always match the seeded project).
    The last response repeats once the list is exhausted.
    """

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def embed_texts(self, texts):
        raise NotImplementedError

    def generate_analysis(self, *args, **kwargs):
        raise NotImplementedError

    def answer_question(self, *args, **kwargs):
        raise NotImplementedError

    def generate_project_plan(self, project_name, project_description, requirements, project_info, feedback=None):
        self.calls.append(
            {"requirements": requirements, "project_info": project_info, "feedback": feedback, "name": project_name}
        )
        item = self.responses[min(len(self.calls), len(self.responses)) - 1]
        if isinstance(item, Exception):
            raise item
        return item(requirements) if callable(item) else item


@pytest.fixture(autouse=True)
def fresh_database():
    assert str(engine.url).startswith("sqlite"), "Refusing to run tests against a non-SQLite database"
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


_counter = itertools.count(1)


@pytest.fixture
def make_user(client):
    def _make(email: str | None = None) -> dict:
        email = email or f"user{next(_counter)}@example.com"
        response = client.post(
            "/api/auth/register", json={"email": email, "password": "password123", "display_name": "Test User"}
        )
        assert response.status_code == 201, response.text
        return {"headers": {"Authorization": f"Bearer {response.json()['access_token']}"}, "email": email}

    return _make


@pytest.fixture
def make_project(client):
    def _make(user: dict, name: str = "Customer Registration & Account Verification", **extra) -> int:
        response = client.post("/api/projects", json={"name": name, **extra}, headers=user["headers"])
        assert response.status_code == 201, response.text
        return response.json()["id"]

    return _make


@pytest.fixture
def use_provider():
    def _use(provider: ScriptedProvider) -> ScriptedProvider:
        app.dependency_overrides[get_llm_provider] = lambda: provider
        return provider

    return _use


@pytest.fixture
def seed_requirements(db):
    """Store Requirements Analyst output for the Customer Registration SRS.

    Mirrors what the analyst extracts from the real test SRS (7 functional
    requirements, 3 non-functional, 3 stories, 7 acceptance criteria, ...).
    Returns a lookup of the ids the Project Manager will see (e.g. "REQ-3").
    """

    def _seed(project_id: int) -> dict:
        run = AgentRun(
            project_id=project_id,
            agent_name="Requirements Analyst AI",
            status="COMPLETED",
            output_summary={
                "project_summary": {
                    "summary": "Customers register with email and password and receive a confirmation email.",
                    "scope": "Registration, validation, duplicate handling, password handling, confirmation email.",
                    "actors": ["Customer"],
                }
            },
        )
        db.add(run)
        db.flush()

        ids: dict[str, dict] = {"REQ": {}, "NFR": {}, "US": {}, "AC": [], "AMB": [], "CON": [], "DEP": []}

        def add(model, **fields):
            row = model(project_id=project_id, **fields)
            db.add(row)
            db.flush()
            return row

        requirements = [
            ("Customer Registration", "The system shall allow a customer to create an account using an email address and password.", "HIGH"),
            ("Email Validation", "The system shall validate that the email address supplied during registration is in a valid email format.", "MEDIUM"),
            ("Password Requirement", "The system shall require a password during customer registration.", "MEDIUM"),
            ("Duplicate Email Handling", "The system shall reject registration when the supplied email address is already associated with an existing account.", "HIGH"),
            ("Successful Registration", "When valid registration data is supplied and the email is not already registered, the system shall create the customer account.", "HIGH"),
            ("Confirmation Email", "After successful account creation, the system shall send a confirmation email to the registered email address.", "MEDIUM"),
            ("Registration Response", "The system shall provide a registration result indicating whether account creation succeeded or failed.", "LOW"),
        ]
        for title, description, priority in requirements:
            row = add(Requirement, title=title, description=description, priority=priority,
                      priority_basis="EXPLICIT", source_references=SRC)
            ids["REQ"][title] = f"REQ-{row.id}"
        req_row = {t: int(v.split("-")[1]) for t, v in ids["REQ"].items()}

        for category, description in [
            ("Performance", "The registration operation shall complete within two seconds under normal operating conditions."),
            ("Security", "Customer passwords shall not be stored as plaintext."),
            ("Reliability", "A failed confirmation-email operation shall not silently report successful email delivery."),
        ]:
            row = add(NonFunctionalRequirement, category=category, description=description,
                      priority="HIGH", source_references=SRC2)
            ids["NFR"][category] = f"NFR-{row.id}"

        stories = [
            ("Register with email and password", "As a customer, I want to register with my email and password so that I can create an account.", "Customer Registration"),
            ("Receive confirmation email", "As a customer, I want to receive a confirmation email after registration so that I know my registration was processed.", "Confirmation Email"),
            ("Reject duplicate registration", "As a customer, I want duplicate registration attempts to be rejected so that an email cannot be registered multiple times.", "Duplicate Email Handling"),
        ]
        story_row = {}
        for title, story, requirement in stories:
            row = add(UserStory, title=title, story=story, priority="HIGH",
                      requirement_id=req_row[requirement], source_references=SRC)
            ids["US"][title] = f"US-{row.id}"
            story_row[title] = row.id

        criteria = [
            ("Register with email and password", "A customer can submit an email address and password and create an account when both inputs are valid."),
            ("Reject duplicate registration", "Registration is rejected when the email address is already associated with an account."),
            ("Register with email and password", "Registration is rejected when the supplied email address is not in a valid email format."),
            ("Register with email and password", "A successful registration creates a customer account."),
            ("Receive confirmation email", "A confirmation email is sent after successful account creation."),
            ("Register with email and password", "The registration operation completes within two seconds under normal operating conditions."),
            ("Register with email and password", "Passwords are not stored as plaintext."),
        ]
        for story_title, description in criteria:
            row = add(AcceptanceCriteria, user_story_id=story_row[story_title], description=description,
                      source_references=SRC2)
            ids["AC"].append(f"AC-{row.id}")

        for description in (
            "FR-004 depends on the system being able to identify existing customer email addresses.",
            "FR-006 depends on successful account creation (FR-005).",
            "FR-006 requires an email-delivery capability.",
        ):
            row = add(Dependency, description=description, source_references=SRC2)
            ids["DEP"].append(f"DEP-{row.id}")

        for description in (
            "The registration flow must use email and password as specified in this document.",
            "The two-second performance target applies under normal operating conditions.",
        ):
            row = add(Constraint, description=description, source_references=SRC2)
            ids["CON"].append(f"CON-{row.id}")

        for description in (
            "The exact password complexity policy is not specified.",
            "The confirmation-email template and sender address are not specified.",
            "The confirmation-email retry policy is not specified.",
            "The exact definition of 'normal operating conditions' for the two-second target is not specified.",
        ):
            row = add(Ambiguity, description=description, impact="MEDIUM", source_references=SRC2)
            ids["AMB"].append(f"AMB-{row.id}")

        db.commit()
        ids["run_id"] = run.id
        return ids

    return _seed
