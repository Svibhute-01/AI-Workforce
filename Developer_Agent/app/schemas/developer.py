from typing import Literal
from pydantic import BaseModel, Field


class FileChange(BaseModel):
    """One file the developer agent wants to create, modify or delete."""

    path: str = Field(
        description="Relative file path inside the project, e.g. 'app/routes/auth.py'"
    )
    action: Literal["create", "modify", "delete"] = Field(
        description=(
            "'create' for a new file, 'modify' for an existing one, "
            "'delete' to remove an obsolete file"
        )
    )
    content: str = Field(
        description="The complete final content of the file. Use an empty string for 'delete'."
    )
    explanation: str = Field(
        description="One or two sentences on what this file does or what changed"
    )


class DeveloperOutput(BaseModel):
    """Everything the developer agent produces for one task."""

    summary: str = Field(description="Short summary of what was implemented")
    changes: list[FileChange] = Field(description="All files to create, modify or delete")