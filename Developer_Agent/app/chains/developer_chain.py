from app.llm import get_llm
from app.prompts.developer import DEVELOPER_PROMPT
from app.schemas.developer import DeveloperOutput


def build_developer_chain():
    llm = get_llm(temperature=0.2)
    structured_llm = llm.with_structured_output(
        DeveloperOutput,
        method="json_schema",
    )
    return DEVELOPER_PROMPT | structured_llm