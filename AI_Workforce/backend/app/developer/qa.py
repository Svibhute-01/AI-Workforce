"""What the QA agent is given, and what the Developer is told when QA finds defects."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ArchDesign, PMTask, Project
from .prompt import _design_section

FIX_LIMIT = 6000
EVIDENCE_CHARS = 300


def build_brief(db: Session, project: Project, task: PMTask) -> dict:
    """The task's acceptance criteria (numbered C1, C2, ...) and the design items traced to it."""
    criteria = [{"id": f"C{i}", "text": text} for i, text in enumerate(task.acceptance_criteria or [], start=1)]
    design = db.scalar(select(ArchDesign).where(ArchDesign.project_id == project.id))
    lines = [line for line in _design_section(design, task) if line.strip() and not line.startswith("Architecture to follow")]
    return {"task_id": task.task_id, "task_title": task.title, "criteria": criteria, "design_text": "\n".join(lines)}


def build_fix_text(report_rows: list[dict]) -> str:
    """The defects QA found, with the evidence, as instructions for the Developer."""
    blocks = []
    for row in report_rows:
        if row.get("verdict") != "FAIL":
            continue
        block = [f"- {row['id']} (acceptance criterion: {row['text']}) FAILED: {row['reason']}"]
        for scenario in row.get("scenarios", []):
            for step in scenario.get("steps", []):
                if step.get("failures"):
                    block.append(f"    {step['request']} answered {step.get('status')}: " + "; ".join(step["failures"]))
                    if step.get("excerpt"):
                        block.append(f"    response began: {step['excerpt'][:EVIDENCE_CHARS]}")
        blocks.append("\n".join(block))
    if not blocks:
        return ""
    text = (
        "\n\nQA TESTED THE RUNNING APP AND FOUND DEFECTS in your previous implementation of this task. "
        "Fix every one of them without breaking what already works, and keep the architecture. "
        "The acceptance criterion is the requirement; the evidence shows what the app really did:\n"
        + "\n".join(blocks)
    )
    return text[:FIX_LIMIT]
