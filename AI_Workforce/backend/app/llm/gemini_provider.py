import json
import logging
import time

from pydantic import ValidationError

from ..config import Settings
from ..schemas import RequirementsAnalysis
from ..schemas_architect import HighLevelDesign, LowLevelDesign
from ..schemas_pm import ProjectPlan
from .architect_prompts import hld_prompt, lld_prompt
from .base import LLMProvider

logger = logging.getLogger(__name__)


class ProviderConfigurationError(RuntimeError):
    """Raised when the configured provider cannot be used."""


class GeminiProvider(LLMProvider):
    def __init__(self, settings: Settings):
        if not settings.gemini_api_key:
            raise ProviderConfigurationError(
                "GEMINI_API_KEY is not configured. Add it to Replit Secrets before processing documents or analysis."
            )

        from google import genai

        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model
        self._embedding_model = settings.gemini_embedding_model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        for attempt in range(2):
            try:
                response = self._client.models.embed_content(
                    model=self._embedding_model,
                    contents=texts,
                )
                return [list(embedding.values) for embedding in response.embeddings]

            except Exception as exc:
                if attempt == 0 and _is_retryable(exc):
                    time.sleep(1.5)
                    continue

                logger.exception("Gemini embedding request failed")
                raise ProviderConfigurationError(
                    f"Embedding provider failed: {exc}"
                ) from exc

    def generate_analysis(
        self,
        project_name: str,
        project_description: str,
        contexts: list[dict],
    ) -> RequirementsAnalysis:

        context_text = _format_contexts(contexts)

        prompt = f"""
You are the Requirements Analyst for the project "{project_name}".

Project description:
{project_description or "Not provided"}

Analyze the retrieved SRS excerpts below.

Transform explicit customer requirements into structured software-analysis
artifacts.

Do not invent:
- features
- rules
- actors
- priorities
- non-functional requirements
- constraints
- risks

Label inferred priorities as INFERRED.

Use ambiguities for missing information.

Every source reference must exactly match a document/page/source in the
supplied excerpts.

Use empty lists when the SRS does not support an artifact.

Generate user stories and acceptance criteria only from supported requirements.

For each supported user story, create at least one concrete acceptance
criterion when the SRS states observable behavior.

Do not leave acceptance_criteria empty when the supplied requirements support one.

Return JSON matching the RequirementsAnalysis schema exactly.

RETRIEVED SRS EXCERPTS:

{context_text}
"""

        for attempt in range(2):
            try:
                from google.genai import types

                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=_gemini_response_schema(),
                        temperature=0.1,
                        max_output_tokens=16000,
                    ),
                )

                parsed = getattr(response, "parsed", None)

                if parsed is None:
                    parsed = json.loads(response.text)

                return RequirementsAnalysis.model_validate(parsed)

            except Exception as exc:
                if attempt == 0 and (
                    _is_retryable(exc)
                    or isinstance(exc, (json.JSONDecodeError, ValidationError))
                ):
                    time.sleep(1.5)
                    continue

                logger.exception("Gemini structured analysis failed")

                raise ProviderConfigurationError(
                    f"Requirements analysis failed: {exc}"
                ) from exc

    def generate_project_plan(
        self,
        project_name: str,
        project_description: str,
        requirements: dict,
        project_info: dict,
        feedback: list[str] | None = None,
    ) -> ProjectPlan:

        base_prompt = _project_plan_prompt(
            project_name,
            project_description,
            requirements,
            project_info,
        )

        problems = list(feedback or [])

        # Three total attempts:
        # attempt 1 = normal generation
        # attempt 2 = corrected generation
        # attempt 3 = final corrected generation
        retry_delays = [2, 5]

        for attempt in range(3):

            prompt = base_prompt

            if problems:

                allowed_ids = _extract_allowed_ids(requirements)

                prompt += f"""

YOUR PREVIOUS PROJECT PLAN WAS REJECTED.

Fix ALL validation problems listed below.

VALIDATION ERRORS:
- {"".join(f"{problem}\\n- " for problem in problems[:40])}

IMPORTANT:
Do NOT simply regenerate the same plan.

You MUST correct every invalid reference.

The only valid IDs available to you are the IDs listed below.

VALID REQUIREMENT IDs:
{", ".join(allowed_ids["requirements"]) or "NONE"}

VALID USER STORY IDs:
{", ".join(allowed_ids["stories"]) or "NONE"}

VALID ACCEPTANCE CRITERIA IDs:
{", ".join(allowed_ids["acceptance_criteria"]) or "NONE"}

VALID NON-FUNCTIONAL REQUIREMENT IDs:
{", ".join(allowed_ids["non_functional"]) or "NONE"}

VALID CONSTRAINT IDs:
{", ".join(allowed_ids["constraints"]) or "NONE"}

VALID DEPENDENCY IDs:
{", ".join(allowed_ids["dependencies"]) or "NONE"}

VALID AMBIGUITY IDs:
{", ".join(allowed_ids["ambiguities"]) or "NONE"}

VALID RISK IDs:
{", ".join(allowed_ids["risks"]) or "NONE"}

STRICT CORRECTION RULES:

1. NEVER invent an ID.
2. NEVER create IDs that are not in the lists above.
3. epic.related_requirement_ids MUST contain ONLY valid REQ-* IDs.
4. task.related_requirement_id MUST contain ONLY valid REQ-* IDs or null.
5. task.related_story_id MUST contain ONLY valid US-* IDs or null.
6. NFR-* must NOT be used as related_requirement_id.
7. CON-* must NOT be used as related_requirement_id.
8. US-* must NOT be used as related_requirement_id.
9. If there is no valid reference, use null.
10. Return the COMPLETE corrected project plan.

Validate every ID mentally before returning the JSON.
"""

            try:
                from google.genai import types

                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=_gemini_response_schema(ProjectPlan),
                        temperature=0.1 if problems else 0.2,
                        max_output_tokens=32000,
                    ),
                )

                parsed = getattr(response, "parsed", None)

                if parsed is None:
                    parsed = json.loads(response.text)

                if isinstance(parsed, ProjectPlan):
                    return parsed

                return ProjectPlan.model_validate(parsed)

            except Exception as exc:

                is_validation_error = isinstance(
                    exc,
                    (json.JSONDecodeError, ValidationError),
                )

                is_retryable_error = _is_retryable(exc)

                if attempt < 2 and (
                    is_retryable_error or is_validation_error
                ):

                    if is_validation_error:
                        problems = [
                            *problems,
                            (
                                "Output was not valid against the schema: "
                                f"{str(exc)[:800]}"
                            ),
                        ]

                    delay = retry_delays[attempt]

                    logger.warning(
                        "Gemini project plan generation failed on attempt "
                        "%s/3. Retrying in %s seconds. Error: %s",
                        attempt + 1,
                        delay,
                        exc,
                    )

                    time.sleep(delay)
                    continue

                logger.exception(
                    "Gemini project plan generation failed"
                )

                raise ProviderConfigurationError(
                    f"Project plan generation failed: {exc}"
                ) from exc

    def generate_hld(
        self,
        project_name: str,
        project_description: str,
        requirements: dict,
        plan: dict,
        preferred_stack: dict,
        feedback: list[str] | None = None,
    ) -> HighLevelDesign:
        return self._generate_design(
            HighLevelDesign,
            "High-level design",
            lambda problems: hld_prompt(
                project_name, project_description, requirements, plan, preferred_stack, problems
            ),
            feedback,
        )

    def generate_lld(
        self,
        project_name: str,
        project_description: str,
        requirements: dict,
        plan: dict,
        hld: dict,
        preferred_stack: dict,
        feedback: list[str] | None = None,
    ) -> LowLevelDesign:
        return self._generate_design(
            LowLevelDesign,
            "Low-level design",
            lambda problems: lld_prompt(
                project_name, project_description, requirements, plan, hld, preferred_stack, problems
            ),
            feedback,
        )

    def _generate_design(self, model, label: str, build_prompt, feedback: list[str] | None):
        """Structured generation with retries for transient errors and malformed output.

        Same retry policy as the project plan: three attempts, backing off on 429/503,
        and feeding schema errors back to the model.
        """
        problems = list(feedback or [])
        retry_delays = [2, 5]

        for attempt in range(3):
            prompt = build_prompt(problems)
            try:
                from google.genai import types

                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=_architect_response_schema(model),
                        temperature=0.1 if problems else 0.2,
                        max_output_tokens=32000,
                    ),
                )

                parsed = getattr(response, "parsed", None)
                if parsed is None:
                    parsed = json.loads(response.text)
                if isinstance(parsed, model):
                    return parsed
                return model.model_validate(parsed)

            except Exception as exc:
                is_validation_error = isinstance(exc, (json.JSONDecodeError, ValidationError))

                if attempt < 2 and (_is_retryable(exc) or is_validation_error):
                    if is_validation_error:
                        problems = [*problems, f"Output was not valid against the schema: {str(exc)[:800]}"]
                    delay = retry_delays[attempt]
                    logger.warning(
                        "Gemini %s generation failed on attempt %s/3. Retrying in %s seconds. Error: %s",
                        label.lower(), attempt + 1, delay, exc,
                    )
                    time.sleep(delay)
                    continue

                logger.exception("Gemini %s generation failed", label.lower())
                raise ProviderConfigurationError(f"{label} generation failed: {exc}") from exc

    def answer_question(
        self,
        question: str,
        contexts: list[dict],
    ) -> str:

        prompt = f"""
Answer the user's question using only the retrieved SRS excerpts below.

If the excerpts do not contain the answer, say that the SRS does not specify it.

Do not invent facts.

Do not mention sources that are not supplied.

Question:
{question}

RETRIEVED SRS EXCERPTS:

{_format_contexts(contexts)}
"""

        for attempt in range(2):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config={"temperature": 0.1},
                )

                return response.text.strip()

            except Exception as exc:

                if attempt == 0 and _is_retryable(exc):
                    time.sleep(1.5)
                    continue

                logger.exception("Gemini RAG answer failed")

                raise ProviderConfigurationError(
                    f"RAG answer failed: {exc}"
                ) from exc


def _project_plan_prompt(
    project_name: str,
    project_description: str,
    requirements: dict,
    project_info: dict,
) -> str:

    start = project_info.get("start_date") or "not provided"
    due = project_info.get("due_date") or "not provided"

    allowed_ids = _extract_allowed_ids(requirements)

    return f"""
You are the Project Manager AI for the software project "{project_name}".

Project description:
{project_description or "Not provided"}

Project start date:
{start}

Project due date:
{due}

Team size, velocity and working calendar:
NOT PROVIDED.

Your ONLY input is the validated output of the Requirements Analyst,
given below as JSON.

Do not re-derive requirements.

Do not assume anything about the SRS beyond this JSON.

Turn the Requirements Analyst output into an execution plan.

============================================================
STRICT ID RULES
============================================================

This is extremely important.

You MUST use ONLY IDs that already exist in the Requirements Analyst output.

NEVER invent IDs.

NEVER create new requirement IDs.

NEVER change an ID.

NEVER guess an ID.

VALID REQUIREMENT IDs:
{", ".join(allowed_ids["requirements"]) or "NONE"}

VALID USER STORY IDs:
{", ".join(allowed_ids["stories"]) or "NONE"}

VALID ACCEPTANCE CRITERIA IDs:
{", ".join(allowed_ids["acceptance_criteria"]) or "NONE"}

VALID NON-FUNCTIONAL REQUIREMENT IDs:
{", ".join(allowed_ids["non_functional"]) or "NONE"}

VALID CONSTRAINT IDs:
{", ".join(allowed_ids["constraints"]) or "NONE"}

VALID DEPENDENCY IDs:
{", ".join(allowed_ids["dependencies"]) or "NONE"}

VALID AMBIGUITY IDs:
{", ".join(allowed_ids["ambiguities"]) or "NONE"}

VALID RISK IDs:
{", ".join(allowed_ids["risks"]) or "NONE"}

REFERENCE RULES:

1. epic.related_requirement_ids
   → ONLY REQ-* IDs.

2. task.related_requirement_id
   → ONLY REQ-* IDs or null.

3. task.related_story_id
   → ONLY US-* IDs or null.

4. task.related_artifact_ids
   → Can contain valid AC, NFR, CON, DEP, AMB or RISK IDs.

5. NFR-* MUST NEVER be used as related_requirement_id.

6. CON-* MUST NEVER be used as related_requirement_id.

7. US-* MUST NEVER be used as related_requirement_id.

8. If no valid reference exists, use null.

9. Every referenced ID must exist in the lists above.

10. Before returning the plan, verify every ID.

============================================================
GROUNDING
============================================================

Every task must be traceable.

Cite IDs exactly as they appear in the input.

Examples:

REQ-1
US-2
AC-5
NFR-1
CON-1
DEP-1
AMB-1
RISK-1

grounding = EXPLICIT
when the input directly calls for the work.

grounding = INFERRED
for reasonable engineering prerequisites that the input implies but
does not explicitly state.

Explain inferred work in rationale.

grounding = AMBIGUOUS
when the input is too vague to build safely.

grounding = UNKNOWN
when required information is unavailable.

Do NOT add features, integrations or capabilities that the requirements
do not support.

If the input does not mention social login, payments, biometrics,
OAuth, etc., they must not appear.

============================================================
TASKS
============================================================

Break every functional requirement and user story into concrete,
implementable tasks.

Only include work justified by the Requirements Analyst output.

Each non-functional requirement and each constraint must be addressed
by at least one appropriate task.

story_points must be one of:

1
2
3
5
8
13

Split anything larger than 13.

suggested_role must be one of:

Frontend Developer
Backend Developer
Full Stack Developer
Database Engineer
AI/ML Engineer
DevOps Engineer
QA Engineer
Security Engineer
UI/UX Designer

Choose the role whose skills the task actually needs.

acceptance_criteria must contain concrete, testable statements.

============================================================
EPICS
============================================================

Group tasks under coherent epics.

Epic requirement references must use ONLY valid REQ-* IDs.

Never put US-* IDs into epic.related_requirement_ids.

============================================================
DEPENDENCIES
============================================================

Each dependency contains:

task_id
depends_on_task_id
dependency_type
description
is_blocking

dependency_type must be one of:

TECHNICAL
DATA
INTEGRATION
PREREQUISITE
EXTERNAL

The dependency graph must contain no cycles.

EXTERNAL dependencies may have depends_on_task_id = null.

============================================================
SPRINTS
============================================================

Choose the number of sprints based on the actual amount of work.

Do not use a fixed number.

Assign every task to exactly one sprint.

A task's sprint must be the same as or later than the sprint of
every task it depends on.

Put foundational and high-priority work first.

Use ISO dates only when they can be derived without guessing capacity.

Otherwise use null.

Team size and velocity are not provided.

Do not invent capacity numbers.

============================================================
MILESTONES
============================================================

Milestones should represent meaningful groups of completed tasks.

Each milestone can contain:

milestone_id
name
description
task_ids
target_sprint

============================================================
RISKS
============================================================

Risks must be specific to this project.

Use actual ambiguities, constraints and dependencies where relevant.

Do not generate generic risks without project justification.

Include:

impact
likelihood
mitigation
related_tasks

============================================================
DEFINITION OF DONE
============================================================

Create a project-specific Definition of Done.

Consider:

implementation complete
acceptance criteria satisfied
tests passing
security requirements satisfied
integration verified
documentation updated

Only include items appropriate to this project.

============================================================
ASSUMPTIONS
============================================================

List only assumptions that were actually necessary.

Use an empty list if no assumptions were necessary.

============================================================
IDENTIFIER FORMAT
============================================================

Generated execution-plan IDs may use:

epic_id:
E1, E2, E3...

task_id:
T1, T2, T3...

sprint_id:
S1, S2, S3...

milestone_id:
M1, M2, M3...

risk_id:
RK1, RK2, RK3...

These execution-plan IDs are different from Requirements Analyst IDs.

Do NOT confuse them.

============================================================
FINAL VALIDATION BEFORE RETURNING JSON
============================================================

Before returning the project plan:

1. Check every epic requirement reference.
2. Check every task requirement reference.
3. Check every task story reference.
4. Check every artifact reference.
5. Ensure every referenced Requirements Analyst ID exists.
6. Ensure REQ IDs are used only for requirements.
7. Ensure US IDs are used only for user stories.
8. Ensure NFR/CON/AC/etc. are not incorrectly used as requirements.
9. Remove any invented IDs.
10. Use null when no valid reference exists.

Return JSON matching the ProjectPlan schema exactly.

============================================================
REQUIREMENTS ANALYST OUTPUT
============================================================

{json.dumps(requirements, indent=1, default=str)}
"""


def _extract_allowed_ids(requirements: dict) -> dict[str, list[str]]:
    """
    Extract the IDs actually present in the Requirements Analyst output.

    The PM must use these IDs and nothing else.
    """

    result = {
        "requirements": [],
        "stories": [],
        "acceptance_criteria": [],
        "non_functional": [],
        "constraints": [],
        "dependencies": [],
        "ambiguities": [],
        "risks": [],
    }

    if not isinstance(requirements, dict):
        return result

    def collect(items, destination):
        if not isinstance(items, list):
            return

        for item in items:
            if isinstance(item, dict):
                item_id = item.get("id")

                if item_id and isinstance(item_id, str):
                    if item_id not in destination:
                        destination.append(item_id)

    collect(
        requirements.get("functional_requirements"),
        result["requirements"],
    )

    collect(
        requirements.get("requirements"),
        result["requirements"],
    )

    collect(
        requirements.get("user_stories"),
        result["stories"],
    )

    collect(
        requirements.get("acceptance_criteria"),
        result["acceptance_criteria"],
    )

    collect(
        requirements.get("non_functional_requirements"),
        result["non_functional"],
    )

    collect(
        requirements.get("constraints"),
        result["constraints"],
    )

    collect(
        requirements.get("dependencies"),
        result["dependencies"],
    )

    collect(
        requirements.get("ambiguities"),
        result["ambiguities"],
    )

    collect(
        requirements.get("risks"),
        result["risks"],
    )

    return result


def _format_contexts(contexts: list[dict]) -> str:
    return "\n\n".join(
        f"[{item['filename']} page {item['page']} | {item['source']}]\n"
        f"{item['text']}"
        for item in contexts
    )


def _is_retryable(error: Exception) -> bool:
    message = str(error).upper()

    return any(
        marker in message
        for marker in (
            "503",
            "UNAVAILABLE",
            "429",
            "RESOURCE_EXHAUSTED",
            "DEADLINE",
        )
    )


def _gemini_response_schema(model=RequirementsAnalysis) -> dict:
    """Gemini rejects Pydantic defaults even though they are valid JSON Schema."""

    schema = model.model_json_schema()

    def remove_defaults(value):
        if isinstance(value, dict):
            return {
                key: remove_defaults(item)
                for key, item in value.items()
                if key != "default"
            }

        if isinstance(value, list):
            return [
                remove_defaults(item)
                for item in value
            ]

        return value

    return remove_defaults(schema)


def _architect_response_schema(model) -> dict:
    """Schema for the System Architect calls: every property is required.

    Pydantic leaves fields that have a default (``rationale = None``, ``data_flows = []``)
    out of ``required``, and Gemini then treats them as optional and often omits them. For
    the design documents that silently drops the rationale of INFERRED / ASSUMED items and
    whole sections such as the data flows. Requiring every property makes Gemini always
    write them; nullable fields still accept an explicit null.
    """

    def require_all(value):
        if isinstance(value, dict):
            result = {key: require_all(item) for key, item in value.items()}
            properties = result.get("properties")
            if result.get("type") == "object" and isinstance(properties, dict) and properties:
                result["required"] = list(properties)
            return result
        if isinstance(value, list):
            return [require_all(item) for item in value]
        return value

    return require_all(_gemini_response_schema(model))
