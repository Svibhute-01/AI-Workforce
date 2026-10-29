from typing import TypedDict, Optional
from app.schemas.developer import DeveloperOutput


class DeveloperState(TypedDict):
    # inputs
    project_id: str
    task: str
    tech_stack: str
    architecture: list   # the System Architect's technologies: [{role, technology, component}]
    deviations: list     # parts of the architecture this agent could not build exactly
    stack: str          # stack profile id, e.g. "python-fastapi" (see app/stacks.py)
    

    # result (None until the generate node runs)
    output: Optional[DeveloperOutput]

    # loop control
    validation_errors: list[str]
    retries: int
     # final result label: "running", "success" or "failed"
    status: str

    # seconds spent per step so far (llm, install, test, ...); see app/timing.py
    timings: dict