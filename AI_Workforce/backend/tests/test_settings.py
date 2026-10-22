import json

import pytest

from app.models import User, UserSettings
from app.security import verify_password

P, PW, PREF = "/api/settings/profile", "/api/settings/password", "/api/settings/preferences"
ALL = [P, PW, PREF, "/api/settings/ai", "/api/settings/security", "/api/settings/integrations"]


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.mark.parametrize("url", ALL)
def test_every_settings_endpoint_requires_authentication(client, url):
    assert client.get(url).status_code in (401, 405)
    assert client.put(url, json={}).status_code in (401, 405)


# ---- profile ------------------------------------------------------------------


def test_profile_shows_real_user_and_project_count(client, make_user, make_project):
    user = make_user("ada@example.com")
    make_project(user)
    make_project(user, name="Second")
    body = client.get(P, headers=user["headers"]).json()
    assert body["email"] == "ada@example.com" and body["display_name"] == "Test User"
    assert body["project_count"] == 2 and body["created_at"]
    assert "password" not in json.dumps(body).lower()


def test_profile_name_update_is_saved_to_the_database(client, db, make_user):
    user = make_user("ada@example.com")
    response = client.put(P, json={"display_name": "  Ada Lovelace  "}, headers=user["headers"])
    assert response.status_code == 200 and response.json()["display_name"] == "Ada Lovelace"
    db.expire_all()
    assert db.query(User).filter_by(email="ada@example.com").one().display_name == "Ada Lovelace"
    assert client.get("/api/auth/me", headers=user["headers"]).json()["display_name"] == "Ada Lovelace"


@pytest.mark.parametrize("body", [{"display_name": ""}, {"display_name": "   "}, {"display_name": "x" * 121}, {}])
def test_profile_rejects_invalid_names(client, make_user, body):
    assert client.put(P, json=body, headers=make_user()["headers"]).status_code == 422


def test_profile_cannot_change_email_or_other_fields(client, db, make_user):
    user = make_user("ada@example.com")
    response = client.put(P, json={"display_name": "Ada", "email": "evil@example.com"}, headers=user["headers"])
    assert response.status_code == 422
    assert db.query(User).filter_by(email="ada@example.com").count() == 1


def test_one_user_cannot_change_another_users_profile(client, make_user):
    a, b = make_user("a@example.com"), make_user("b@example.com")
    client.put(P, json={"display_name": "Changed A"}, headers=a["headers"])
    assert client.get(P, headers=b["headers"]).json()["display_name"] == "Test User"


# ---- password -----------------------------------------------------------------


def test_password_change_validates_current_and_hashes_the_new_one(client, db, make_user):
    user = make_user("ada@example.com")  # registered with password123
    ok = client.put(PW, json={"current_password": "password123", "new_password": "a-brand-new-pass"}, headers=user["headers"])
    assert ok.status_code == 200 and "password" not in ok.text.replace("Password updated", "").lower()

    assert login(client, "ada@example.com", "password123").status_code == 401  # old password no longer works
    assert login(client, "ada@example.com", "a-brand-new-pass").status_code == 200

    db.expire_all()
    stored = db.query(User).filter_by(email="ada@example.com").one().password_hash
    assert stored != "a-brand-new-pass" and stored.startswith("$2") and verify_password("a-brand-new-pass", stored)


def test_wrong_current_password_is_rejected_and_nothing_changes(client, make_user):
    user = make_user("ada@example.com")
    response = client.put(PW, json={"current_password": "not-it", "new_password": "a-brand-new-pass"}, headers=user["headers"])
    assert response.status_code == 400 and "incorrect" in response.json()["detail"].lower()
    assert login(client, "ada@example.com", "password123").status_code == 200


@pytest.mark.parametrize("new", ["short", "password123"])
def test_weak_or_unchanged_new_password_is_rejected(client, make_user, new):
    user = make_user()
    response = client.put(PW, json={"current_password": "password123", "new_password": new}, headers=user["headers"])
    assert response.status_code in (400, 422)


def test_password_change_records_when_it_happened(client, make_user):
    user = make_user()
    assert client.get("/api/settings/security", headers=user["headers"]).json()["password_last_changed"] is None
    client.put(PW, json={"current_password": "password123", "new_password": "a-brand-new-pass"}, headers=user["headers"])
    assert client.get("/api/settings/security", headers=user["headers"]).json()["password_last_changed"]


# ---- preferences --------------------------------------------------------------


def test_new_user_gets_defaults_without_a_row_being_created(client, db, make_user):
    user = make_user()
    body = client.get(PREF, headers=user["headers"]).json()
    assert body["theme"] == "system" and all(body["notifications"].values()) and len(body["notifications"]) == 4
    assert db.query(UserSettings).count() == 0


def test_preferences_persist_and_merge_partial_updates(client, db, make_user):
    user = make_user()
    client.put(PREF, json={"theme": "dark"}, headers=user["headers"])
    client.put(PREF, json={"notifications": {"ai_agent_failure": False}}, headers=user["headers"])
    response = client.put(PREF, json={"notifications": {"task_updates": False}}, headers=user["headers"])
    assert response.status_code == 200

    body = client.get(PREF, headers=user["headers"]).json()  # a fresh request reads from the database
    assert body["theme"] == "dark"
    assert body["notifications"] == {"ai_task_completion": True, "ai_agent_failure": False,
                                     "project_updates": True, "task_updates": False}
    assert db.query(UserSettings).count() == 1


@pytest.mark.parametrize("body", [{"theme": "purple"}, {"notifications": {"spam": True}}, {"notifications": {"task_updates": "maybe"}}, {"other": 1}])
def test_invalid_preferences_are_rejected(client, make_user, body):
    assert client.put(PREF, json=body, headers=make_user()["headers"]).status_code == 422


def test_preferences_are_private_to_each_user(client, make_user):
    a, b = make_user(), make_user()
    client.put(PREF, json={"theme": "dark", "notifications": {"project_updates": False}}, headers=a["headers"])
    other = client.get(PREF, headers=b["headers"]).json()
    assert other["theme"] == "system" and other["notifications"]["project_updates"] is True


# ---- AI / security / integrations: read-only, no secrets -----------------------


def test_ai_settings_reflect_configuration_without_exposing_the_key(client, make_user):
    body = client.get("/api/settings/ai", headers=make_user()["headers"]).json()
    assert body["provider"] == "Google Gemini" and body["model"] and body["embedding_model"] == "gemini-embedding-001"
    assert body["api_key_configured"] is True  # conftest sets a key
    assert "test-key" not in json.dumps(body)


def test_no_endpoint_leaks_secrets_or_hashes(client, db, make_user):
    user = make_user("ada@example.com")
    client.put(PREF, json={"theme": "dark"}, headers=user["headers"])
    client.put(PW, json={"current_password": "password123", "new_password": "a-brand-new-pass"}, headers=user["headers"])
    stored_hash = db.query(User).filter_by(email="ada@example.com").one().password_hash
    blob = " ".join(client.get(url, headers=user["headers"]).text for url in
                    (P, PREF, "/api/settings/ai", "/api/settings/security", "/api/settings/integrations"))
    for secret in ("test-key", "test-secret", stored_hash, "a-brand-new-pass", "password_hash", "jwt", "api_key\":"):
        assert secret not in blob


def test_security_info_has_no_credentials(client, make_user):
    body = client.get("/api/settings/security", headers=make_user()["headers"]).json()
    assert body["session_duration_hours"] == 24 and body["password_storage"] == "Hashed with bcrypt"


def test_integrations_are_honestly_reported_as_not_connected(client, make_user):
    items = client.get("/api/settings/integrations", headers=make_user()["headers"]).json()
    assert [i["key"] for i in items] == ["github", "jira", "slack"]
    assert all(i["status"] == "not_connected" and i["available"] is False for i in items)
