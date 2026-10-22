"""Validation of the Architect's design (the "Validate Architecture" step).

Pydantic already guarantees shape, types and the allowed grounding values. This module
checks *meaning*:

* required HLD/LLD content is present
* identifiers are unique
* every relationship, API, table and sequence reference points at something that exists
* every requirement and task id exists in the Requirements Analyst / Project Manager output
* grounding classifications are used honestly (EXPLICIT cites a requirement, INFERRED and
  ASSUMED explain themselves)
* the design is consistent with itself (an API's controller belongs to the API's component, ...)

Errors block persistence. Coverage gaps (a functional or non-functional requirement that no
design element addresses) trigger one repair attempt and are then recorded as warnings,
exactly as the Project Manager treats coverage. Nothing here invents design content; the
only derived values are the architecture diagram and the traceability matrix, both built
from the already-validated design.

Everything here is a pure function of the design and the id sets, so the workflow's
``validate_architecture`` gate can run the same checks without touching the database.
"""

from dataclasses import dataclass, field

from ..schemas_architect import (
    REQUIRED_QUALITY_CATEGORIES,
    HighLevelDesign,
    LowLevelDesign,
)

KIND_BY_PREFIX = {
    "REQ": "Functional requirement",
    "US": "User story",
    "AC": "Acceptance criterion",
    "NFR": "Non-functional requirement",
    "CON": "Constraint",
    "DEP": "Dependency",
    "AMB": "Ambiguity",
    "RISK": "Risk",
}
_LAYER_BY_TYPE = {
    "FRONTEND": 0, "GATEWAY": 0,
    "API": 1, "SERVICE": 1, "AI_SERVICE": 1, "OTHER": 1,
    "QUEUE": 2, "CACHE": 2,
    "DATABASE": 3, "STORAGE": 3,
    "EXTERNAL_SYSTEM": 4,
}
_MAX_LISTED = 10


@dataclass(frozen=True)
class ReferenceIds:
    """The ids a design is allowed to cite. Built from real Requirements Analyst / PM output."""

    requirement_ids: frozenset[str]
    task_ids: frozenset[str]
    titles: dict[str, str] = field(default_factory=dict)

    @classmethod
    def build(cls, requirement_ids, task_ids, titles=None) -> "ReferenceIds":
        return cls(frozenset(requirement_ids), frozenset(task_ids), dict(titles or {}))

    def with_prefix(self, *prefixes: str) -> frozenset[str]:
        return frozenset(i for i in self.requirement_ids if i.split("-", 1)[0] in prefixes)

    @property
    def functional_ids(self) -> frozenset[str]:
        return self.with_prefix("REQ")

    @property
    def nfr_ids(self) -> frozenset[str]:
        return self.with_prefix("NFR")

    @property
    def constraint_ids(self) -> frozenset[str]:
        return self.with_prefix("CON")

    def to_dict(self) -> dict:
        return {"requirement_ids": sorted(self.requirement_ids), "task_ids": sorted(self.task_ids)}

    @classmethod
    def from_dict(cls, data: dict) -> "ReferenceIds":
        return cls.build(data.get("requirement_ids") or [], data.get("task_ids") or [])


@dataclass
class ArchIssues:
    errors: list[str] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def needs_repair(self) -> bool:
        return bool(self.errors or self.coverage_gaps)

    def feedback(self) -> list[str]:
        return [*self.errors, *self.coverage_gaps]


# ---------------------------------------------------------------------------
# Normalisation (harmless clean-up only)
# ---------------------------------------------------------------------------


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values or []:
        value = (value or "").strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def normalize_design(hld: HighLevelDesign, lld: LowLevelDesign | None = None):
    """Trim and de-duplicate. Never adds, renames or drops design content that has meaning."""
    hld = hld.model_copy(deep=True)
    lld = lld.model_copy(deep=True) if lld is not None else None
    warnings: list[str] = []

    def clean_ids(items):
        for item in items:
            if hasattr(item, "requirement_ids"):
                item.requirement_ids = _dedupe(item.requirement_ids)
            if hasattr(item, "task_ids"):
                item.task_ids = _dedupe(item.task_ids)

    clean_ids([hld.style, *hld.actors, *hld.components, *hld.data_flows, *hld.integrations, *hld.deployment,
               *hld.decisions, *hld.quality_considerations, *hld.risks, *hld.open_items])
    for item in [*hld.actors, *hld.deployment]:
        item.component_ids = _dedupe(item.component_ids)

    seen: set[tuple] = set()
    unique = []
    for relationship in hld.relationships:
        key = (relationship.source_component_id, relationship.target_component_id, relationship.interaction)
        if key in seen:
            continue
        seen.add(key)
        unique.append(relationship)
    if len(unique) != len(hld.relationships):
        warnings.append(f"Removed {len(hld.relationships) - len(unique)} duplicate component relationship(s).")
    hld.relationships = unique

    for flow in hld.data_flows:
        flow.steps = sorted(flow.steps, key=lambda step: step.order)

    if lld is not None:
        clean_ids([*lld.modules, *lld.data_models, *lld.apis, *lld.tables, *lld.business_rules,
                   *lld.sequence_flows, *lld.validation_rules, *lld.open_items])
        for module in lld.modules:
            module.depends_on_module_ids = _dedupe(module.depends_on_module_ids)
        for flow in lld.sequence_flows:
            flow.steps = sorted(flow.steps, key=lambda step: step.order)
    return hld, lld, warnings


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _valid(kind: str, ids) -> str:
    """Tail for a repair message: the ids that ARE defined, so the model can pick one or define it."""
    listed = ", ".join(sorted(ids)) or "none are defined"
    return f" Defined {kind}: {listed}."


def _unique(items, attr: str, label: str, errors: list[str]) -> set[str]:
    seen: set[str] = set()
    for item in items:
        value = getattr(item, attr)
        if value in seen:
            errors.append(f"Duplicate {label} id '{value}'.")
        seen.add(value)
    return seen


def _check_traced(label: str, item, refs: ReferenceIds, errors: list[str]) -> None:
    for requirement_id in item.requirement_ids:
        if requirement_id not in refs.requirement_ids:
            errors.append(f"{label} cites unknown requirement id '{requirement_id}'.")
    for task_id in getattr(item, "task_ids", []):
        if task_id not in refs.task_ids:
            errors.append(f"{label} cites unknown task id '{task_id}'.")
    grounding = getattr(item, "grounding", None)
    if grounding == "EXPLICIT" and not item.requirement_ids:
        errors.append(f"{label} is classified EXPLICIT but cites no requirement; cite one or reclassify it.")
    if grounding in ("INFERRED", "ASSUMED") and not (getattr(item, "rationale", None) or "").strip():
        errors.append(f"{label} is classified {grounding} but gives no rationale.")


def validate_hld(hld: HighLevelDesign, refs: ReferenceIds) -> ArchIssues:
    issues = ArchIssues()
    errors, warnings = issues.errors, issues.warnings

    _check_traced("The architecture style", hld.style, refs, errors)

    if not hld.components:
        errors.append("The HLD defines no components.")
    component_ids = _unique(hld.components, "component_id", "component", errors)
    for component in hld.components:
        _check_traced(f"Component {component.component_id}", component, refs, errors)
        if not [r for r in component.responsibilities if r and r.strip()]:
            errors.append(f"Component {component.component_id} lists no responsibilities.")

    _unique(hld.relationships, "relationship_id", "relationship", errors)
    connected: set[str] = set()
    for relationship in hld.relationships:
        label = f"Relationship {relationship.relationship_id}"
        for role, value in (("source", relationship.source_component_id), ("target", relationship.target_component_id)):
            if value not in component_ids:
                errors.append(f"{label} has unknown {role} component '{value}'.")
        if relationship.source_component_id == relationship.target_component_id:
            errors.append(f"{label} connects component '{relationship.source_component_id}' to itself.")
        connected.update((relationship.source_component_id, relationship.target_component_id))
    if len(hld.components) > 1:
        if not hld.relationships:
            errors.append("The HLD has several components but no relationships between them.")
        else:
            isolated = [c.component_id for c in hld.components if c.component_id not in connected]
            if isolated:
                warnings.append(f"Components with no relationships: {', '.join(isolated)}.")

    actor_ids = _unique(hld.actors, "actor_id", "actor", errors)
    for actor in hld.actors:
        label = f"Actor {actor.actor_id}"
        _check_traced(label, actor, refs, errors)
        if not actor.component_ids:
            errors.append(f"{label} interacts with no component.")
        for component_id in actor.component_ids:
            if component_id not in component_ids:
                errors.append(f"{label} references unknown component '{component_id}'." + _valid("component ids", component_ids))
    if not hld.actors:
        issues.coverage_gaps.append(
            "The HLD names no actors (the people or outside systems that use the system); add them in `actors`."
        )

    node_ids = _unique(hld.deployment, "node_id", "deployment node", errors)
    hosted: dict[str, list[str]] = {}
    for node in hld.deployment:
        label = f"Deployment node {node.node_id}"
        _check_traced(label, node, refs, errors)
        if not node.component_ids:
            errors.append(f"{label} hosts no component.")
        for component_id in node.component_ids:
            if component_id not in component_ids:
                errors.append(f"{label} hosts unknown component '{component_id}'." + _valid("component ids", component_ids))
            hosted.setdefault(component_id, []).append(node.node_id)
    for component_id, nodes in sorted(hosted.items()):
        if len(nodes) > 1:
            errors.append(f"Component {component_id} is placed on several deployment nodes ({', '.join(nodes)}); use one.")
    if not hld.deployment:
        issues.coverage_gaps.append("The HLD has no deployment nodes; describe where the components run in `deployment`.")
    else:
        unplaced = [
            c.component_id for c in hld.components if c.type != "EXTERNAL_SYSTEM" and c.component_id not in hosted
        ]
        if unplaced:
            issues.coverage_gaps.append(
                f"Components not placed on any deployment node: {', '.join(unplaced)}."
            )
    for clash in sorted((actor_ids | node_ids) & component_ids):
        errors.append(f"Id '{clash}' is used for more than one kind of HLD element.")
    for clash in sorted(actor_ids & node_ids):
        errors.append(f"Id '{clash}' is used for both an actor and a deployment node.")

    if not hld.data_flows:
        errors.append("The HLD defines no data flows.")
    _unique(hld.data_flows, "flow_id", "data flow", errors)
    for flow in hld.data_flows:
        label = f"Data flow {flow.flow_id}"
        _check_traced(label, flow, refs, errors)
        if not flow.steps:
            errors.append(f"{label} has no steps.")
        if len({step.order for step in flow.steps}) != len(flow.steps):
            errors.append(f"{label} repeats a step order number.")
        for step in flow.steps:
            for value in (step.source_component_id, step.target_component_id):
                if value not in component_ids:
                    errors.append(f"{label} step {step.order} references unknown component '{value}'.")

    _unique(hld.integrations, "integration_id", "integration", errors)
    for integration in hld.integrations:
        label = f"Integration {integration.integration_id}"
        _check_traced(label, integration, refs, errors)
        if integration.component_id is not None and integration.component_id not in component_ids:
            errors.append(f"{label} references unknown component '{integration.component_id}'.")

    if not hld.decisions:
        errors.append("The HLD records no technology or architecture decisions.")
    _unique(hld.decisions, "decision_id", "decision", errors)
    for decision in hld.decisions:
        _check_traced(f"Decision {decision.decision_id}", decision, refs, errors)

    _unique(hld.quality_considerations, "consideration_id", "quality consideration", errors)
    for item in hld.quality_considerations:
        _check_traced(f"Quality consideration {item.consideration_id}", item, refs, errors)
    present = {item.category for item in hld.quality_considerations}
    for category in REQUIRED_QUALITY_CATEGORIES:
        if category not in present:
            errors.append(f"The HLD does not address {category.replace('_', ' ').lower()}.")

    _unique(hld.risks, "risk_id", "architecture risk", errors)
    for risk in hld.risks:
        label = f"Architecture risk {risk.risk_id}"
        for component_id in risk.component_ids:
            if component_id not in component_ids:
                errors.append(f"{label} references unknown component '{component_id}'.")
        for requirement_id in risk.requirement_ids:
            if requirement_id not in refs.requirement_ids:
                errors.append(f"{label} cites unknown requirement id '{requirement_id}'.")
    if not hld.risks:
        warnings.append("The HLD lists no architecture risks.")

    _unique(hld.open_items, "item_id", "open item", errors)
    for item in hld.open_items:
        for requirement_id in item.requirement_ids:
            if requirement_id not in refs.requirement_ids:
                errors.append(f"Open item {item.item_id} cites unknown requirement id '{requirement_id}'.")
    return issues


def validate_lld(lld: LowLevelDesign, hld: HighLevelDesign, refs: ReferenceIds) -> ArchIssues:
    issues = ArchIssues()
    errors, warnings = issues.errors, issues.warnings
    component_ids = {c.component_id for c in hld.components}

    if not lld.modules:
        errors.append("The LLD defines no modules.")
    module_ids = _unique(lld.modules, "module_id", "module", errors)
    for clash in sorted(module_ids & component_ids):
        errors.append(f"Id '{clash}' is used for both a component and a module.")
    module_component = {m.module_id: m.component_id for m in lld.modules}
    names_seen: set[tuple] = set()
    for module in lld.modules:
        label = f"Module {module.module_id}"
        _check_traced(label, module, refs, errors)
        if module.component_id not in component_ids:
            errors.append(f"{label} belongs to unknown component '{module.component_id}'." + _valid("component ids", component_ids))
        for dependency in module.depends_on_module_ids:
            if dependency not in module_ids:
                errors.append(f"{label} depends on unknown module '{dependency}'." + _valid("module ids", module_ids))
            elif dependency == module.module_id:
                errors.append(f"{label} depends on itself.")
        if not [r for r in module.responsibilities if r and r.strip()]:
            errors.append(f"{label} lists no responsibilities.")
        key = (module.component_id, module.name.strip().lower())
        if key in names_seen:
            errors.append(f"Component {module.component_id} has two modules named '{module.name}'.")
        names_seen.add(key)

    _unique(lld.interfaces, "interface_id", "interface", errors)
    for interface in lld.interfaces:
        for module_id in interface.implemented_by_module_ids:
            if module_id not in module_ids:
                errors.append(f"Interface {interface.interface_id} is implemented by unknown module '{module_id}'." + _valid("module ids", module_ids))

    model_ids = _unique(lld.data_models, "data_model_id", "data model", errors)
    model_fields: dict[str, set[str]] = {}
    for model in lld.data_models:
        label = f"Data model {model.data_model_id}"
        _check_traced(label, model, refs, errors)
        if not model.fields:
            errors.append(f"{label} has no fields.")
        names = [f.name for f in model.fields]
        if len(set(names)) != len(names):
            errors.append(f"{label} repeats a field name.")
        model_fields[model.data_model_id] = set(names)

    api_ids = _unique(lld.apis, "api_id", "API", errors)
    routes: set[tuple] = set()
    for api in lld.apis:
        label = f"API {api.api_id}"
        _check_traced(label, api, refs, errors)
        if api.component_id not in component_ids:
            errors.append(f"{label} belongs to unknown component '{api.component_id}'." + _valid("component ids", component_ids))
        if api.module_id is not None:
            if api.module_id not in module_ids:
                errors.append(f"{label} is implemented by unknown module '{api.module_id}'." + _valid("module ids", module_ids))
            elif api.component_id in component_ids and module_component[api.module_id] != api.component_id:
                errors.append(
                    f"{label} belongs to component '{api.component_id}' but its module "
                    f"'{api.module_id}' belongs to '{module_component[api.module_id]}'."
                )
        if not api.path.startswith("/"):
            errors.append(f"{label} path '{api.path}' must start with '/'.")
        route = (api.method, api.path)
        if route in routes:
            errors.append(f"{label} duplicates the route {api.method} {api.path}.")
        routes.add(route)
        for role, value in (("request", api.request_model_id), ("response", api.response_model_id)):
            if value is not None and value not in model_ids:
                errors.append(
                    f"{label} references unknown {role} model '{value}'. Define it in data_models with an id "
                    f"like DM1 and reference that id, use an existing model, or use null."
                    + _valid("data model ids", model_ids)
                )
        for error in api.errors:
            if not 100 <= error.status_code <= 599:
                errors.append(f"{label} has an invalid HTTP status code {error.status_code}.")
        if api.method in ("POST", "PUT", "PATCH") and api.request_model_id is None:
            warnings.append(f"{label} ({api.method} {api.path}) has no request model.")
    if not lld.apis:
        warnings.append("The LLD defines no API endpoints.")

    table_ids = _unique(lld.tables, "table_id", "table", errors)
    table_names = [t.name.strip().lower() for t in lld.tables]
    if len(set(table_names)) != len(table_names):
        errors.append("Two tables share the same name.")
    table_columns: dict[str, set[str]] = {}
    for table in lld.tables:
        label = f"Table {table.table_id}"
        _check_traced(label, table, refs, errors)
        columns = [c.name for c in table.columns]
        if not columns:
            errors.append(f"{label} has no columns.")
        if len(set(columns)) != len(columns):
            errors.append(f"{label} repeats a column name.")
        if columns and not any(c.primary_key for c in table.columns):
            errors.append(f"{label} has no primary key column.")
        table_columns[table.table_id] = set(columns)
    if not lld.tables:
        warnings.append("The LLD defines no database tables.")

    _unique(lld.table_relationships, "relationship_id", "table relationship", errors)
    for relationship in lld.table_relationships:
        label = f"Table relationship {relationship.relationship_id}"
        for role, table_id, column in (
            ("source", relationship.source_table_id, relationship.source_column),
            ("target", relationship.target_table_id, relationship.target_column),
        ):
            if table_id not in table_ids:
                errors.append(f"{label} has unknown {role} table '{table_id}'.")
            elif column not in table_columns[table_id]:
                errors.append(f"{label} has unknown {role} column '{table_id}.{column}'.")

    _unique(lld.business_rules, "rule_id", "business rule", errors)
    for rule in lld.business_rules:
        label = f"Business rule {rule.rule_id}"
        _check_traced(label, rule, refs, errors)
        if rule.module_id is not None and rule.module_id not in module_ids:
            errors.append(f"{label} references unknown module '{rule.module_id}'." + _valid("module ids", module_ids))

    if not lld.sequence_flows:
        errors.append("The LLD defines no sequence flows.")
    _unique(lld.sequence_flows, "sequence_id", "sequence flow", errors)
    for flow in lld.sequence_flows:
        label = f"Sequence flow {flow.sequence_id}"
        _check_traced(label, flow, refs, errors)
        participants = _unique(flow.participants, "participant_id", f"participant in {flow.sequence_id}", errors)
        for participant in flow.participants:
            if participant.ref_id is not None and participant.ref_id not in component_ids | module_ids:
                errors.append(f"{label} participant '{participant.participant_id}' references unknown element '{participant.ref_id}'.")
        if not flow.steps:
            errors.append(f"{label} has no steps.")
        if len({step.order for step in flow.steps}) != len(flow.steps):
            errors.append(f"{label} repeats a step order number.")
        for step in flow.steps:
            for value in (step.source_participant_id, step.target_participant_id):
                if value not in participants:
                    errors.append(f"{label} step {step.order} uses undeclared participant '{value}'.")
            if step.api_id is not None and step.api_id not in api_ids:
                errors.append(f"{label} step {step.order} references unknown API '{step.api_id}'." + _valid("API ids", api_ids))

    _unique(lld.design_patterns, "pattern_id", "design pattern", errors)
    for pattern in lld.design_patterns:
        for module_id in pattern.applied_to_module_ids:
            if module_id not in module_ids:
                errors.append(f"Design pattern {pattern.pattern_id} is applied to unknown module '{module_id}'." + _valid("module ids", module_ids))

    _unique(lld.error_handling, "rule_id", "error-handling rule", errors)
    for rule in lld.error_handling:
        for api_id in rule.api_ids:
            if api_id not in api_ids:
                errors.append(f"Error-handling rule {rule.rule_id} references unknown API '{api_id}'." + _valid("API ids", api_ids))
        if rule.status_code is not None and not 100 <= rule.status_code <= 599:
            errors.append(f"Error-handling rule {rule.rule_id} has an invalid HTTP status code {rule.status_code}.")

    _unique(lld.validation_rules, "rule_id", "validation rule", errors)
    for rule in lld.validation_rules:
        label = f"Validation rule {rule.rule_id}"
        if rule.data_model_id is not None:
            if rule.data_model_id not in model_ids:
                errors.append(f"{label} references unknown data model '{rule.data_model_id}'.")
            elif rule.field_name is not None and rule.field_name not in model_fields[rule.data_model_id]:
                errors.append(f"{label} references unknown field '{rule.data_model_id}.{rule.field_name}'.")
        for requirement_id in rule.requirement_ids:
            if requirement_id not in refs.requirement_ids:
                errors.append(f"{label} cites unknown requirement id '{requirement_id}'.")

    _unique(lld.open_items, "item_id", "open item", errors)
    for item in lld.open_items:
        for requirement_id in item.requirement_ids:
            if requirement_id not in refs.requirement_ids:
                errors.append(f"Open item {item.item_id} cites unknown requirement id '{requirement_id}'.")
    return issues


def _cited(hld: HighLevelDesign, lld: LowLevelDesign) -> tuple[set[str], set[str]]:
    """(requirement ids, task ids) cited by any design element."""
    elements = [hld.style, *hld.actors, *hld.components, *hld.data_flows, *hld.integrations, *hld.deployment, *hld.decisions,
                *hld.quality_considerations, *hld.risks, *hld.open_items,
                *lld.modules, *lld.data_models, *lld.apis, *lld.tables, *lld.business_rules,
                *lld.sequence_flows, *lld.validation_rules, *lld.open_items]
    requirements: set[str] = set()
    tasks: set[str] = set()
    for element in elements:
        requirements.update(getattr(element, "requirement_ids", []))
        tasks.update(getattr(element, "task_ids", []))
    return requirements, tasks


def validate_design(hld: HighLevelDesign, lld: LowLevelDesign, refs: ReferenceIds) -> ArchIssues:
    """Full check of a complete design: HLD, LLD, their consistency, and requirement coverage."""
    first = validate_hld(hld, refs)
    second = validate_lld(lld, hld, refs)
    issues = ArchIssues(
        errors=[*first.errors, *second.errors],
        warnings=[*first.warnings, *second.warnings],
    )

    item_ids = [i.item_id for i in [*hld.open_items, *lld.open_items]]
    if len(set(item_ids)) != len(item_ids):
        issues.errors.append("An open-item id is used in both the HLD and the LLD; ids must be unique.")

    requirements, tasks = _cited(hld, lld)
    for requirement_id in sorted(refs.functional_ids - requirements):
        issues.coverage_gaps.append(
            f"Functional requirement {requirement_id} is not addressed by any component, module, API, table, rule or sequence."
        )
    for requirement_id in sorted(refs.nfr_ids - requirements):
        issues.coverage_gaps.append(
            f"Non-functional requirement {requirement_id} is not addressed by any quality consideration, decision or design element."
        )
    uncovered_constraints = sorted(refs.constraint_ids - requirements)
    if uncovered_constraints:
        issues.warnings.append(f"Constraints not referenced by the design: {', '.join(uncovered_constraints[:_MAX_LISTED])}.")
    unreferenced_tasks = sorted(refs.task_ids - tasks)
    if unreferenced_tasks:
        shown = ", ".join(unreferenced_tasks[:_MAX_LISTED])
        more = f" and {len(unreferenced_tasks) - _MAX_LISTED} more" if len(unreferenced_tasks) > _MAX_LISTED else ""
        issues.warnings.append(f"Project-plan tasks not referenced by the design: {shown}{more}.")
    return issues


# ---------------------------------------------------------------------------
# Derived views (built from the validated design, never written by the LLM)
# ---------------------------------------------------------------------------


def _mermaid_text(value: str) -> str:
    return " ".join(str(value).replace('"', "'").split())


def build_diagram(hld: HighLevelDesign) -> dict:
    """Architecture diagram structure from the generated components and relationships."""
    nodes = [
        {
            "id": c.component_id,
            "label": c.name,
            "type": c.type,
            "layer": _LAYER_BY_TYPE.get(c.type, 1),
            "grounding": c.grounding,
        }
        for c in hld.components
    ]
    edges = [
        {
            "id": r.relationship_id,
            "source": r.source_component_id,
            "target": r.target_component_id,
            "label": r.description if len(r.description) <= 48 else r.description[:45] + "...",
            "interaction": r.interaction,
        }
        for r in hld.relationships
    ]

    lines = ["flowchart LR"]
    for node in nodes:
        text = f'"{_mermaid_text(node["label"])}<br/>{node["type"].replace("_", " ")}"'
        if node["type"] in ("DATABASE", "STORAGE"):
            lines.append(f"  {node['id']}[({text})]")
        elif node["type"] == "EXTERNAL_SYSTEM":
            lines.append(f"  {node['id']}{{{{{text}}}}}")
        else:
            lines.append(f"  {node['id']}[{text}]")
    for edge in edges:
        lines.append(f'  {edge["source"]} -->|"{_mermaid_text(edge["interaction"])}"| {edge["target"]}')
    return {"nodes": nodes, "edges": edges, "mermaid": "\n".join(lines)}


def build_detailed_diagram(hld: HighLevelDesign, lld: LowLevelDesign) -> dict:
    """Detailed architecture view: every component with what the LLD places inside it.

    Derived from the validated design only. Modules sit in the component they belong to, an
    endpoint sits under the controller that implements it, and module dependencies and table
    foreign keys become arrows. Tables carry no component in the LLD, so they are shown in the
    database component only when there is exactly one; otherwise they get their own box rather
    than being guessed into one.
    """
    module_ids = {m.module_id for m in lld.modules}
    table_ids = {t.table_id for t in lld.tables}

    endpoints_of_module: dict[str, list[dict]] = {}
    loose_endpoints: dict[str, list[dict]] = {}
    for api in lld.apis:
        endpoint = {
            "id": api.api_id,
            "method": api.method,
            "path": api.path,
            "summary": api.summary,
            "auth_required": api.auth_required,
        }
        if api.module_id in module_ids:
            endpoints_of_module.setdefault(api.module_id, []).append(endpoint)
        else:
            loose_endpoints.setdefault(api.component_id, []).append(endpoint)

    tables = [
        {
            "id": t.table_id,
            "name": t.name,
            "columns": len(t.columns),
            "primary_key": [c.name for c in t.columns if c.primary_key],
            "description": t.description,
        }
        for t in lld.tables
    ]
    databases = [c for c in hld.components if c.type == "DATABASE"]
    table_owner = databases[0].component_id if len(databases) == 1 else None

    containers = []
    for component in hld.components:
        containers.append(
            {
                "id": component.component_id,
                "label": component.name,
                "type": component.type,
                "layer": _LAYER_BY_TYPE.get(component.type, 1),
                "grounding": component.grounding,
                "technology": component.technology,
                "modules": [
                    {
                        "id": m.module_id,
                        "name": m.name,
                        "kind": m.kind,
                        "description": m.description,
                        "methods": len(m.methods),
                        "endpoints": endpoints_of_module.get(m.module_id, []),
                    }
                    for m in lld.modules
                    if m.component_id == component.component_id
                ],
                "endpoints": loose_endpoints.get(component.component_id, []),
                "tables": tables if component.component_id == table_owner else [],
            }
        )

    separate_tables = None
    if tables and table_owner is None:
        separate_tables = {
            "id": "DATA_MODEL",
            "label": "Database tables",
            "type": "DATABASE",
            "layer": _LAYER_BY_TYPE["DATABASE"],
            "grounding": "INFERRED",
            "technology": None,
            "modules": [],
            "endpoints": [],
            "tables": tables,
        }

    return {
        "containers": containers + ([separate_tables] if separate_tables else []),
        "relationships": [
            {
                "id": r.relationship_id,
                "source": r.source_component_id,
                "target": r.target_component_id,
                "interaction": r.interaction,
                "label": r.description,
            }
            for r in hld.relationships
        ],
        "module_edges": [
            {"id": f"{m.module_id}>{dependency}", "source": m.module_id, "target": dependency}
            for m in lld.modules
            for dependency in m.depends_on_module_ids
            if dependency in module_ids
        ],
        "table_edges": [
            {
                "id": r.relationship_id,
                "source": r.source_table_id,
                "target": r.target_table_id,
                "source_column": r.source_column,
                "target_column": r.target_column,
                "cardinality": r.cardinality,
            }
            for r in lld.table_relationships
            if r.source_table_id in table_ids and r.target_table_id in table_ids
        ],
    }


def build_traceability(hld: HighLevelDesign, lld: LowLevelDesign, refs: ReferenceIds) -> list[dict]:
    """Requirement -> design elements matrix, derived from the ids the design actually cites."""
    buckets = {
        "component_ids": [(c.component_id, c) for c in hld.components],
        "module_ids": [(m.module_id, m) for m in lld.modules],
        "api_ids": [(a.api_id, a) for a in lld.apis],
        "table_ids": [(t.table_id, t) for t in lld.tables],
        "sequence_ids": [(s.sequence_id, s) for s in lld.sequence_flows],
        "other_element_ids": [
            *[(f.flow_id, f) for f in hld.data_flows],
            *[(i.integration_id, i) for i in hld.integrations],
            *[(d.decision_id, d) for d in hld.decisions],
            *[(q.consideration_id, q) for q in hld.quality_considerations],
            *[(r.risk_id, r) for r in hld.risks],
            *[(m.data_model_id, m) for m in lld.data_models],
            *[(b.rule_id, b) for b in lld.business_rules],
            *[(v.rule_id, v) for v in lld.validation_rules],
        ],
    }
    shown_prefixes = ("REQ", "US", "NFR", "CON")
    entries = []
    for requirement_id in sorted(refs.requirement_ids, key=_natural_key):
        prefix = requirement_id.split("-", 1)[0]
        if prefix not in shown_prefixes:
            continue
        entry = {key: [] for key in buckets}
        tasks: set[str] = set()
        for key, items in buckets.items():
            for element_id, element in items:
                if requirement_id in element.requirement_ids:
                    entry[key].append(element_id)
                    tasks.update(getattr(element, "task_ids", []))
        covered = any(entry.values())
        entries.append(
            {
                "requirement_id": requirement_id,
                "title": refs.titles.get(requirement_id),
                "kind": KIND_BY_PREFIX.get(prefix, prefix),
                "status": "COVERED" if covered else "NOT_COVERED",
                **entry,
                "task_ids": sorted(tasks, key=_natural_key),
            }
        )
    return entries


def _natural_key(value: str):
    prefix, _, number = value.partition("-")
    digits = "".join(ch for ch in value if ch.isdigit())
    return (prefix, int(digits) if digits else 0, value)


def design_counts(hld: HighLevelDesign, lld: LowLevelDesign) -> dict[str, int]:
    """Headline numbers for run summaries and the API."""
    return {
        "actors": len(hld.actors),
        "components": len(hld.components),
        "relationships": len(hld.relationships),
        "deployment_nodes": len(hld.deployment),
        "data_flows": len(hld.data_flows),
        "decisions": len(hld.decisions),
        "risks": len(hld.risks),
        "modules": len(lld.modules),
        "apis": len(lld.apis),
        "data_models": len(lld.data_models),
        "tables": len(lld.tables),
        "sequence_flows": len(lld.sequence_flows),
        "open_items": len(hld.open_items) + len(lld.open_items),
    }
