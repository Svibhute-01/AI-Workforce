"""Scripted "LLM answers" used ONLY by the Architect unit tests.

``registration_hld(requirements, plan)`` / ``registration_lld(...)`` are what good model
responses look like for the Customer Registration SRS. They are built from the ids in the
payloads the agent actually sent, so they always cite real ids. The production code never
uses this module.
"""

import copy

from app.schemas_architect import HighLevelDesign, LowLevelDesign

from .conftest import ScriptedProvider


def _ids(requirements: dict) -> dict:
    return {
        "REQ": {r["title"]: r["id"] for r in requirements["functional_requirements"]},
        "NFR": {n["category"]: n["id"] for n in requirements["non_functional_requirements"]},
        "US": {s["title"]: s["id"] for s in requirements["user_stories"]},
        "AMB": [a["id"] for a in requirements["ambiguities"]],
        "CON": [c["id"] for c in requirements["constraints"]],
    }


def registration_hld_dict(requirements: dict, plan: dict) -> dict:
    i = _ids(requirements)
    REQ, NFR = i["REQ"], i["NFR"]
    all_req = list(REQ.values())

    def traced(grounding, req=(), tasks=(), rationale=None):
        return {"grounding": grounding, "requirement_ids": list(req), "task_ids": list(tasks), "rationale": rationale}

    return {
        "overview": "A web application that lets customers register with an email and password and receive a confirmation email.",
        "style": {
            "name": "Layered monolith",
            "description": "One deployable backend with controller, service and repository layers, plus a React client.",
            **traced("ASSUMED", rationale="The SRS does not choose a style; a single service is enough for one registration flow."),
        },
        "system_architecture": "The browser client calls the registration API; the API validates input, stores the account in the database and asks the email provider to send the confirmation.",
        "actors": [
            {"actor_id": "A1", "name": "Customer", "description": "A person who registers for an account.",
             "interaction": "Registers through the web form", "component_ids": ["C1"],
             **traced("EXPLICIT", [REQ["Customer Registration"]])},
        ],
        "components": [
            {"component_id": "C1", "name": "Web Client", "type": "FRONTEND", "description": "Registration form.",
             "responsibilities": ["Collect email and password", "Show the registration result"], "technology": "React",
             **traced("EXPLICIT", [REQ["Customer Registration"], REQ["Registration Response"]], ["T4"])},
            {"component_id": "C2", "name": "Registration API", "type": "API", "description": "Validates input and creates accounts.",
             "responsibilities": ["Validate email and password", "Reject duplicate emails", "Create the account", "Trigger confirmation email"],
             "technology": "FastAPI",
             **traced("EXPLICIT", [REQ["Email Validation"], REQ["Password Requirement"], REQ["Duplicate Email Handling"], REQ["Successful Registration"]], ["T4", "T5"])},
            {"component_id": "C3", "name": "Account Database", "type": "DATABASE", "description": "Stores customer accounts.",
             "responsibilities": ["Persist accounts", "Enforce unique email"], "technology": "PostgreSQL",
             **traced("ASSUMED", [REQ["Duplicate Email Handling"]], ["T2"], "PostgreSQL is the project's existing database; the SRS names none.")},
            {"component_id": "C4", "name": "Email Provider", "type": "EXTERNAL_SYSTEM", "description": "Delivers confirmation emails.",
             "responsibilities": ["Deliver the confirmation email"], "technology": None,
             **traced("EXPLICIT", [REQ["Confirmation Email"]])},
        ],
        "relationships": [
            {"relationship_id": "R1", "source_component_id": "C1", "target_component_id": "C2", "interaction": "HTTP",
             "description": "Submits registration requests", "data_exchanged": "email, password", "protocol": "HTTPS/JSON"},
            {"relationship_id": "R2", "source_component_id": "C2", "target_component_id": "C3", "interaction": "DATABASE",
             "description": "Reads and writes accounts", "data_exchanged": "account records", "protocol": "SQL"},
            {"relationship_id": "R3", "source_component_id": "C2", "target_component_id": "C4", "interaction": "HTTP",
             "description": "Requests the confirmation email", "data_exchanged": "recipient address", "protocol": "HTTPS"},
        ],
        "data_flows": [
            {"flow_id": "DF1", "name": "Register a customer", "description": "From form submission to confirmation.",
             "steps": [
                 {"order": 1, "source_component_id": "C1", "target_component_id": "C2", "description": "Submit email and password"},
                 {"order": 2, "source_component_id": "C2", "target_component_id": "C3", "description": "Check for an existing account and create one"},
                 {"order": 3, "source_component_id": "C2", "target_component_id": "C4", "description": "Request the confirmation email"},
             ], **traced("EXPLICIT", [REQ["Successful Registration"], REQ["Confirmation Email"]], ["T4"])},
        ],
        "integrations": [
            {"integration_id": "INT1", "name": "Email delivery", "purpose": "Send the confirmation email.",
             "component_id": "C2", "protocol": "HTTPS", **traced("EXPLICIT", [REQ["Confirmation Email"]])},
        ],
        "deployment": [
            {"node_id": "DN1", "name": "Customer browser", "kind": "CLIENT_DEVICE", "description": "Runs the registration page.",
             "technology": "Web browser", "component_ids": ["C1"],
             **traced("ASSUMED", rationale="A web client implies the customer's browser; the SRS does not say more.")},
            {"node_id": "DN2", "name": "API container", "kind": "CONTAINER", "description": "Runs the registration API.",
             "technology": "Docker", "component_ids": ["C2"],
             **traced("ASSUMED", rationale="The SRS does not describe hosting; one container keeps deployment simple.")},
            {"node_id": "DN3", "name": "Database server", "kind": "SERVER", "description": "Hosts the account database.",
             "technology": "PostgreSQL server", "component_ids": ["C3"],
             **traced("ASSUMED", rationale="PostgreSQL is the project's existing database; hosting is not specified.")},
        ],
        "decisions": [
            {"decision_id": "D1", "area": "Backend framework", "decision": "Use FastAPI.",
             "alternatives_considered": ["Django"], "tradeoffs": "Fast to build; fewer batteries than Django.",
             **traced("ASSUMED", rationale="Matches the existing project stack; the SRS names no framework.")},
        ],
        "quality_considerations": [
            {"consideration_id": "Q1", "category": "AUTHENTICATION_AUTHORIZATION", "title": "No sign-in in scope",
             "approach": "The SRS covers registration only; login and authorization are not specified.",
             **traced("UNKNOWN", rationale="Sign-in is not part of these requirements.")},
            {"consideration_id": "Q2", "category": "SCALABILITY", "title": "Stateless API",
             "approach": "Keep the API stateless so more instances can be added behind a load balancer.",
             **traced("INFERRED", [NFR["Performance"]], rationale="Supports the two-second target under load.")},
            {"consideration_id": "Q3", "category": "RELIABILITY", "title": "Honest email status",
             "approach": "Report an email failure instead of claiming delivery.",
             **traced("EXPLICIT", [NFR["Reliability"]])},
            {"consideration_id": "Q4", "category": "SECURITY", "title": "Hash passwords",
             "approach": "Store only salted password hashes.", **traced("EXPLICIT", [NFR["Security"]])},
            {"consideration_id": "Q5", "category": "DEPLOYMENT", "title": "Single deployable",
             "approach": "Deploy the API and client as two containers.",
             **traced("ASSUMED", rationale="The SRS does not describe deployment.")},
        ],
        "risks": [
            {"risk_id": "AR1", "title": "Email provider outage", "description": "Confirmation emails fail.",
             "impact": "MEDIUM", "likelihood": "MEDIUM", "mitigation": "Surface the failure and allow a resend.",
             "component_ids": ["C4"], "requirement_ids": [REQ["Confirmation Email"]]},
        ],
        "open_items": [
            {"item_id": "OH1", "kind": "ASSUMED", "statement": "PostgreSQL and FastAPI are used.",
             "impact": "Changing them affects the persistence and API layers.", "requirement_ids": []},
            {"item_id": "OH2", "kind": "UNKNOWN", "statement": "Sign-in behaviour is not specified.",
             "impact": "No authorization design is possible yet.", "requirement_ids": []},
        ],
    }


def registration_lld_dict(requirements: dict, plan: dict) -> dict:
    i = _ids(requirements)
    REQ, NFR = i["REQ"], i["NFR"]

    def traced(grounding, req=(), tasks=(), rationale=None):
        return {"grounding": grounding, "requirement_ids": list(req), "task_ids": list(tasks), "rationale": rationale}

    return {
        "modules": [
            {"module_id": "M1", "component_id": "C2", "name": "RegistrationController", "kind": "CONTROLLER",
             "description": "HTTP entry point for registration.", "responsibilities": ["Parse the request", "Return the result"],
             "methods": [{"name": "register", "signature": "register(request: RegisterRequest) -> RegisterResponse", "description": "Handle POST /register"}],
             "depends_on_module_ids": ["M2"], **traced("EXPLICIT", [REQ["Customer Registration"], REQ["Registration Response"]], ["T4"])},
            {"module_id": "M2", "component_id": "C2", "name": "RegistrationService", "kind": "SERVICE",
             "description": "Registration business logic.", "responsibilities": ["Validate input", "Reject duplicates", "Create accounts", "Send confirmation"],
             "methods": [{"name": "register", "signature": "register(email: str, password: str) -> Account", "description": "Create an account"}],
             "depends_on_module_ids": ["M3"],
             **traced("EXPLICIT", [REQ["Email Validation"], REQ["Password Requirement"], REQ["Duplicate Email Handling"], REQ["Successful Registration"], REQ["Confirmation Email"]], ["T4", "T5"])},
            {"module_id": "M3", "component_id": "C2", "name": "AccountRepository", "kind": "REPOSITORY",
             "description": "Account persistence.", "responsibilities": ["Find an account by email", "Insert an account"],
             "methods": [], "depends_on_module_ids": [], **traced("INFERRED", [REQ["Duplicate Email Handling"]], ["T2"], "Needed to look up existing emails.")},
        ],
        "interfaces": [
            {"interface_id": "I1", "name": "AccountStore", "description": "Account persistence contract.",
             "methods": [{"name": "find_by_email", "signature": "find_by_email(email: str) -> Account | None", "description": "Look up an account"}],
             "implemented_by_module_ids": ["M3"]},
        ],
        "data_models": [
            {"data_model_id": "DM1", "name": "RegisterRequest", "kind": "REQUEST", "description": "Registration input.",
             "fields": [
                 {"name": "email", "type": "string", "required": True, "description": None, "validation": "valid email format"},
                 {"name": "password", "type": "string", "required": True, "description": None, "validation": "non-empty"},
             ], **traced("EXPLICIT", [REQ["Email Validation"], REQ["Password Requirement"]])},
            {"data_model_id": "DM2", "name": "RegisterResponse", "kind": "RESPONSE", "description": "Registration result.",
             "fields": [{"name": "success", "type": "boolean", "required": True, "description": None, "validation": None}],
             **traced("EXPLICIT", [REQ["Registration Response"]])},
        ],
        "apis": [
            {"api_id": "API1", "component_id": "C2", "module_id": "M1", "method": "POST", "path": "/api/register",
             "summary": "Register a customer", "auth_required": False, "request_model_id": "DM1", "response_model_id": "DM2",
             "errors": [{"status_code": 409, "condition": "Email already registered"}, {"status_code": 422, "condition": "Invalid email or missing password"}],
             "validation_rules": ["email must be valid", "password is required"],
             **traced("EXPLICIT", [REQ["Customer Registration"], REQ["Duplicate Email Handling"]], ["T4"])},
        ],
        "tables": [
            {"table_id": "TBL1", "name": "customer_accounts", "description": "Registered customers.",
             "columns": [
                 {"name": "id", "type": "integer", "primary_key": True, "nullable": False, "unique": True, "description": None},
                 {"name": "email", "type": "varchar(320)", "primary_key": False, "nullable": False, "unique": True, "description": "case-insensitive unique"},
                 {"name": "password_hash", "type": "varchar(255)", "primary_key": False, "nullable": False, "unique": False, "description": None},
             ], "indexes": ["unique index on lower(email)"],
             **traced("EXPLICIT", [REQ["Duplicate Email Handling"], REQ["Successful Registration"], NFR["Security"]], ["T2"])},
        ],
        "table_relationships": [],
        "business_rules": [
            {"rule_id": "BR1", "title": "Reject duplicate email", "description": "An already registered email cannot register again.",
             "module_id": "M2", "pseudocode": "if repo.find_by_email(email): raise Conflict",
             **traced("EXPLICIT", [REQ["Duplicate Email Handling"]], ["T2"])},
        ],
        "sequence_flows": [
            {"sequence_id": "SEQ1", "name": "Successful registration", "description": "Happy path.",
             "participants": [
                 {"participant_id": "P1", "label": "Customer", "ref_id": None},
                 {"participant_id": "P2", "label": "RegistrationController", "ref_id": "M1"},
                 {"participant_id": "P3", "label": "RegistrationService", "ref_id": "M2"},
             ],
             "steps": [
                 {"order": 1, "source_participant_id": "P1", "target_participant_id": "P2", "message": "POST /api/register", "api_id": "API1"},
                 {"order": 2, "source_participant_id": "P2", "target_participant_id": "P3", "message": "register(email, password)", "api_id": None},
                 {"order": 3, "source_participant_id": "P3", "target_participant_id": "P2", "message": "account created", "api_id": None},
             ], **traced("EXPLICIT", [REQ["Successful Registration"], REQ["Confirmation Email"]], ["T4"])},
        ],
        "design_patterns": [
            {"pattern_id": "DP1", "name": "Repository", "applied_to_module_ids": ["M3"], "rationale": "Isolates persistence.", "grounding": "INFERRED"},
        ],
        "error_handling": [
            {"rule_id": "ER1", "title": "Map domain errors to HTTP", "approach": "Duplicate email -> 409; validation failure -> 422.",
             "api_ids": ["API1"], "status_code": None},
        ],
        "validation_rules": [
            {"rule_id": "VR1", "data_model_id": "DM1", "field_name": "email", "rule": "Must be a syntactically valid email address.",
             "requirement_ids": [REQ["Email Validation"]]},
        ],
        "open_items": [
            {"item_id": "OL1", "kind": "UNKNOWN", "statement": "Password complexity policy is not specified.",
             "impact": "Validation rules for passwords cannot be finalised.", "requirement_ids": []},
        ],
    }


def registration_hld(requirements: dict, plan: dict) -> HighLevelDesign:
    return HighLevelDesign.model_validate(registration_hld_dict(requirements, plan))


def registration_lld(requirements: dict, plan: dict, hld: dict | None = None) -> LowLevelDesign:
    return LowLevelDesign.model_validate(registration_lld_dict(requirements, plan))


def mutated(builder, mutate):
    """Return a builder that applies ``mutate(dict)`` to the good design."""

    def build(*args, **kwargs):
        data = copy.deepcopy(builder(*args, **kwargs).model_dump())
        mutate(data)
        return type(builder(*args, **kwargs)).model_validate(data)

    return build


class ScriptedArchitectProvider(ScriptedProvider):
    """Deterministic stand-in for Gemini's design calls.

    ``hld`` / ``lld`` are lists of responses: a design model, an ``Exception`` to raise, or a
    callable ``(requirements, plan) -> design``. The last response repeats once the list is
    used up, so a single bad design is returned on every repair attempt.
    """

    def __init__(self, hld=None, lld=None):
        super().__init__()
        self.hld_responses = list(hld or [])
        self.lld_responses = list(lld or [])
        self.hld_calls: list[dict] = []
        self.lld_calls: list[dict] = []

    @staticmethod
    def _next(responses, calls, call):
        calls.append(call)
        item = responses[min(len(calls), len(responses)) - 1]
        if isinstance(item, Exception):
            raise item
        return item(call["requirements"], call["plan"]) if callable(item) else item

    def generate_hld(self, project_name, project_description, requirements, plan, preferred_stack, feedback=None):
        call = {"requirements": requirements, "plan": plan, "feedback": feedback}
        return self._next(self.hld_responses, self.hld_calls, call)

    def generate_lld(self, project_name, project_description, requirements, plan, hld, preferred_stack, feedback=None):
        call = {"requirements": requirements, "plan": plan, "hld": hld, "feedback": feedback}
        return self._next(self.lld_responses, self.lld_calls, call)
