"""Prompts for the System Architect AI (pure string builders, no provider or database imports)."""

import json

_ID_KINDS = (
    ("requirements", "VALID REQUIREMENT / STORY / NFR / CONSTRAINT / OTHER REQUIREMENTS-ANALYST IDs"),
)


def requirement_ids_by_kind(requirements: dict) -> dict[str, list[str]]:
    """Group the ids present in the Requirements Analyst payload."""
    groups = {
        "functional_requirements": "REQ",
        "user_stories": "US",
        "acceptance_criteria": "AC",
        "non_functional_requirements": "NFR",
        "constraints": "CON",
        "dependencies": "DEP",
        "ambiguities": "AMB",
        "risks": "RISK",
    }
    result: dict[str, list[str]] = {}
    for key, prefix in groups.items():
        items = requirements.get(key) if isinstance(requirements, dict) else None
        ids = [i["id"] for i in items if isinstance(i, dict) and isinstance(i.get("id"), str)] if isinstance(items, list) else []
        result[prefix] = ids
    return result


def _id_block(requirements: dict, plan: dict) -> str:
    groups = requirement_ids_by_kind(requirements)
    labels = {
        "REQ": "FUNCTIONAL REQUIREMENT IDs (REQ-*)",
        "US": "USER STORY IDs (US-*)",
        "AC": "ACCEPTANCE CRITERIA IDs (AC-*)",
        "NFR": "NON-FUNCTIONAL REQUIREMENT IDs (NFR-*)",
        "CON": "CONSTRAINT IDs (CON-*)",
        "DEP": "DEPENDENCY IDs (DEP-*)",
        "AMB": "AMBIGUITY IDs (AMB-*)",
        "RISK": "REQUIREMENTS-ANALYST RISK IDs (RISK-*)",
    }
    lines = [f"{labels[prefix]}:\n{', '.join(ids) or 'NONE'}" for prefix, ids in groups.items()]
    task_ids = [t["id"] for t in plan.get("tasks", []) if isinstance(t, dict) and "id" in t]
    lines.append(f"PROJECT MANAGER TASK IDs (T*):\n{', '.join(task_ids) or 'NONE'}")
    return "\n\n".join(lines)


_GROUNDING_RULES = """
============================================================
GROUNDING AND HONESTY (extremely important)
============================================================

Every design element carries a `grounding` classification:

EXPLICIT  - the requirements directly state or require it. It MUST cite at least one
            requirement id in `requirement_ids`.
INFERRED  - a reasonable engineering consequence of the requirements that they do not
            state. It MUST explain the inference in `rationale`.
ASSUMED   - a decision the requirements leave open and you had to make. It MUST give
            the reasoning and the trade-off in `rationale`, and be recorded in
            `open_items` with kind ASSUMED.
UNKNOWN   - the requirements do not say and you could not responsibly decide. Say so;
            record it in `open_items` with kind UNKNOWN.

Rules:
1. NEVER invent a requirement id or a task id. Cite ONLY ids from the lists below.
2. `requirement_ids` takes Requirements Analyst ids ONLY. `task_ids` takes Project
   Manager task ids ONLY. Never mix them up.
3. Do NOT introduce a technology, integration, feature or actor because it is popular.
   If the requirements do not call for it, leave it out.
4. The Developer AI can build and verify ONLY the project stack below, so design with it:
   use it for the backend, the database and the frontend, and name its technologies on
   the components. Because the SRS does not choose a stack, choices that use it are
   ASSUMED, with the trade-off explained. Do NOT propose another language, framework,
   database or frontend framework for those layers. If the requirements truly cannot be
   met with this stack, say so in `open_items` as UNKNOWN instead of choosing something
   the Developer cannot build.
5. If a decision is not specified, state the assumption and the trade-off. Never present
   an assumption as a requirement.
6. Do NOT write application source code. Signatures, field lists, schemas and short
   pseudocode are the level of detail wanted.
7. Cite requirements and tasks on every element that exists because of them, so the
   design is traceable. Every functional requirement and every non-functional
   requirement should be addressed by at least one element.

Every element has a `rationale` field and you MUST always fill it in. For INFERRED and
ASSUMED it must be a real explanation (one or two sentences); an empty or null rationale
is rejected. For EXPLICIT and UNKNOWN give a short reason for the element.
""".strip()


def _stack_block(preferred_stack: dict) -> str:
    return "\n".join(f"- {key}: {value}" for key, value in preferred_stack.items())


def _repair_block(problems: list[str], extra_ids: str = "") -> str:
    if not problems:
        return ""
    listed = "\n- ".join(problems[:40])
    return f"""

============================================================
YOUR PREVIOUS ATTEMPT WAS REJECTED
============================================================

Fix ALL of these problems and return the COMPLETE corrected output (not a patch):

- {listed}

Do not simply regenerate the same output. Every id you cite must exist in the lists
given in this prompt; use null / an empty list when there is nothing valid to cite.
{extra_ids}
""".rstrip()


def hld_prompt(
    project_name: str,
    project_description: str,
    requirements: dict,
    plan: dict,
    preferred_stack: dict,
    problems: list[str] | None = None,
) -> str:
    return f"""
You are the System Architect AI for the software project "{project_name}".

Project description:
{project_description or "Not provided"}

Your inputs are the validated output of the Requirements Analyst and of the Project
Manager, given below as JSON. You do not read the SRS. Produce the HIGH-LEVEL DESIGN
(HLD) that a Developer can later refine into implementation.

{_GROUNDING_RULES}

PROJECT STACK (the only stack the Developer AI can build):
{_stack_block(preferred_stack)}

============================================================
VALID IDs YOU MAY CITE
============================================================

{_id_block(requirements, plan)}

============================================================
WHAT THE HLD MUST CONTAIN
============================================================

overview             - what is being built and the shape of the solution.
style                - the architecture style/pattern, with its grounding and rationale.
system_architecture  - a prose description of how the pieces fit together.
actors               - the people or outside systems that USE the system (A1, A2, ...), for
                       example a customer or an administrator. Each has a name, a description,
                       a short `interaction` phrase (how they use the system), the
                       component_ids they interact with directly, and grounding. Do not
                       list components or external services the system calls as actors.
components           - the major components/modules. component_id C1, C2, ... Each has a
                       type, description, concrete responsibilities, technology (or null)
                       and grounding. Create only components the requirements justify.
relationships        - component-to-component communication. relationship_id R1, R2, ...
                       source_component_id / target_component_id MUST be component ids;
                       a component must not relate to itself. `protocol` is a short label
                       for how they talk (for example "REST over HTTPS", "SQL", "SMTP");
                       give it ONLY when the requirements or your stated decisions support
                       it, otherwise null.
data_flows           - the main system/data flows. flow_id DF1, DF2, ... Ordered steps
                       (order 1, 2, 3...) between existing components. You MUST include
                       at least one flow (for example the main user journey); an empty list
                       is rejected.
integrations         - external systems the requirements need (INT1, INT2, ...). If none,
                       use an empty list. component_id is the component that talks to it.
deployment           - where the components run (DN1, DN2, ...): a client device, a
                       server, a container, a managed/cloud service. Each node has a name, a
                       kind, a technology (or null), a description, grounding, and the
                       component_ids that run there. A component runs on at most one node;
                       external systems are not deployed by you. If the requirements do not
                       say how the system is hosted, still propose nodes, classify them
                       ASSUMED with a rationale and record an open item.
decisions            - technology and architecture decisions (D1, D2, ...) with
                       alternatives_considered, tradeoffs and rationale.
quality_considerations - Q1, Q2, ... You MUST include at least one entry for EACH of:
                       AUTHENTICATION_AUTHORIZATION, SCALABILITY, RELIABILITY, SECURITY,
                       DEPLOYMENT. If the requirements say nothing about a topic, still
                       include the entry, state that it is unspecified, classify it
                       UNKNOWN (or ASSUMED with a rationale) and record an open item.
                       PERFORMANCE / OBSERVABILITY / OTHER entries are optional.
risks                - architecture risks specific to THIS design (AR1, AR2, ...), with
                       impact, likelihood, mitigation, and the components they concern.
open_items           - every ASSUMED or UNKNOWN matter (OH1, OH2, ...) with kind,
                       statement and impact.

Do NOT include an architecture diagram: it is generated from your components and
relationships afterwards, so those two lists must be complete and accurate.

Return JSON matching the HighLevelDesign schema exactly.
{_repair_block(problems or [])}

============================================================
REQUIREMENTS ANALYST OUTPUT
============================================================

{json.dumps(requirements, indent=1, default=str)}

============================================================
PROJECT MANAGER PLAN
============================================================

{json.dumps(plan, indent=1, default=str)}
"""


def lld_prompt(
    project_name: str,
    project_description: str,
    requirements: dict,
    plan: dict,
    hld: dict,
    preferred_stack: dict,
    problems: list[str] | None = None,
) -> str:
    component_ids = [c["component_id"] for c in hld.get("components", []) if isinstance(c, dict) and "component_id" in c]
    extra = f"\nVALID COMPONENT IDs FROM THE HLD:\n{', '.join(component_ids) or 'NONE'}\n"
    return f"""
You are the System Architect AI for the software project "{project_name}".

Project description:
{project_description or "Not provided"}

The HIGH-LEVEL DESIGN below has already been validated. Produce the matching LOW-LEVEL
DESIGN (LLD): an implementation blueprint detailed enough for a Developer AI to build
from. Stay consistent with the HLD and do not contradict or re-decide it.

{_GROUNDING_RULES}

PROJECT STACK (the only stack the Developer AI can build; keep the LLD within it):
{_stack_block(preferred_stack)}

============================================================
VALID IDs YOU MAY CITE
============================================================

{_id_block(requirements, plan)}

VALID COMPONENT IDs FROM THE HLD:
{', '.join(component_ids) or 'NONE'}

============================================================
WHAT THE LLD MUST CONTAIN
============================================================

modules          - M1, M2, ... controllers, services, repositories, models, UI
                   components, etc. Each belongs to ONE HLD component (component_id),
                   has responsibilities, methods (name, signature, description) and
                   depends_on_module_ids (existing module ids, never itself).
                   Module ids must differ from component ids.
interfaces       - I1, I2, ... abstractions between modules, implemented by existing
                   modules.
data_models      - DM1, DM2, ... request / response / DTO models with typed fields
                   (data_model_id, kind REQUEST|RESPONSE|DTO, fields with name, type,
                   required, validation). Write this list BEFORE the apis. Every model an
                   API uses must be defined here, with an id of exactly the form DM<number>
                   (DM1, DM2, ...). Never use descriptive ids such as DM_USER_RESP.
apis             - API1, API2, ... Each has a component_id, the controller module_id in
                   that SAME component (or null), HTTP method, path (starting with "/"),
                   summary, auth_required, request_model_id / response_model_id (an id
                   you defined in data_models, such as DM3, or null when the call has no body
                   to describe; never an id that is not in data_models), errors (status_code 100-599 + condition) and
                   validation_rules. No two APIs may share method + path.
tables           - TBL1, TBL2, ... database tables with columns (name, type,
                   primary_key, nullable, unique) - every table needs a primary key.
table_relationships - TR1, TR2, ... between existing tables and EXISTING columns, with
                   cardinality. source_column is the foreign key that references
                   target_column. Read cardinality from the referenced (target) table to the
                   referencing (source) table: ONE_TO_MANY = one target row has many source
                   rows (the usual foreign key), ONE_TO_ONE, MANY_TO_MANY (via a join table).
business_rules   - BR1, BR2, ... important business logic; add short pseudocode where
                   it helps (algorithms, state transitions). module_id may be null.
sequence_flows   - SEQ1, SEQ2, ... one per important use case. Declare participants
                   (participant_id P1, P2, ...; ref_id is an HLD component id or a
                   module id, or null for an actor such as the end user), then ordered
                   steps (order 1, 2, 3...) between declared participants. A step may
                   reference an api_id.
design_patterns  - DP1, DP2, ... only where a pattern is genuinely applied, with the
                   modules it applies to and why.
error_handling   - ER1, ER2, ... the error-handling approach (and the api_ids / HTTP
                   status codes it applies to).
validation_rules - VR1, VR2, ... input/business validation, optionally tied to a
                   data_model_id and field_name.
open_items       - every ASSUMED or UNKNOWN matter in the LLD (OL1, OL2, ...). Use the
                   OL prefix; the HLD already used OH.

If the requirements need no database or no HTTP API, use an empty list for it rather than
inventing one.

Return JSON matching the LowLevelDesign schema exactly.
{_repair_block(problems or [], extra)}

============================================================
VALIDATED HIGH-LEVEL DESIGN
============================================================

{json.dumps(hld, indent=1, default=str)}

============================================================
REQUIREMENTS ANALYST OUTPUT
============================================================

{json.dumps(requirements, indent=1, default=str)}

============================================================
PROJECT MANAGER PLAN
============================================================

{json.dumps(plan, indent=1, default=str)}
"""
