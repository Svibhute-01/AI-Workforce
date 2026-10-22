from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..dependencies import get_current_user
from ..models import Project, User, UserSettings
from ..schemas_settings import (
    AISettingsResponse,
    IntegrationItem,
    NotificationPreferences,
    PasswordChange,
    PreferencesResponse,
    PreferencesUpdate,
    ProfileResponse,
    ProfileUpdate,
    SecurityResponse,
)
from ..security import hash_password, verify_password

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:  # SQLite returns naive UTC timestamps
        return value.replace(tzinfo=timezone.utc)
    return value


def _settings_row(db: Session, user: User) -> UserSettings | None:
    return db.get(UserSettings, user.id)


def _profile(db: Session, user: User) -> ProfileResponse:
    count = db.scalar(select(func.count()).select_from(Project).where(Project.owner_id == user.id)) or 0
    return ProfileResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=_aware(user.created_at),
        project_count=count,
    )


def _preferences(row: UserSettings | None) -> PreferencesResponse:
    if row is None:
        return PreferencesResponse()
    return PreferencesResponse(
        theme=row.theme or "system",
        notifications=NotificationPreferences(**(row.notifications or {})),
        updated_at=_aware(row.updated_at),
    )


# ---- profile --------------------------------------------------------------------


@router.get("/profile", response_model=ProfileResponse)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _profile(db, user)


@router.put("/profile", response_model=ProfileResponse)
def update_profile(payload: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.display_name = payload.display_name
    db.commit()
    db.refresh(user)
    return _profile(db, user)


# ---- password -------------------------------------------------------------------


@router.put("/password")
def change_password(payload: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different from the current one")

    user.password_hash = hash_password(payload.new_password)
    row = _settings_row(db, user)
    if row is None:
        row = UserSettings(user_id=user.id, theme="system", notifications={})
        db.add(row)
    row.password_changed_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Password updated"}


# ---- preferences ----------------------------------------------------------------


@router.get("/preferences", response_model=PreferencesResponse)
def get_preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _preferences(_settings_row(db, user))


@router.put("/preferences", response_model=PreferencesResponse)
def update_preferences(payload: PreferencesUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _settings_row(db, user)
    if row is None:
        row = UserSettings(user_id=user.id, theme="system", notifications={})
        db.add(row)
    if payload.theme is not None:
        row.theme = payload.theme
    if payload.notifications is not None:
        changes = payload.notifications.model_dump(exclude_none=True)
        row.notifications = {**(row.notifications or {}), **changes}  # reassign so the JSON change is persisted
    db.commit()
    db.refresh(row)
    return _preferences(row)


# ---- read-only information ------------------------------------------------------


@router.get("/ai", response_model=AISettingsResponse)
def get_ai_settings(user: User = Depends(get_current_user)):
    settings = get_settings()
    return AISettingsResponse(
        provider="Google Gemini",
        model=settings.gemini_model,
        embedding_model=settings.gemini_embedding_model,
        vector_store="ChromaDB",
        api_key_configured=bool(settings.gemini_api_key),
    )


@router.get("/security", response_model=SecurityResponse)
def get_security(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _settings_row(db, user)
    return SecurityResponse(
        auth_method="Email and password",
        password_storage="Hashed with bcrypt",
        session_duration_hours=get_settings().access_token_expire_minutes / 60,
        account_created=_aware(user.created_at),
        password_last_changed=_aware(row.password_changed_at) if row else None,
    )


@router.get("/integrations", response_model=list[IntegrationItem])
def get_integrations(user: User = Depends(get_current_user)):
    # No integration exists in the backend yet, so every one is reported as such.
    return [
        IntegrationItem(key="github", name="GitHub", description="Link code repositories to projects",
                        status="not_connected", available=False),
        IntegrationItem(key="jira", name="Jira", description="Sync issues and sprints",
                        status="not_connected", available=False),
        IntegrationItem(key="slack", name="Slack", description="Send notifications to a channel",
                        status="not_connected", available=False),
    ]
