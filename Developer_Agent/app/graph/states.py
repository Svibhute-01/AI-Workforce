from typing import TypedDict, Optional
from app.schemas.developer import DeveloperOutput


class DeveloperState(TypedDict):
    # inputs
    project_id: str
    task: str
    tech_stack: str
    stack: str          # stack profile id, e.g. "python-fastapi" (see app/stacks.py)
    

    # result (None until the generate node runs)
    output: Optional[DeveloperOutput]

    # loop control
    validation_errors: list[str]
    retries: int
     # final result label: "running", "success" or "failed"
    status: str