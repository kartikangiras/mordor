// The decisions, readable: entity names instead of ids, the person's title instead of a role id,
// one sentence per record, labelled details instead of raw JSON (PIVOT_PLAN.md task 27, P3/P19).
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useStore } from '@/lib/store'
import { PERSONAS } from '@/lib/experience'
import { ACTION_LABELS, OUTCOME_LABELS } from '@/lib/labels'
import { TIERS, type TierId } from '@/lib/aqi'
import { RECORD_STEPS, type DecisionRecord } from '@/lib/protocol'
import { istLabel } from '@/lib/time'

const ROLE_TITLES: Record<string, string> = { operator: 'operator', verifier: 'air-quality officer', analyst: 'forecast team', auditor: 'Directorate of Education', system: 'the model', pending: 'the model' }
const TYPE_LABELS: Record<string, string> = { school: 'school', rwa: "residents' association", agri_officer: 'district agriculture office', hospital: 'hospital' }

/** id -> display name, from the people and schools layers in the store. */
export function useEntityName(): (id: string) => string {
  const entities = useStore((s) => s.entities)
  const schools = useStore((s) => s.schools)
  return (id) => entities?.features.find((f) => f.properties.id === id)?.properties.name ?? schools?.features.find((f) => f.properties.id === id)?.properties.name ?? id
}

export function who(r: DecisionRecord): string {
  const p = r.by.persona ? PERSONAS[r.by.persona] : null
  if (p) return `${p.name} · ${p.title}`
  if (r.by.name && r.by.name !== 'system') return r.by.name
  return ROLE_TITLES[r.by.role] ?? r.by.role
}

const tierLabel = (t: unknown) => (typeof t === 'string' && t in TIERS ? TIERS[t as TierId].label : '—')
const actions = (a: unknown) => (Array.isArray(a) && a.length ? a.map((x) => ACTION_LABELS[String(x)] ?? String(x)).join(', ') : 'no actions')

/** One plain sentence per record. */
export function sentence(r: DecisionRecord): string {
  const p = r.payload
  switch (r.kind) {
    case 'enrol': return p.subject === 'registration' && p.approved ? 'approved the registration' : `registered the ${TYPE_LABELS[String(p.type)] ?? String(p.type ?? 'entity')}${p.people ? ` for ${Number(p.people).toLocaleString('en-IN')} people` : ''}`
    case 'forecast': return p.dayTier || p.peakAqi ? `forecast ${tierLabel(p.dayTier)}${p.peakAqi ? `, peak AQI ${p.peakAqi}` : ''}${p.headline ? ` — ${p.headline}` : ''}` : `forecast: ${String(p.headline ?? p.riskCategory ?? '—')}`
    case 'advise': return p.subject === 'plan' ? `planned ${(p.cells as unknown[] | undefined)?.length ?? 0} cells: ${actions(p.actions)}` : `advised ${String(p.audience ?? 'parents')}${p.source === 'agent' ? ' with a drafted message' : ' with the standard message'}`
    case 'act': { const as = p.assessment as { coverage?: number; protectedHours?: number; hoursAtRisk?: number; value?: number; unit?: string } | undefined; return `did: ${actions(p.actions)}${p.sentVia === 'whatsapp' ? ', sent on WhatsApp' : p.sentVia === 'email' ? ', sent by email' : p.sentVia === 'noted' || p.sentVia === 'copy' ? ', recorded without sending' : ''}${as && as.coverage !== undefined ? ` — covered ${Math.round(as.coverage * 100)}% of the hours at risk${as.hoursAtRisk ? ` (${as.protectedHours} of ${as.hoursAtRisk} h, ${Number(as.value ?? 0).toLocaleString('en-IN')} ${as.unit})` : ''}` : ''}` }
    case 'verify': return p.subject === 'registration' ? `checked the registration: ${String(p.outcome ?? 'approved')}` : `checked the day: ${OUTCOME_LABELS[String(p.outcome)] ?? String(p.outcome ?? '—').replace(/_/g, ' ')}${p.evidence ? ` — ${String(p.evidence)}` : p.reason ? ` — ${String(p.reason)}` : ''}`
    case 'account': return `${String(p.value ?? '—')} ${String(p.unit ?? '')} — ${String(p.status ?? '').replace(/_/g, ' ')}`
    default: return r.kind
  }
}

const DETAIL_KEYS: [string, string, (v: unknown) => string][] = [
  ['date', 'day', String], ['dayTier', 'tier', tierLabel], ['peakAqi', 'peak AQI', String], ['actions', 'actions', actions], ['sentVia', 'sent via', (v) => (v === 'noted' || v === 'copy' ? 'recorded without sending' : String(v))],
  ['outcome', 'outcome', (v) => OUTCOME_LABELS[String(v)] ?? String(v).replace(/_/g, ' ')], ['evidence', 'evidence', String], ['reason', 'reason', String], ['status', 'status', (v) => String(v).replace(/_/g, ' ')],
  ['value', 'value', String], ['unit', 'unit', String], ['people', 'people', String], ['hours', 'hours', (v) => (Array.isArray(v) ? v.join('–') : String(v))], ['dismissal', 'dismissal', (v) => (Array.isArray(v) ? v.join('–') : String(v))],
  ['cells', 'cells', (v) => (Array.isArray(v) ? v.map((c) => (c as { name?: string }).name ?? '').filter(Boolean).join(', ') : String(v))], ['verifiedBy', 'verified by', String], ['outdoorHoursCancelled', 'outdoor hours cancelled', String], ['chars', 'message length', (v) => `${v} characters`],
]

/** The pipeline writes a forecast and an advisory for every entity on every run (eight a day). A
 *  reader wants the latest, once, with the count; people's decisions stay one row each. */
function collapse(rows: DecisionRecord[]): { r: DecisionRecord; runs: number }[] {
  const system = (r: DecisionRecord) => (r.kind === 'forecast' || (r.kind === 'advise' && r.payload.subject !== 'plan')) && !r.by.persona && (r.by.name === 'system' || r.by.role === 'analyst')
  const latest = new Map<string, { r: DecisionRecord; runs: number }>()
  const out: { r: DecisionRecord; runs: number }[] = []
  for (const r of [...rows].sort((a, b) => a.seq - b.seq)) {
    if (!system(r)) { out.push({ r, runs: 1 }); continue }
    const key = `${r.kind}:${r.date}`
    const cur = latest.get(key)
    if (cur) { cur.r = r; cur.runs += 1 } else { const e = { r, runs: 1 }; latest.set(key, e); out.push(e) }
  }
  return out.sort((a, b) => b.r.seq - a.r.seq)
}

function Row({ r, runs, name, showEntity }: { r: DecisionRecord; runs: number; name: string; showEntity: boolean }) {
  const [open, setOpen] = useState(false)
  const step = RECORD_STEPS.find((s) => s.kind === r.kind)
  const details = DETAIL_KEYS.filter(([k]) => r.payload[k] !== undefined && r.payload[k] !== null && r.payload[k] !== '').map(([k, label, fmt]) => [label, fmt(r.payload[k])] as const)
  return (
    <li className="border-t border-white/8 py-2.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <div className="text-[13px] text-fg"><span className="mr-2 rounded-full bg-white/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-fg/80">{step?.label ?? r.kind}</span><span className="text-mute">{who(r)}</span> {sentence(r)}{r.by.persona && <span className="ml-2 rounded-full border border-fire/40 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-fire" title="Written by a fictional walkthrough persona">demo</span>}</div>
        <div className="font-mono text-[10.5px] text-mute">{istLabel(r.ts)} IST{runs > 1 && <> · latest of {runs} runs</>}{showEntity && <> · <Link to={`/records/${encodeURIComponent(r.entity)}`} className="underline hover:text-fg">{name}</Link></>}</div>
      </div>
      {details.length > 0 && (
        <div className="mt-1">
          <button type="button" onClick={() => setOpen(!open)} className="font-mono text-[10.5px] text-mute underline hover:text-fg">{open ? 'less' : 'details'}</button>
          {open && <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 text-[12px]">{details.map(([k, v]) => <div key={k} className="contents"><dt className="font-mono text-[10.5px] uppercase tracking-wider text-mute">{k}</dt><dd className="text-fg/90">{v}</dd></div>)}</dl>}
        </div>
      )}
    </li>
  )
}

/** records grouped by entity when more than one entity is present; newest first within a group. */
export default function DecisionList({ records, groupByEntity = true }: { records: DecisionRecord[]; groupByEntity?: boolean }) {
  const nameOf = useEntityName()
  const groups = groupByEntity ? [...new Set(records.map((r) => r.entity))].map((e) => ({ entity: e, rows: records.filter((r) => r.entity === e) })) : [{ entity: null, rows: records }]
  if (!records.length) return <div className="font-mono text-[11px] text-mute">No decisions yet.</div>
  return (
    <div className="space-y-5">
      {groups.map((g) => (
        <section key={g.entity ?? 'all'}>
          {g.entity && groups.length > 1 && <h2 className="mb-1 text-[14px] font-semibold text-fg"><Link to={`/records/${encodeURIComponent(g.entity)}`} className="hover:underline">{nameOf(g.entity)}</Link> <span className="font-mono text-[10.5px] font-normal text-mute">{g.rows.filter((r) => r.by.persona || !(r.kind === 'forecast' || r.kind === 'advise')).length} decisions · {g.rows.length} records</span></h2>}
          <ol>{collapse(g.rows).map(({ r, runs }) => <Row key={r.id} r={r} runs={runs} name={nameOf(r.entity)} showEntity={groups.length === 1 && !!groupByEntity && records.some((x) => x.entity !== r.entity)} />)}</ol>
        </section>
      ))}
    </div>
  )
}
