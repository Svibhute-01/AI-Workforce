"""Scripted "LLM answers" used ONLY by unit tests.

``registration_plan(payload)`` is what a good model response looks like for the
Customer Registration SRS. It is built from the ids in the payload the agent
actually sent, so it always references real ids. The production code never uses
this module.
"""

import copy

from app.schemas_pm import ProjectPlan


def _index(payload: dict) -> dict:
    return {
        "REQ": {r["title"]: r["id"] for r in payload["functional_requirements"]},
        "NFR": {n["category"]: n["id"] for n in payload["non_functional_requirements"]},
        "US": {s["title"]: s["id"] for s in payload["user_stories"]},
        "AC": [a["id"] for a in payload["acceptance_criteria"]],
        "AMB": [a["id"] for a in payload["ambiguities"]],
        "DEP": [d["id"] for d in payload["dependencies"]],
        "CON": [c["id"] for c in payload["constraints"]],
    }


def registration_plan_dict(payload: dict) -> dict:
    i = _index(payload)
    REQ, NFR, US, AC, AMB, DEP, CON = i["REQ"], i["NFR"], i["US"], i["AC"], i["AMB"], i["DEP"], i["CON"]
    reg, reg_story = REQ["Customer Registration"], US["Register with email and password"]

    def task(task_id, title, description, epic, sprint, role, points, priority, grounding="EXPLICIT", **extra):
        return {
            "task_id": task_id, "title": title, "description": description, "epic_id": epic, "sprint": sprint,
            "suggested_role": role, "story_points": points, "priority": priority, "grounding": grounding,
            "acceptance_criteria": extra.pop("acceptance_criteria", [f"{title} works as described."]),
            "related_artifact_ids": extra.pop("related_artifact_ids", []), **extra,
        }

    tasks = [
        task("T1", "Set up service skeleton and database migrations",
             "Create the registration service project structure and the migration tooling needed to create the account table.",
             "E1", "S1", "Backend Developer", 3, "HIGH", "INFERRED",
             rationale="Engineering prerequisite: the account data model cannot be built without a service and migrations."),
        task("T2", "Design account data model with unique email constraint",
             "Create the customer account table with a case-insensitive unique email column so existing emails can be identified.",
             "E1", "S1", "Database Engineer", 3, "HIGH", related_requirement_id=REQ["Duplicate Email Handling"],
             related_artifact_ids=[DEP[0]]),
        task("T3", "Clarify password complexity policy",
             "Obtain a decision on the password rules; the SRS does not define them.",
             "E1", "S1", "Backend Developer", 1, "MEDIUM", "AMBIGUOUS",
             related_requirement_id=REQ["Password Requirement"], related_artifact_ids=[AMB[0]],
             rationale="The SRS states that a password is required but not its complexity policy."),
        task("T4", "Implement registration endpoint",
             "Accept an email address and password and orchestrate account creation.",
             "E2", "S1", "Backend Developer", 5, "HIGH", related_requirement_id=reg, related_story_id=reg_story,
             related_artifact_ids=[AC[0]]),
        task("T5", "Validate email format", "Reject registrations whose email address is not in a valid format.",
             "E2", "S1", "Backend Developer", 2, "MEDIUM", related_requirement_id=REQ["Email Validation"],
             related_artifact_ids=[AC[2]]),
        task("T6", "Require password on registration", "Reject registrations that omit the password.",
             "E2", "S1", "Backend Developer", 2, "MEDIUM", related_requirement_id=REQ["Password Requirement"]),
        task("T7", "Store passwords using a salted hash",
             "Hash passwords with a strong adaptive algorithm; never persist plaintext.",
             "E2", "S1", "Security Engineer", 3, "HIGH", related_artifact_ids=[NFR["Security"], AC[6]]),
        task("T8", "Reject duplicate email registrations",
             "Return a rejection when the email already belongs to an account, including under concurrent requests.",
             "E2", "S2", "Backend Developer", 3, "HIGH", related_requirement_id=REQ["Duplicate Email Handling"],
             related_story_id=US["Reject duplicate registration"], related_artifact_ids=[AC[1]]),
        task("T9", "Create customer account on valid registration",
             "Persist the customer account when the data is valid and the email is unused.",
             "E2", "S2", "Backend Developer", 3, "HIGH", related_requirement_id=REQ["Successful Registration"],
             related_artifact_ids=[AC[3]]),
        task("T10", "Integrate email delivery capability",
             "Connect to an email-delivery service that can send transactional email.",
             "E3", "S2", "Backend Developer", 5, "MEDIUM", related_requirement_id=REQ["Confirmation Email"],
             related_artifact_ids=[DEP[2], AMB[1]]),
        task("T11", "Send confirmation email after account creation",
             "Send a confirmation email to the registered address once the account exists.",
             "E3", "S2", "Backend Developer", 5, "MEDIUM", related_requirement_id=REQ["Confirmation Email"],
             related_story_id=US["Receive confirmation email"], related_artifact_ids=[DEP[1], AC[4]]),
        task("T12", "Report email delivery failures honestly",
             "Never report a confirmation email as delivered when sending failed.",
             "E3", "S2", "Backend Developer", 3, "MEDIUM", related_artifact_ids=[NFR["Reliability"], AMB[2]]),
        task("T13", "Return registration result", "Return whether account creation succeeded or failed.",
             "E2", "S2", "Backend Developer", 2, "LOW", related_requirement_id=REQ["Registration Response"]),
        task("T14", "Verify registration completes within two seconds",
             "Load-test registration to check the two-second target under the agreed normal operating conditions.",
             "E4", "S3", "QA Engineer", 3, "MEDIUM", "AMBIGUOUS",
             related_artifact_ids=[NFR["Performance"], AC[5], CON[1], AMB[3]],
             rationale="'Normal operating conditions' is not defined in the requirements."),
        task("T15", "Write automated tests for registration flows",
             "Cover valid registration, invalid email, missing password, duplicates and confirmation email.",
             "E4", "S3", "QA Engineer", 5, "HIGH", related_story_id=reg_story, related_requirement_id=reg,
             related_artifact_ids=[AC[0], AC[1], AC[2], AC[3], AC[4]]),
    ]

    edges = [
        ("T2", "T1", "TECHNICAL"), ("T4", "T1", "TECHNICAL"), ("T4", "T2", "DATA"),
        ("T5", "T4", "TECHNICAL"), ("T6", "T4", "TECHNICAL"), ("T7", "T2", "DATA"),
        ("T8", "T2", "DATA"), ("T8", "T4", "TECHNICAL"), ("T9", "T7", "PREREQUISITE"),
        ("T9", "T8", "PREREQUISITE"), ("T11", "T9", "PREREQUISITE"), ("T11", "T10", "INTEGRATION"),
        ("T12", "T11", "TECHNICAL"), ("T13", "T9", "TECHNICAL"), ("T14", "T11", "PREREQUISITE"),
        ("T15", "T13", "PREREQUISITE"), ("T15", "T12", "PREREQUISITE"),
    ]
    dependencies = [
        {"task_id": a, "depends_on_task_id": b, "dependency_type": kind, "description": f"{a} needs {b}",
         "is_blocking": kind in ("PREREQUISITE", "DATA")}
        for a, b, kind in edges
    ]
    dependencies.append({"task_id": "T10", "depends_on_task_id": None, "dependency_type": "EXTERNAL",
                         "description": "An email-delivery service must be available and credentials provisioned.",
                         "is_blocking": True})

    return {
        "execution_summary": "Build email/password registration first, then duplicate handling and account creation, "
                             "then confirmation email, and finish with performance and regression verification.",
        "epics": [
            {"epic_id": "E1", "title": "Foundations", "description": "Service, data model and open decisions.",
             "priority": "HIGH", "related_requirement_ids": [REQ["Duplicate Email Handling"]]},
            {"epic_id": "E2", "title": "Registration", "description": "Registering customers.",
             "priority": "HIGH", "related_requirement_ids": [reg, REQ["Email Validation"]]},
            {"epic_id": "E3", "title": "Confirmation email", "description": "Confirming registrations by email.",
             "priority": "MEDIUM", "related_requirement_ids": [REQ["Confirmation Email"]]},
            {"epic_id": "E4", "title": "Quality", "description": "Performance and regression testing.",
             "priority": "MEDIUM", "related_requirement_ids": []},
        ],
        "tasks": tasks,
        "dependencies": dependencies,
        "sprints": [
            {"sprint_id": "S1", "name": "Registration core", "goal": "Accept and validate registrations.",
             "capacity_notes": "Team size and velocity are not provided."},
            {"sprint_id": "S2", "name": "Accounts and email", "goal": "Create accounts and send confirmations.",
             "capacity_notes": "Team size and velocity are not provided."},
            {"sprint_id": "S3", "name": "Verification", "goal": "Prove performance and correctness.",
             "capacity_notes": "Team size and velocity are not provided."},
        ],
        "milestones": [
            {"milestone_id": "M1", "title": "Registration API accepts valid input",
             "description": "Endpoint, validation and password hashing complete.",
             "task_ids": ["T4", "T5", "T6", "T7"], "target_sprint": "S1"},
            {"milestone_id": "M2", "title": "Confirmation email sent",
             "description": "Accounts are created and confirmation emails go out.",
             "task_ids": ["T9", "T10", "T11", "T12"], "target_sprint": "S2"},
            {"milestone_id": "M3", "title": "Quality gate passed",
             "description": "Performance target and regression tests pass.",
             "task_ids": ["T14", "T15"], "target_sprint": "S3"},
        ],
        "risks": [
            {"risk_id": "RK1", "title": "Email provider unavailable",
             "description": "Confirmation emails depend on an external delivery service that is not yet chosen.",
             "impact": "HIGH", "likelihood": "MEDIUM",
             "mitigation": "Choose a provider early and hide it behind an interface so it can be swapped.",
             "related_tasks": ["T10", "T11"]},
            {"risk_id": "RK2", "title": "Password policy undefined",
             "description": "Without a defined complexity policy, validation may need rework.",
             "impact": "MEDIUM", "likelihood": "HIGH",
             "mitigation": "Get the policy decided in sprint 1 before implementing validation.",
             "related_tasks": ["T3", "T6"]},
            {"risk_id": "RK3", "title": "Two-second target cannot be verified",
             "description": "'Normal operating conditions' is undefined, so the target cannot be tested objectively.",
             "impact": "MEDIUM", "likelihood": "MEDIUM",
             "mitigation": "Agree a load profile before writing the performance test.",
             "related_tasks": ["T14"]},
        ],
        "definition_of_done": {"items": [
            "Registration behavior implemented and reviewed",
            "Every cited acceptance criterion is satisfied",
            "Automated tests pass",
            "Passwords are verified not to be stored as plaintext",
            "Confirmation email flow verified end to end",
            "Registration meets the two-second target under the agreed conditions",
            "API documentation updated",
        ]},
        "assumptions": [],
    }


def registration_plan(payload: dict) -> ProjectPlan:
    return ProjectPlan.model_validate(registration_plan_dict(payload))


def mutated(payload: dict, mutate) -> ProjectPlan:
    """Build the good plan, apply ``mutate(dict)``, and validate the result."""
    data = copy.deepcopy(registration_plan_dict(payload))
    mutate(data)
    return ProjectPlan.model_validate(data)
