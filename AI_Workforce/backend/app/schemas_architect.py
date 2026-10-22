"""Schemas for the System Architect AI.

Two groups live here:

* ``HighLevelDesign`` / ``LowLevelDesign`` and their parts: the contract the LLM must
  satisfy. The Architect is asked for the HLD first and the LLD second (the LLD is
  built on the validated HLD), so each call stays small enough for the model.
* ``Architecture*Response`` models: what the API returns, including the two structures
  the backend *derives* from the validated design (the architecture diagram and the
  requirement traceability matrix). Neither is written by the LLM.

As in ``schemas_pm`` the rules (non-empty text, ranges, references) are enforced by
validators and ``architect_validation`` instead of ``Field(ge=..., min_length=...)``, so
the JSON schema sent to Gemini stays simple.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .schemas import AgentRunResponse

ARCHITECT_AGENT_NAME = "System Architect AI"

Grounding = Literal["EXPLICIT", "INFERRED", "ASSUMED", "UNKNOWN"]
Level = Literal["HIGH", "MEDIUM", "LOW"]
ComponentType = Literal[
    "FRONTEND", "API", "SERVICE", "DATABASE", "STORAGE", "CACHE", "QUEUE",
    "GATEWAY", "AI_SERVICE", "EXTERNAL_SYSTEM", "OTHER",
]
Interaction = Literal["HTTP", "MESSAGE", "DATABASE", "FUNCTION_CALL", "EVENT", "FILE", "OTHER"]
DeploymentKind = Literal["CLIENT_DEVICE", "SERVER", "CONTAINER", "MANAGED_SERVICE", "CLOUD_SERVICE", "OTHER"]
QualityCategory = Literal[
    "AUTHENTICATION_AUTHORIZATION", "SCALABILITY", "RELIABILITY", "SECURITY",
    "DEPLOYMENT", "PERFORMANCE", "OBSERVABILITY", "OTHER",
]
ModuleKind = Literal[
    "CONTROLLER", "SERVICE", "REPOSITORY", "MODEL", "MIDDLEWARE",
    "CLIENT", "UI_COMPONENT", "UTILITY", "OTHER",
]
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
ModelKind = Literal["REQUEST", "RESPONSE", "DTO"]
Cardinality = Literal["ONE_TO_ONE", "ONE_TO_MANY", "MANY_TO_MANY"]
OpenItemKind = Literal["ASSUMED", "UNKNOWN"]

# Quality categories every HLD must address (an entry may state that the requirements
# do not specify the topic, classified UNKNOWN, but the topic may not be skipped).
REQUIRED_QUALITY_CATEGORIES = (
    "AUTHENTICATION_AUTHORIZATION", "SCALABILITY", "RELIABILITY", "SECURITY", "DEPLOYMENT",
)


def _required_text(value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError("must not be empty")
    return value


class Traced(BaseModel):
    """Grounding and traceability shared by every design element that makes a claim."""

    grounding: Grounding
    requirement_ids: list[str] = Field(default_factory=list)  # Requirements Analyst ids only
    task_ids: list[str] = Field(default_factory=list)         # Project Manager task ids only
    rationale: str | None = None


# ---------------------------------------------------------------------------
# High-level design
# ---------------------------------------------------------------------------


class ArchStyle(Traced):
    name: str
    description: str

    clean_text = field_validator("name", "description")(_required_text)


class ArchComponent(Traced):
    component_id: str
    name: str
    type: ComponentType
    description: str
    responsibilities: list[str] = Field(default_factory=list)
    technology: str | None = None

    clean_text = field_validator("component_id", "name", "description")(_required_text)


class ArchActor(Traced):
    """A person or outside system that uses the system (drawn in the system context diagram)."""

    actor_id: str
    name: str
    description: str
    interaction: str | None = None  # short phrase: how the actor uses the system
    component_ids: list[str] = Field(default_factory=list)  # components the actor interacts with directly

    clean_text = field_validator("actor_id", "name", "description")(_required_text)


class ArchDeploymentNode(Traced):
    """A place components run (device, server, container, managed service); drawn in the deployment diagram."""

    node_id: str
    name: str
    kind: DeploymentKind
    description: str
    technology: str | None = None
    component_ids: list[str] = Field(default_factory=list)  # components that run here

    clean_text = field_validator("node_id", "name", "description")(_required_text)


class ArchRelationship(BaseModel):
    relationship_id: str
    source_component_id: str
    target_component_id: str
    interaction: Interaction
    description: str
    data_exchanged: str | None = None
    protocol: str | None = None  # e.g. "REST over HTTPS", "SQL"; only when the design supports it

    clean_text = field_validator("relationship_id", "source_component_id", "target_component_id", "description")(
        _required_text
    )


class ArchDataFlowStep(BaseModel):
    order: int
    source_component_id: str
    target_component_id: str
    description: str

    clean_text = field_validator("source_component_id", "target_component_id", "description")(_required_text)


class ArchDataFlow(Traced):
    flow_id: str
    name: str
    description: str
    steps: list[ArchDataFlowStep] = Field(default_factory=list)

    clean_text = field_validator("flow_id", "name", "description")(_required_text)


class ArchIntegration(Traced):
    integration_id: str
    name: str
    purpose: str
    component_id: str | None = None   # the component that talks to the external system
    protocol: str | None = None

    clean_text = field_validator("integration_id", "name", "purpose")(_required_text)


class ArchDecision(Traced):
    decision_id: str
    area: str
    decision: str
    alternatives_considered: list[str] = Field(default_factory=list)
    tradeoffs: str

    clean_text = field_validator("decision_id", "area", "decision", "tradeoffs")(_required_text)


class ArchQuality(Traced):
    consideration_id: str
    category: QualityCategory
    title: str
    approach: str

    clean_text = field_validator("consideration_id", "title", "approach")(_required_text)


class ArchRisk(BaseModel):
    risk_id: str
    title: str
    description: str
    impact: Level
    likelihood: Level
    mitigation: str
    component_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)

    clean_text = field_validator("risk_id", "title", "description", "mitigation")(_required_text)


class ArchOpenItem(BaseModel):
    """An assumption the design depends on, or something the requirements leave unknown."""

    item_id: str
    kind: OpenItemKind
    statement: str
    impact: str
    requirement_ids: list[str] = Field(default_factory=list)

    clean_text = field_validator("item_id", "statement", "impact")(_required_text)


class HighLevelDesign(BaseModel):
    overview: str
    style: ArchStyle
    system_architecture: str
    actors: list[ArchActor] = Field(default_factory=list)
    components: list[ArchComponent] = Field(default_factory=list)
    relationships: list[ArchRelationship] = Field(default_factory=list)
    data_flows: list[ArchDataFlow] = Field(default_factory=list)
    integrations: list[ArchIntegration] = Field(default_factory=list)
    deployment: list[ArchDeploymentNode] = Field(default_factory=list)
    decisions: list[ArchDecision] = Field(default_factory=list)
    quality_considerations: list[ArchQuality] = Field(default_factory=list)
    risks: list[ArchRisk] = Field(default_factory=list)
    open_items: list[ArchOpenItem] = Field(default_factory=list)

    clean_text = field_validator("overview", "system_architecture")(_required_text)


# ---------------------------------------------------------------------------
# Low-level design
# ---------------------------------------------------------------------------


class LldMethod(BaseModel):
    name: str
    signature: str
    description: str

    clean_text = field_validator("name", "signature", "description")(_required_text)


class LldModule(Traced):
    module_id: str
    component_id: str
    name: str
    kind: ModuleKind
    description: str
    responsibilities: list[str] = Field(default_factory=list)
    methods: list[LldMethod] = Field(default_factory=list)
    depends_on_module_ids: list[str] = Field(default_factory=list)

    clean_text = field_validator("module_id", "component_id", "name", "description")(_required_text)


class LldInterface(BaseModel):
    interface_id: str
    name: str
    description: str
    methods: list[LldMethod] = Field(default_factory=list)
    implemented_by_module_ids: list[str] = Field(default_factory=list)

    clean_text = field_validator("interface_id", "name", "description")(_required_text)


class LldField(BaseModel):
    name: str
    type: str
    required: bool
    description: str | None = None
    validation: str | None = None

    clean_text = field_validator("name", "type")(_required_text)


class LldDataModel(Traced):
    data_model_id: str
    name: str
    kind: ModelKind
    description: str
    fields: list[LldField] = Field(default_factory=list)

    clean_text = field_validator("data_model_id", "name", "description")(_required_text)


class LldApiError(BaseModel):
    status_code: int
    condition: str

    clean_text = field_validator("condition")(_required_text)


class LldApi(Traced):
    api_id: str
    component_id: str
    module_id: str | None = None      # the controller that implements the endpoint
    method: HttpMethod
    path: str
    summary: str
    auth_required: bool
    request_model_id: str | None = None
    response_model_id: str | None = None
    errors: list[LldApiError] = Field(default_factory=list)
    validation_rules: list[str] = Field(default_factory=list)

    clean_text = field_validator("api_id", "component_id", "path", "summary")(_required_text)


class LldColumn(BaseModel):
    name: str
    type: str
    primary_key: bool
    nullable: bool
    unique: bool
    description: str | None = None

    clean_text = field_validator("name", "type")(_required_text)


class LldTable(Traced):
    table_id: str
    name: str
    description: str
    columns: list[LldColumn] = Field(default_factory=list)
    indexes: list[str] = Field(default_factory=list)

    clean_text = field_validator("table_id", "name", "description")(_required_text)


class LldTableRelationship(BaseModel):
    relationship_id: str
    source_table_id: str
    source_column: str
    target_table_id: str
    target_column: str
    cardinality: Cardinality
    description: str | None = None

    clean_text = field_validator(
        "relationship_id", "source_table_id", "source_column", "target_table_id", "target_column"
    )(_required_text)


class LldBusinessRule(Traced):
    rule_id: str
    title: str
    description: str
    module_id: str | None = None
    pseudocode: str | None = None

    clean_text = field_validator("rule_id", "title", "description")(_required_text)


class LldSeqParticipant(BaseModel):
    participant_id: str
    label: str
    ref_id: str | None = None   # a component_id or module_id; None for actors such as the end user

    clean_text = field_validator("participant_id", "label")(_required_text)


class LldSeqStep(BaseModel):
    order: int
    source_participant_id: str
    target_participant_id: str
    message: str
    api_id: str | None = None

    clean_text = field_validator("source_participant_id", "target_participant_id", "message")(_required_text)


class LldSequenceFlow(Traced):
    sequence_id: str
    name: str
    description: str
    participants: list[LldSeqParticipant] = Field(default_factory=list)
    steps: list[LldSeqStep] = Field(default_factory=list)

    clean_text = field_validator("sequence_id", "name", "description")(_required_text)


class LldPattern(BaseModel):
    pattern_id: str
    name: str
    applied_to_module_ids: list[str] = Field(default_factory=list)
    rationale: str
    grounding: Grounding

    clean_text = field_validator("pattern_id", "name", "rationale")(_required_text)


class LldErrorRule(BaseModel):
    rule_id: str
    title: str
    approach: str
    api_ids: list[str] = Field(default_factory=list)
    status_code: int | None = None

    clean_text = field_validator("rule_id", "title", "approach")(_required_text)


class LldValidationRule(BaseModel):
    rule_id: str
    data_model_id: str | None = None
    field_name: str | None = None
    rule: str
    requirement_ids: list[str] = Field(default_factory=list)

    clean_text = field_validator("rule_id", "rule")(_required_text)


class LowLevelDesign(BaseModel):
    modules: list[LldModule] = Field(default_factory=list)
    interfaces: list[LldInterface] = Field(default_factory=list)
    apis: list[LldApi] = Field(default_factory=list)
    data_models: list[LldDataModel] = Field(default_factory=list)
    tables: list[LldTable] = Field(default_factory=list)
    table_relationships: list[LldTableRelationship] = Field(default_factory=list)
    business_rules: list[LldBusinessRule] = Field(default_factory=list)
    sequence_flows: list[LldSequenceFlow] = Field(default_factory=list)
    design_patterns: list[LldPattern] = Field(default_factory=list)
    error_handling: list[LldErrorRule] = Field(default_factory=list)
    validation_rules: list[LldValidationRule] = Field(default_factory=list)
    open_items: list[ArchOpenItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API responses
# ---------------------------------------------------------------------------


class DiagramNode(BaseModel):
    id: str
    label: str
    type: str
    layer: int
    grounding: str


class DiagramEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    interaction: str


class ArchitectureDiagram(BaseModel):
    """Built from the validated components and relationships, never written by the LLM."""

    nodes: list[DiagramNode] = Field(default_factory=list)
    edges: list[DiagramEdge] = Field(default_factory=list)
    mermaid: str = ""
    # Components with their modules, endpoints and tables (see build_detailed_diagram). Computed
    # when the architecture is served, so designs saved earlier get it without regenerating.
    detailed: dict[str, Any] | None = None


class TraceabilityEntry(BaseModel):
    """One Requirements Analyst artifact and every design element that cites it."""

    requirement_id: str
    title: str | None = None
    kind: str
    status: Literal["COVERED", "NOT_COVERED"]
    component_ids: list[str] = Field(default_factory=list)
    module_ids: list[str] = Field(default_factory=list)
    api_ids: list[str] = Field(default_factory=list)
    table_ids: list[str] = Field(default_factory=list)
    sequence_ids: list[str] = Field(default_factory=list)
    other_element_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)


class ArchitectureInfo(BaseModel):
    id: int
    overview: str
    warnings: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    created_at: datetime | None = None
    requirements_changed: bool = False
    plan_changed: bool = False


class ArchitectureResponse(BaseModel):
    """Everything the frontend needs in one call.

    ``status`` reflects the most recent Architect run. If a regeneration failed, the
    previous valid design is still returned and ``status`` is FAILED.
    """

    status: Literal["NOT_GENERATED", "PROCESSING", "COMPLETED", "FAILED"]
    architecture: ArchitectureInfo | None = None
    hld: HighLevelDesign | None = None
    lld: LowLevelDesign | None = None
    diagram: ArchitectureDiagram | None = None
    traceability: list[TraceabilityEntry] = Field(default_factory=list)
    open_items: list[ArchOpenItem] = Field(default_factory=list)
    latest_agent_run: AgentRunResponse | None = None
