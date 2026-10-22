import { useMemo, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import ArchitectureDiagram from './ArchitectureDiagram'
import VisualArchitecture from './visual/VisualArchitecture'

const LEVEL = { HIGH: 'badge-danger', MEDIUM: 'badge-warning', LOW: 'badge-success' }
const GROUNDING = {
  EXPLICIT: 'badge-success',
  INFERRED: 'badge-info',
  ASSUMED: 'badge-warning',
  UNKNOWN: 'bg-gray-100 text-text-secondary',
}
const GROUNDING_HELP = {
  EXPLICIT: 'Stated in the requirements',
  INFERRED: 'Derived from the requirements',
  ASSUMED: 'A design choice the requirements do not make',
  UNKNOWN: 'The requirements do not say',
}
const METHOD = {
  GET: 'badge-info',
  POST: 'badge-success',
  PUT: 'badge-warning',
  PATCH: 'badge-warning',
  DELETE: 'badge-danger',
}
const QUALITY_LABEL = {
  AUTHENTICATION_AUTHORIZATION: 'Authentication & authorization',
  SCALABILITY: 'Scalability',
  RELIABILITY: 'Reliability',
  SECURITY: 'Security',
  DEPLOYMENT: 'Deployment',
  PERFORMANCE: 'Performance',
  OBSERVABILITY: 'Observability',
  OTHER: 'Other',
}
const pretty = (value) => String(value || '').replace(/_/g, ' ')

function Badge({ children, className = 'bg-gray-100 text-text-secondary', title }) {
  return <span className={`badge ${className}`} title={title}>{children}</span>
}

function GroundingBadge({ value }) {
  if (!value) return null
  return <Badge className={GROUNDING[value]} title={GROUNDING_HELP[value]}>{value}</Badge>
}

function Chip({ children, title, tone = 'bg-bg-light text-text-secondary' }) {
  return <span className={`text-xs px-2 py-1 rounded ${tone}`} title={title}>{children}</span>
}

function Metric({ label, value }) {
  return (
    <div className="bg-bg-light rounded-lg p-4">
      <p className="text-2xl font-bold text-primary">{value}</p>
      <p className="text-xs text-text-secondary mt-1">{label}</p>
    </div>
  )
}

function Empty({ children }) {
  return <p className="text-sm text-text-secondary">{children}</p>
}

function Heading({ children }) {
  return <h3 className="font-semibold text-text-primary mb-3">{children}</h3>
}

function Code({ children }) {
  return <pre className="text-xs bg-bg-light text-text-primary rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">{children}</pre>
}

/** Requirement and task ids a design element cites, with titles on hover. */
function Refs({ item, titles }) {
  const requirements = item.requirement_ids || []
  const tasks = item.task_ids || []
  if (!requirements.length && !tasks.length) return null
  return (
    <div className="flex flex-wrap gap-2 mt-3">
      {requirements.map((id) => <Chip key={id} title={titles[id]} tone="bg-purple-100 text-primary">{id}</Chip>)}
      {tasks.map((id) => <Chip key={id} tone="bg-bg-light text-text-secondary">{id}</Chip>)}
    </div>
  )
}

function Rationale({ item }) {
  if (!item.rationale) return null
  return <p className="text-xs text-text-secondary mt-2"><span className="font-medium">Why:</span> {item.rationale}</p>
}

function Card({ children }) {
  return <div className="border border-border-light rounded-lg p-4">{children}</div>
}

function Table({ headers, children }) {
  return (
    <div className="overflow-x-auto border border-border-light rounded-lg">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 border-b border-border-light text-left text-text-secondary">
            {headers.map((header) => <th key={header} className="px-3 py-2 font-medium whitespace-nowrap">{header}</th>)}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

/* ------------------------------------------------------------------ HLD */

function HldOverview({ data, titles }) {
  const { hld, architecture } = data
  const byCategory = {}
  hld.quality_considerations.forEach((item) => {
    ;(byCategory[item.category] = byCategory[item.category] || []).push(item)
  })
  const counts = architecture.counts || {}
  return (
    <div className="space-y-6">
      <div>
        <Heading>Architecture Overview</Heading>
        <p className="text-sm text-text-secondary whitespace-pre-wrap">{hld.overview}</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Metric label="Components" value={counts.components ?? hld.components.length} />
        <Metric label="Relationships" value={counts.relationships ?? hld.relationships.length} />
        <Metric label="Data flows" value={counts.data_flows ?? hld.data_flows.length} />
        <Metric label="Decisions" value={counts.decisions ?? hld.decisions.length} />
        <Metric label="Risks" value={counts.risks ?? hld.risks.length} />
      </div>

      <div>
        <Heading>Architecture Style</Heading>
        <Card>
          <div className="flex items-start justify-between gap-3">
            <p className="font-semibold text-text-primary">{hld.style.name}</p>
            <GroundingBadge value={hld.style.grounding} />
          </div>
          <p className="text-sm text-text-secondary mt-1">{hld.style.description}</p>
          <Rationale item={hld.style} />
          <Refs item={hld.style} titles={titles} />
        </Card>
      </div>

      <div>
        <Heading>System Architecture</Heading>
        <p className="text-sm text-text-secondary whitespace-pre-wrap">{hld.system_architecture}</p>
      </div>

      {!!hld.integrations.length && (
        <div>
          <Heading>External Integrations</Heading>
          <div className="space-y-3">
            {hld.integrations.map((item) => (
              <Card key={item.integration_id}>
                <div className="flex items-start justify-between gap-3">
                  <p className="font-semibold text-text-primary"><span className="text-text-secondary font-normal">{item.integration_id}</span> {item.name}</p>
                  <GroundingBadge value={item.grounding} />
                </div>
                <p className="text-sm text-text-secondary mt-1">{item.purpose}</p>
                <div className="flex flex-wrap gap-2 mt-2">
                  {item.component_id && <Chip>via {item.component_id}</Chip>}
                  {item.protocol && <Chip>{item.protocol}</Chip>}
                </div>
                <Rationale item={item} />
                <Refs item={item} titles={titles} />
              </Card>
            ))}
          </div>
        </div>
      )}

      <div>
        <Heading>Quality Considerations</Heading>
        {!hld.quality_considerations.length && <Empty>No quality considerations recorded.</Empty>}
        <div className="space-y-4">
          {Object.entries(byCategory).map(([category, items]) => (
            <div key={category}>
              <p className="text-xs font-semibold uppercase tracking-wide text-text-secondary mb-2">{QUALITY_LABEL[category] || pretty(category)}</p>
              <div className="space-y-3">
                {items.map((item) => (
                  <Card key={item.consideration_id}>
                    <div className="flex items-start justify-between gap-3">
                      <p className="font-semibold text-text-primary">{item.title}</p>
                      <GroundingBadge value={item.grounding} />
                    </div>
                    <p className="text-sm text-text-secondary mt-1">{item.approach}</p>
                    <Rationale item={item} />
                    <Refs item={item} titles={titles} />
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Components({ data, titles }) {
  const { components } = data.hld
  if (!components.length) return <Empty>No components defined.</Empty>
  return (
    <div className="space-y-3">
      {components.map((component) => (
        <Card key={component.component_id}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="font-semibold text-text-primary"><span className="text-text-secondary font-normal">{component.component_id}</span> {component.name}</p>
              <p className="text-sm text-text-secondary mt-1">{component.description}</p>
            </div>
            <div className="flex flex-col gap-1 items-end shrink-0">
              <Badge className="bg-purple-100 text-primary">{pretty(component.type)}</Badge>
              <GroundingBadge value={component.grounding} />
            </div>
          </div>
          {!!component.responsibilities.length && (
            <ul className="list-disc pl-5 text-sm text-text-secondary mt-3 space-y-1">
              {component.responsibilities.map((item, index) => <li key={index}>{item}</li>)}
            </ul>
          )}
          {component.technology && <p className="text-xs text-text-secondary mt-3">Technology: <span className="font-medium text-text-primary">{component.technology}</span></p>}
          <Rationale item={component} />
          <Refs item={component} titles={titles} />
        </Card>
      ))}
    </div>
  )
}

function Relationships({ data }) {
  const { components, relationships } = data.hld
  const name = Object.fromEntries(components.map((c) => [c.component_id, c.name]))
  if (!relationships.length) return <Empty>No relationships defined.</Empty>
  return (
    <Table headers={['ID', 'From', 'To', 'Interaction', 'Description', 'Data exchanged']}>
      {relationships.map((r) => (
        <tr key={r.relationship_id} className="border-b border-border-light last:border-b-0 align-top">
          <td className="px-3 py-2 text-text-secondary whitespace-nowrap">{r.relationship_id}</td>
          <td className="px-3 py-2 text-text-primary">{name[r.source_component_id] || r.source_component_id}</td>
          <td className="px-3 py-2 text-text-primary">{name[r.target_component_id] || r.target_component_id}</td>
          <td className="px-3 py-2"><Badge className="bg-purple-100 text-primary">{pretty(r.interaction)}</Badge></td>
          <td className="px-3 py-2 text-text-secondary">{r.description}</td>
          <td className="px-3 py-2 text-text-secondary">{r.data_exchanged || '—'}</td>
        </tr>
      ))}
    </Table>
  )
}

function DataFlows({ data, titles }) {
  const { components, data_flows } = data.hld
  const name = Object.fromEntries(components.map((c) => [c.component_id, c.name]))
  if (!data_flows.length) return <Empty>No data flows defined.</Empty>
  return (
    <div className="space-y-4">
      {data_flows.map((flow) => (
        <Card key={flow.flow_id}>
          <div className="flex items-start justify-between gap-3">
            <p className="font-semibold text-text-primary"><span className="text-text-secondary font-normal">{flow.flow_id}</span> {flow.name}</p>
            <GroundingBadge value={flow.grounding} />
          </div>
          <p className="text-sm text-text-secondary mt-1">{flow.description}</p>
          <ol className="mt-3 space-y-2">
            {flow.steps.map((step) => (
              <li key={step.order} className="flex items-start gap-3 text-sm">
                <span className="w-6 h-6 shrink-0 rounded-full bg-primary-light text-primary text-xs font-semibold flex items-center justify-center">{step.order}</span>
                <div>
                  <p className="text-text-primary"><span className="font-medium">{name[step.source_component_id] || step.source_component_id}</span> → <span className="font-medium">{name[step.target_component_id] || step.target_component_id}</span></p>
                  <p className="text-text-secondary">{step.description}</p>
                </div>
              </li>
            ))}
          </ol>
          <Rationale item={flow} />
          <Refs item={flow} titles={titles} />
        </Card>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ LLD */

function LldOverview({ data, titles }) {
  const { lld } = data
  const counts = data.architecture.counts || {}
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Metric label="Modules" value={counts.modules ?? lld.modules.length} />
        <Metric label="API endpoints" value={counts.apis ?? lld.apis.length} />
        <Metric label="Data models" value={counts.data_models ?? lld.data_models.length} />
        <Metric label="Tables" value={counts.tables ?? lld.tables.length} />
        <Metric label="Sequence flows" value={counts.sequence_flows ?? lld.sequence_flows.length} />
      </div>

      <div>
        <Heading>Business Logic</Heading>
        {!lld.business_rules.length && <Empty>No business rules recorded.</Empty>}
        <div className="space-y-3">
          {lld.business_rules.map((rule) => (
            <Card key={rule.rule_id}>
              <div className="flex items-start justify-between gap-3">
                <p className="font-semibold text-text-primary"><span className="text-text-secondary font-normal">{rule.rule_id}</span> {rule.title}</p>
                <GroundingBadge value={rule.grounding} />
              </div>
              <p className="text-sm text-text-secondary mt-1">{rule.description}</p>
              {rule.module_id && <p className="text-xs text-text-secondary mt-2">Implemented in {rule.module_id}</p>}
              {rule.pseudocode && <div className="mt-3"><Code>{rule.pseudocode}</Code></div>}
              <Rationale item={rule} />
              <Refs item={rule} titles={titles} />
            </Card>
          ))}
        </div>
      </div>

      {!!lld.design_patterns.length && (
        <div>
          <Heading>Design Patterns</Heading>
          <div className="space-y-3">
            {lld.design_patterns.map((pattern) => (
              <Card key={pattern.pattern_id}>
                <div className="flex items-start justify-between gap-3">
                  <p className="font-semibold text-text-primary">{pattern.name}</p>
                  <GroundingBadge value={pattern.grounding} />
                </div>
                <p className="text-sm text-text-secondary mt-1">{pattern.rationale}</p>
                {!!pattern.applied_to_module_ids.length && (
                  <div className="flex flex-wrap gap-2 mt-2">{pattern.applied_to_module_ids.map((id) => <Chip key={id}>{id}</Chip>)}</div>
                )}
              </Card>
            ))}
          </div>
        </div>
      )}

      {!!lld.error_handling.length && (
        <div>
          <Heading>Error Handling</Heading>
          <div className="space-y-3">
            {lld.error_handling.map((rule) => (
              <Card key={rule.rule_id}>
                <p className="font-semibold text-text-primary">{rule.title}</p>
                <p className="text-sm text-text-secondary mt-1">{rule.approach}</p>
                <div className="flex flex-wrap gap-2 mt-2">
                  {rule.status_code && <Chip>HTTP {rule.status_code}</Chip>}
                  {rule.api_ids.map((id) => <Chip key={id}>{id}</Chip>)}
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {!!lld.validation_rules.length && (
        <div>
          <Heading>Validation Rules</Heading>
          <Table headers={['ID', 'Applies to', 'Rule', 'Requirements']}>
            {lld.validation_rules.map((rule) => (
              <tr key={rule.rule_id} className="border-b border-border-light last:border-b-0 align-top">
                <td className="px-3 py-2 text-text-secondary whitespace-nowrap">{rule.rule_id}</td>
                <td className="px-3 py-2 text-text-primary whitespace-nowrap">{[rule.data_model_id, rule.field_name].filter(Boolean).join('.') || '—'}</td>
                <td className="px-3 py-2 text-text-secondary">{rule.rule}</td>
                <td className="px-3 py-2"><div className="flex flex-wrap gap-1">{rule.requirement_ids.map((id) => <Chip key={id} title={titles[id]} tone="bg-purple-100 text-primary">{id}</Chip>)}</div></td>
              </tr>
            ))}
          </Table>
        </div>
      )}
    </div>
  )
}

function ModelFields({ model }) {
  if (!model) return null
  return (
    <div className="mt-2">
      <p className="text-xs font-medium text-text-primary mb-1">{model.name} <span className="text-text-secondary font-normal">({pretty(model.kind).toLowerCase()})</span></p>
      <Table headers={['Field', 'Type', 'Required', 'Validation']}>
        {model.fields.map((field) => (
          <tr key={field.name} className="border-b border-border-light last:border-b-0">
            <td className="px-3 py-1.5 text-text-primary">{field.name}</td>
            <td className="px-3 py-1.5 text-text-secondary">{field.type}</td>
            <td className="px-3 py-1.5 text-text-secondary">{field.required ? 'yes' : 'no'}</td>
            <td className="px-3 py-1.5 text-text-secondary">{field.validation || '—'}</td>
          </tr>
        ))}
      </Table>
    </div>
  )
}

function Apis({ data, titles }) {
  const { apis, data_models } = data.lld
  const model = Object.fromEntries(data_models.map((m) => [m.data_model_id, m]))
  const standalone = data_models.filter((m) => !apis.some((a) => a.request_model_id === m.data_model_id || a.response_model_id === m.data_model_id))
  if (!apis.length && !data_models.length) return <Empty>No API specification defined.</Empty>
  return (
    <div className="space-y-4">
      {apis.map((api) => (
        <Card key={api.api_id}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="font-semibold text-text-primary flex flex-wrap items-center gap-2">
                <Badge className={METHOD[api.method]}>{api.method}</Badge>
                <code className="text-sm">{api.path}</code>
              </p>
              <p className="text-sm text-text-secondary mt-1">{api.summary}</p>
            </div>
            <div className="flex flex-col gap-1 items-end shrink-0">
              <Badge className={api.auth_required ? 'badge-warning' : 'bg-gray-100 text-text-secondary'}>{api.auth_required ? 'Auth required' : 'Public'}</Badge>
              <GroundingBadge value={api.grounding} />
            </div>
          </div>
          <div className="flex flex-wrap gap-2 mt-3">
            <Chip>{api.api_id}</Chip>
            <Chip>component {api.component_id}</Chip>
            {api.module_id && <Chip>module {api.module_id}</Chip>}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ModelFields model={model[api.request_model_id]} />
            <ModelFields model={model[api.response_model_id]} />
          </div>
          {!!api.errors.length && (
            <div className="mt-3">
              <p className="text-xs font-medium text-text-primary mb-1">Errors</p>
              <ul className="text-sm text-text-secondary space-y-1">
                {api.errors.map((error, index) => <li key={index}><span className="font-medium text-text-primary">{error.status_code}</span> — {error.condition}</li>)}
              </ul>
            </div>
          )}
          {!!api.validation_rules.length && (
            <div className="mt-3">
              <p className="text-xs font-medium text-text-primary mb-1">Validation</p>
              <ul className="list-disc pl-5 text-sm text-text-secondary space-y-1">
                {api.validation_rules.map((rule, index) => <li key={index}>{rule}</li>)}
              </ul>
            </div>
          )}
          <Rationale item={api} />
          <Refs item={api} titles={titles} />
        </Card>
      ))}
      {!!standalone.length && (
        <div>
          <Heading>Other Data Models</Heading>
          <div className="space-y-3">{standalone.map((m) => <Card key={m.data_model_id}><ModelFields model={m} /></Card>)}</div>
        </div>
      )}
    </div>
  )
}

function Database({ data, titles }) {
  const { tables, table_relationships } = data.lld
  const name = Object.fromEntries(tables.map((t) => [t.table_id, t.name]))
  if (!tables.length) return <Empty>No database tables defined.</Empty>
  return (
    <div className="space-y-6">
      <div className="space-y-4">
        {tables.map((table) => (
          <Card key={table.table_id}>
            <div className="flex items-start justify-between gap-3">
              <p className="font-semibold text-text-primary"><span className="text-text-secondary font-normal">{table.table_id}</span> <code>{table.name}</code></p>
              <GroundingBadge value={table.grounding} />
            </div>
            <p className="text-sm text-text-secondary mt-1 mb-3">{table.description}</p>
            <Table headers={['Column', 'Type', 'Key', 'Nullable', 'Unique', 'Notes']}>
              {table.columns.map((column) => (
                <tr key={column.name} className="border-b border-border-light last:border-b-0">
                  <td className="px-3 py-1.5 text-text-primary">{column.name}</td>
                  <td className="px-3 py-1.5 text-text-secondary">{column.type}</td>
                  <td className="px-3 py-1.5">{column.primary_key && <Badge className="bg-purple-100 text-primary">PK</Badge>}</td>
                  <td className="px-3 py-1.5 text-text-secondary">{column.nullable ? 'yes' : 'no'}</td>
                  <td className="px-3 py-1.5 text-text-secondary">{column.unique ? 'yes' : 'no'}</td>
                  <td className="px-3 py-1.5 text-text-secondary">{column.description || '—'}</td>
                </tr>
              ))}
            </Table>
            {!!table.indexes.length && (
              <div className="flex flex-wrap gap-2 mt-3">{table.indexes.map((index) => <Chip key={index}>{index}</Chip>)}</div>
            )}
            <Rationale item={table} />
            <Refs item={table} titles={titles} />
          </Card>
        ))}
      </div>
      <div>
        <Heading>Relationships</Heading>
        {!table_relationships.length && <Empty>No relationships between tables.</Empty>}
        {!!table_relationships.length && (
          <Table headers={['ID', 'From', 'To', 'Cardinality', 'Description']}>
            {table_relationships.map((r) => (
              <tr key={r.relationship_id} className="border-b border-border-light last:border-b-0 align-top">
                <td className="px-3 py-2 text-text-secondary whitespace-nowrap">{r.relationship_id}</td>
                <td className="px-3 py-2 text-text-primary"><code>{name[r.source_table_id] || r.source_table_id}.{r.source_column}</code></td>
                <td className="px-3 py-2 text-text-primary"><code>{name[r.target_table_id] || r.target_table_id}.{r.target_column}</code></td>
                <td className="px-3 py-2"><Badge className="bg-purple-100 text-primary">{pretty(r.cardinality)}</Badge></td>
                <td className="px-3 py-2 text-text-secondary">{r.description || '—'}</td>
              </tr>
            ))}
          </Table>
        )}
      </div>
    </div>
  )
}

function Modules({ data, titles }) {
  const { modules, interfaces } = data.lld
  const component = Object.fromEntries(data.hld.components.map((c) => [c.component_id, c.name]))
  const moduleName = Object.fromEntries(modules.map((m) => [m.module_id, m.name]))
  if (!modules.length) return <Empty>No modules defined.</Empty>
  return (
    <div className="space-y-6">
      <div className="space-y-3">
        {modules.map((module) => (
          <Card key={module.module_id}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-semibold text-text-primary"><span className="text-text-secondary font-normal">{module.module_id}</span> {module.name}</p>
                <p className="text-sm text-text-secondary mt-1">{module.description}</p>
              </div>
              <div className="flex flex-col gap-1 items-end shrink-0">
                <Badge className="bg-purple-100 text-primary">{pretty(module.kind)}</Badge>
                <GroundingBadge value={module.grounding} />
              </div>
            </div>
            <p className="text-xs text-text-secondary mt-2">Component: {component[module.component_id] || module.component_id}</p>
            {!!module.responsibilities.length && (
              <ul className="list-disc pl-5 text-sm text-text-secondary mt-3 space-y-1">
                {module.responsibilities.map((item, index) => <li key={index}>{item}</li>)}
              </ul>
            )}
            {!!module.methods.length && (
              <div className="mt-3 space-y-2">
                {module.methods.map((method) => (
                  <div key={method.name + method.signature}>
                    <code className="text-xs text-primary">{method.signature}</code>
                    <p className="text-xs text-text-secondary">{method.description}</p>
                  </div>
                ))}
              </div>
            )}
            {!!module.depends_on_module_ids.length && (
              <p className="text-xs text-text-secondary mt-3">Depends on: {module.depends_on_module_ids.map((id) => moduleName[id] || id).join(', ')}</p>
            )}
            <Rationale item={module} />
            <Refs item={module} titles={titles} />
          </Card>
        ))}
      </div>
      {!!interfaces.length && (
        <div>
          <Heading>Interfaces</Heading>
          <div className="space-y-3">
            {interfaces.map((item) => (
              <Card key={item.interface_id}>
                <p className="font-semibold text-text-primary"><span className="text-text-secondary font-normal">{item.interface_id}</span> {item.name}</p>
                <p className="text-sm text-text-secondary mt-1">{item.description}</p>
                <div className="mt-2 space-y-1">{item.methods.map((m) => <div key={m.name}><code className="text-xs text-primary">{m.signature}</code></div>)}</div>
                {!!item.implemented_by_module_ids.length && (
                  <p className="text-xs text-text-secondary mt-2">Implemented by: {item.implemented_by_module_ids.map((id) => moduleName[id] || id).join(', ')}</p>
                )}
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function Sequences({ data, titles }) {
  const { sequence_flows } = data.lld
  if (!sequence_flows.length) return <Empty>No sequence flows defined.</Empty>
  return (
    <div className="space-y-4">
      {sequence_flows.map((flow) => {
        const label = Object.fromEntries(flow.participants.map((p) => [p.participant_id, p.label]))
        return (
          <Card key={flow.sequence_id}>
            <div className="flex items-start justify-between gap-3">
              <p className="font-semibold text-text-primary"><span className="text-text-secondary font-normal">{flow.sequence_id}</span> {flow.name}</p>
              <GroundingBadge value={flow.grounding} />
            </div>
            <p className="text-sm text-text-secondary mt-1">{flow.description}</p>
            <div className="flex flex-wrap gap-2 mt-3">
              {flow.participants.map((p) => <Chip key={p.participant_id} tone="bg-purple-100 text-primary">{p.label}</Chip>)}
            </div>
            <ol className="mt-3 space-y-2">
              {flow.steps.map((step) => (
                <li key={step.order} className="flex items-start gap-3 text-sm">
                  <span className="w-6 h-6 shrink-0 rounded-full bg-primary-light text-primary text-xs font-semibold flex items-center justify-center">{step.order}</span>
                  <div>
                    <p className="text-text-primary"><span className="font-medium">{label[step.source_participant_id] || step.source_participant_id}</span> → <span className="font-medium">{label[step.target_participant_id] || step.target_participant_id}</span></p>
                    <p className="text-text-secondary">{step.message}{step.api_id && <Chip> {step.api_id}</Chip>}</p>
                  </div>
                </li>
              ))}
            </ol>
            <Rationale item={flow} />
            <Refs item={flow} titles={titles} />
          </Card>
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------- decisions, risks */

function Decisions({ data, titles }) {
  const { decisions } = data.hld
  if (!decisions.length) return <Empty>No design decisions recorded.</Empty>
  return (
    <div className="space-y-3">
      {decisions.map((decision) => (
        <Card key={decision.decision_id}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-text-secondary">{decision.area}</p>
              <p className="font-semibold text-text-primary mt-1"><span className="text-text-secondary font-normal">{decision.decision_id}</span> {decision.decision}</p>
            </div>
            <GroundingBadge value={decision.grounding} />
          </div>
          <p className="text-sm text-text-secondary mt-2"><span className="font-medium text-text-primary">Trade-offs:</span> {decision.tradeoffs}</p>
          {!!decision.alternatives_considered.length && (
            <p className="text-sm text-text-secondary mt-1"><span className="font-medium text-text-primary">Alternatives considered:</span> {decision.alternatives_considered.join(', ')}</p>
          )}
          <Rationale item={decision} />
          <Refs item={decision} titles={titles} />
        </Card>
      ))}
    </div>
  )
}

function Risks({ data, titles }) {
  const { risks, components } = data.hld
  const name = Object.fromEntries(components.map((c) => [c.component_id, c.name]))
  if (!risks.length) return <Empty>No architecture risks recorded.</Empty>
  return (
    <div className="space-y-3">
      {risks.map((risk) => (
        <Card key={risk.risk_id}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="font-semibold text-text-primary"><span className="text-text-secondary font-normal">{risk.risk_id}</span> {risk.title}</p>
              <p className="text-sm text-text-secondary mt-1">{risk.description}</p>
            </div>
            <div className="flex flex-col gap-1 items-end shrink-0">
              <Badge className={LEVEL[risk.impact]}>Impact {risk.impact}</Badge>
              <Badge className={LEVEL[risk.likelihood]}>Likelihood {risk.likelihood}</Badge>
            </div>
          </div>
          <p className="text-sm text-text-secondary mt-2"><span className="font-medium text-text-primary">Mitigation:</span> {risk.mitigation}</p>
          <div className="flex flex-wrap gap-2 mt-3">
            {risk.component_ids.map((id) => <Chip key={id}>{name[id] || id}</Chip>)}
            {risk.requirement_ids.map((id) => <Chip key={id} title={titles[id]} tone="bg-purple-100 text-primary">{id}</Chip>)}
          </div>
        </Card>
      ))}
    </div>
  )
}

/* ---------------------------------------------- traceability, open items */

function Traceability({ data }) {
  const [filter, setFilter] = useState('ALL')
  const rows = data.traceability.filter((row) => filter === 'ALL' || row.status === filter)
  const covered = data.traceability.filter((row) => row.status === 'COVERED').length
  if (!data.traceability.length) return <Empty>No traceability information available.</Empty>
  const cell = (ids) => (ids.length ? <div className="flex flex-wrap gap-1">{ids.map((id) => <Chip key={id}>{id}</Chip>)}</div> : <span className="text-text-secondary">—</span>)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-text-secondary">{covered} of {data.traceability.length} requirement artifacts are addressed by the design.</p>
        <label className="text-sm text-text-secondary">Show
          <select value={filter} onChange={(e) => setFilter(e.target.value)} className="input-field ml-3">
            <option value="ALL">All</option>
            <option value="COVERED">Covered</option>
            <option value="NOT_COVERED">Not covered</option>
          </select>
        </label>
      </div>
      <Table headers={['Requirement', 'Kind', 'Status', 'Components', 'Modules', 'APIs', 'Tables', 'Sequences', 'Tasks']}>
        {rows.map((row) => (
          <tr key={row.requirement_id} className="border-b border-border-light last:border-b-0 align-top">
            <td className="px-3 py-2"><p className="font-medium text-text-primary whitespace-nowrap">{row.requirement_id}</p>{row.title && <p className="text-xs text-text-secondary max-w-[14rem]">{row.title}</p>}</td>
            <td className="px-3 py-2 text-text-secondary">{row.kind}</td>
            <td className="px-3 py-2"><Badge className={row.status === 'COVERED' ? 'badge-success' : 'badge-warning'}>{pretty(row.status)}</Badge></td>
            <td className="px-3 py-2">{cell(row.component_ids)}</td>
            <td className="px-3 py-2">{cell(row.module_ids)}</td>
            <td className="px-3 py-2">{cell(row.api_ids)}</td>
            <td className="px-3 py-2">{cell(row.table_ids)}</td>
            <td className="px-3 py-2">{cell(row.sequence_ids)}</td>
            <td className="px-3 py-2">{cell(row.task_ids)}</td>
          </tr>
        ))}
      </Table>
      {!rows.length && <Empty>Nothing matches this filter.</Empty>}
    </div>
  )
}

function OpenItems({ data, titles }) {
  const groups = [
    { kind: 'ASSUMED', title: 'Assumptions', hint: 'Design choices the requirements do not make. Confirm or change them.' },
    { kind: 'UNKNOWN', title: 'Unknowns', hint: 'Things the requirements leave unspecified.' },
  ]
  if (!data.open_items.length) return <Empty>No assumptions or unknowns recorded.</Empty>
  return (
    <div className="space-y-6">
      {groups.map((group) => {
        const items = data.open_items.filter((item) => item.kind === group.kind)
        return (
          <div key={group.kind}>
            <Heading>{group.title} ({items.length})</Heading>
            <p className="text-xs text-text-secondary mb-3">{group.hint}</p>
            {!items.length && <Empty>None.</Empty>}
            <div className="space-y-3">
              {items.map((item) => (
                <Card key={item.item_id}>
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm text-text-primary"><span className="text-text-secondary">{item.item_id}</span> {item.statement}</p>
                    <GroundingBadge value={item.kind} />
                  </div>
                  <p className="text-sm text-text-secondary mt-2"><span className="font-medium text-text-primary">Impact:</span> {item.impact}</p>
                  <Refs item={item} titles={titles} />
                </Card>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/* ------------------------------------------------------------------ main */

function ArchitectureResults({ architecture, projectName }) {
  const [active, setActive] = useState('overview')
  const titles = useMemo(
    () => Object.fromEntries((architecture?.traceability || []).map((row) => [row.requirement_id, row.title || row.kind])),
    [architecture],
  )

  if (!architecture?.hld || !architecture?.lld) {
    return (
      <div className="text-sm text-text-secondary">
        {architecture?.status === 'FAILED' && architecture.latest_agent_run?.error
          ? `The last attempt to generate the architecture failed: ${architecture.latest_agent_run.error}`
          : 'No architecture yet. Generate the project plan, then run the System Architect from the AI Agents page.'}
      </div>
    )
  }

  const { hld, lld, traceability } = architecture
  const info = architecture.architecture
  const tabs = [
    { key: 'overview', label: 'HLD Overview' },
    { key: 'diagram', label: 'Architecture Diagram' },
    { key: 'components', label: `Components (${hld.components.length})` },
    { key: 'relationships', label: `Component Relationships (${hld.relationships.length})` },
    { key: 'dataflow', label: `Data Flow (${hld.data_flows.length})` },
    { key: 'lld', label: 'LLD' },
    { key: 'apis', label: `APIs (${lld.apis.length})` },
    { key: 'database', label: `Database Design (${lld.tables.length})` },
    { key: 'modules', label: `Classes/Modules (${lld.modules.length})` },
    { key: 'sequences', label: `Sequence Flows (${lld.sequence_flows.length})` },
    { key: 'decisions', label: `Design Decisions (${hld.decisions.length})` },
    { key: 'risks', label: `Risks (${hld.risks.length})` },
    { key: 'traceability', label: `Requirement Traceability (${traceability.length})` },
    { key: 'open', label: `Assumptions / Unknowns (${architecture.open_items.length})` },
  ]
  // Sections read the design plus the architecture summary (counts, timestamps) from one object.
  const data = { architecture: info, hld, lld, traceability, open_items: architecture.open_items, diagram: architecture.diagram }

  return (
    <div className="space-y-4">
      {info.requirements_changed && (
        <div className="flex items-start gap-2 text-sm text-yellow-800 bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          The requirements were re-analyzed after this architecture was generated. Regenerate it to keep it in sync.
        </div>
      )}
      {info.plan_changed && (
        <div className="flex items-start gap-2 text-sm text-yellow-800 bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          The project plan was regenerated after this architecture was generated. Regenerate it to keep it in sync.
        </div>
      )}
      {architecture.status === 'FAILED' && architecture.latest_agent_run?.error && (
        <div className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          The latest regeneration failed, so the previous architecture is shown. {architecture.latest_agent_run.error}
        </div>
      )}

      <VisualArchitecture hld={data.hld} lld={data.lld} projectName={projectName} />

      <div className="border-t border-border-light pt-5">
        <h3 className="text-lg font-bold text-text-primary">Detailed design</h3>
        <p className="text-sm text-text-secondary">The full written HLD and LLD behind the diagrams above.</p>
      </div>

      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActive(tab.key)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                active === tab.key ? 'bg-primary text-white' : 'bg-bg-light text-text-secondary hover:text-text-primary'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {info.created_at && (
          <span className="text-xs text-text-secondary whitespace-nowrap ml-3">Generated {new Date(info.created_at).toLocaleString()}</span>
        )}
      </div>

      {active === 'overview' && <HldOverview data={data} titles={titles} />}
      {active === 'diagram' && <ArchitectureDiagram diagram={data.diagram} />}
      {active === 'components' && <Components data={data} titles={titles} />}
      {active === 'relationships' && <Relationships data={data} />}
      {active === 'dataflow' && <DataFlows data={data} titles={titles} />}
      {active === 'lld' && <LldOverview data={data} titles={titles} />}
      {active === 'apis' && <Apis data={data} titles={titles} />}
      {active === 'database' && <Database data={data} titles={titles} />}
      {active === 'modules' && <Modules data={data} titles={titles} />}
      {active === 'sequences' && <Sequences data={data} titles={titles} />}
      {active === 'decisions' && <Decisions data={data} titles={titles} />}
      {active === 'risks' && <Risks data={data} titles={titles} />}
      {active === 'traceability' && <Traceability data={data} />}
      {active === 'open' && <OpenItems data={data} titles={titles} />}

      {!!info.warnings?.length && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <p className="text-sm font-medium text-yellow-800 mb-2">Notes from validation</p>
          <ul className="list-disc pl-5 text-sm text-yellow-800 space-y-1">
            {info.warnings.map((item, index) => <li key={index}>{item}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

export default ArchitectureResults
