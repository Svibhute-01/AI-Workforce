"""Request/response models for the Settings page. No model here ever carries a secret."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Theme = Literal["light", "dark", "system"]


class ProfileResponse(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    created_at: datetime | None = None
    project_count: int = 0


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("display_name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class NotificationPreferences(BaseModel):
    ai_task_completion: bool = True
    ai_agent_failure: bool = True
    project_updates: bool = True
    task_updates: bool = True


class NotificationPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai_task_completion: bool | None = None
    ai_agent_failure: bool | None = None
    project_updates: bool | None = None
    task_updates: bool | None = None


class PreferencesResponse(BaseModel):
    theme: Theme = "system"
    notifications: NotificationPreferences = Field(default_factory=NotificationPreferences)
    updated_at: datetime | None = None


class PreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: Theme | None = None
    notifications: NotificationPreferencesUpdate | None = None


class AISettingsResponse(BaseModel):
    provider: str
    model: str
    embedding_model: str
    vector_store: str
    api_key_configured: bool  # a yes/no only - the key itself is never returned


class SecurityResponse(BaseModel):
    auth_method: str
    password_storage: str
    session_duration_hours: float
    account_created: datetime | None = None
    password_last_changed: datetime | None = None


class IntegrationItem(BaseModel):
    key: str
    name: str
    description: str
    status: Literal["not_connected", "connected"]
    available: bool
