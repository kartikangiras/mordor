// Reading the decision records (PIVOT_PLAN.md task 44). The store writes a forecast and an
// advisory for every entity on every run (eight a day) and a walkthrough can log the same act
// many times; a reader wants the state of the day per entity, and a history that says "logged 8
// times" instead of eight rows. Pure functions; the pages only render what comes out.
import { PERSONAS } from '@/lib/experience'
import { ACTION_LABELS, OUTCOME_LABELS } from '@/lib/labels'
import { TIERS, type TierId } from '@/lib/aqi'
import type { DecisionRecord } from '@/lib/protocol'
import { istClock } from '@/lib/time'

const ROLE_TITLES: Record<string, string> = { verifier: 'the air-quality officer', analyst: 'the forecast team', auditor: 'the Directorate of Education', system: 'the model', pending: 'the model' }
/** A signed-in operator with no persona is named by the seat they hold at that kind of entity. */
const SEAT_TITLES: Record<string, string> = { school: 'the principal', rwa: 'the RWA secretary', hospital: 'the medical superintendent', agri_officer: 'the district agriculture officer' }
export const TYPE_LABELS: Record<string, string> = { school: 'school', rwa: "residents' association", agri_officer: 'district agriculture office', hospital: 'hospital' }
const TIER_RANK: Record<string, number> = { T4: 4, T3: 3, T2: 2, T1: 1, T0: 0 }

export const isTier = (t: unknown): t is TierId => typeof t === 'string' && t in TIERS
export const tierLabel = (t: unknown) => (isTier(t) ? TIERS[t].label : null)
export const actionsText = (a: unknown) => (Array.isArray(a) && a.length ? a.map((x) => ACTION_LABELS[String(x)] ?? String(x).replace(/_/g, ' ')).join(', ') : 'no actions')

/** A person's record: written by a persona or a signed-in user, not by the pipeline. */
export const byPerson = (r: DecisionRecord) => !!r.by.persona || (!!r.by.sub && r.by.name !== 'system')
/** The pipeline's per-run rows: the forecast and the advisory (a person's plan is an advisory too, but theirs). */
export const bySystem = (r: DecisionRecord) => !byPerson(r) && (r.kind === 'forecast' || (r.kind === 'advise' && r.payload.subject !== 'plan') || r.kind === 'account')

/** Who did it, as a name and a title; never a role id. */
export function who(r: DecisionRecord): string {
  const p = r.by.persona ? PERSONAS[r.by.persona] : null
  if (p) return `${p.name} · ${p.title}`
  if (r.by.name && r.by.name !== 'system') return r.by.name
  if (r.by.role === 'operator') return SEAT_TITLES[r.actorType] ?? 'the operator'
  return ROLE_TITLES[r.by.role] ?? `the ${r.by.role}`
}
export const whoShort = (r: DecisionRecord) => (r.by.persona ? r.by.persona : who(r))

const sentVia = (v: unknown) => (v === 'whatsapp' ? ', sent on WhatsApp' : v === 'email' ? ', sent by email' : v === 'noted' || v === 'copy' ? ', recorded without sending' : '')

/** One plain sentence per record, for the history. */
export function sentence(r: DecisionRecord): string {
  const p = r.payload
  switch (r.kind) {
    case 'enrol': return p.subject === 'registration' && p.approved ? 'approved the registration' : `registered the ${TYPE_LABELS[String(p.type)] ?? String(p.type ?? 'entity')}${p.people ? ` for ${Number(p.people).toLocaleString('en-IN')} people` : ''}`
    case 'forecast': return `forecast ${forecastText(r)}`
    case 'advise': return p.subject === 'plan' ? `planned ${(p.cells as unknown[] | undefined)?.length ?? 0} cells: ${actionsText(p.actions)}` : `advised ${String(p.audience ?? 'parents')}${p.source === 'agent' ? ' with a drafted message' : ' with the standard message'}`
    case 'act': return `did: ${actionsText(p.actions)}${sentVia(p.sentVia)}${coverageText(p.assessment)}`
    case 'verify': return p.subject === 'registration' ? `checked the registration: ${String(p.outcome ?? 'approved')}` : checkText(r)
    case 'account': return creditText(r)
    default: return r.kind
  }
}

export function forecastText(r: DecisionRecord): string {
  const p = r.payload
  const tier = tierLabel(p.dayTier)
  if (tier) return `${tier}${p.peakAqi ? `, peak AQI ${p.peakAqi}` : ''}${p.headline ? ` — ${String(p.headline)}` : ''}`
  // a source card (district office): no exposure tier, a risk category and a headline
  const risk = p.riskCategory ?? p.dayTier
  const burning = typeof p.burningNow === 'number' ? `, ${p.burningNow} cells burning` : ''
  return risk ? `burning risk ${String(risk)}${burning}` : String(p.headline ?? '—')
}

export function coverageText(a: unknown): string {
  const as = a as { coverage?: number; protectedHours?: number; hoursAtRisk?: number; value?: number; unit?: string } | undefined
  if (!as || as.coverage === undefined) return ''
  if (!as.hoursAtRisk) return ' — no hours at risk that day'
  return ` — covered ${Math.round(as.coverage * 100)}% of the hours at risk (${as.protectedHours} of ${as.hoursAtRisk} h, ${Number(as.value ?? 0).toLocaleString('en-IN')} ${as.unit})`
}

export function checkText(r: DecisionRecord): string {
  const p = r.payload
  const o = String(p.outcome ?? 'pending')
  if (o === 'pending') return 'check pending: the station confirms the day tomorrow'
  const label = OUTCOME_LABELS[o] ?? o.replace(/_/g, ' ')
  // the label already says it for a missing station; otherwise the evidence, or the reason
  const why = o === 'no_station' || o === 'no_data' ? '' : p.evidence && p.evidence !== 'officer judgement' ? ` — ${String(p.evidence)}` : p.reason ? ` — ${String(p.reason)}` : ''
  return `checked the day: ${label}${why}`
}

export function creditText(r: DecisionRecord): string {
  const p = r.payload
  const status = String(p.status ?? '').replace(/_/g, ' ')
  return `${Number(p.value ?? 0).toLocaleString('en-IN')} ${String(p.unit ?? '')} · ${status || 'provisional'}`
}

/** A folded history row: the record shown, how many identical ones it stands for, and their span. */
export type FoldedRow = { r: DecisionRecord; times: number; first: string; runs: number }

/** The history, newest first: the pipeline's rows folded to the latest per day with the run count,
 *  and a person's identical consecutive records (same kind, person, actions, outcome) folded to one
 *  with the count and the span. */
export function foldHistory(rows: DecisionRecord[]): FoldedRow[] {
  const bySeq = [...rows].sort((a, b) => a.seq - b.seq)
  const latest = new Map<string, FoldedRow>()
  const out: FoldedRow[] = []
  let prev: FoldedRow | null = null
  for (const r of bySeq) {
    if (bySystem(r)) {
      const key = `${r.kind}:${r.payload.date ?? r.date}`
      const cur = latest.get(key)
      if (cur) { cur.r = r; cur.runs += 1 } else { const e = { r, times: 1, first: r.ts, runs: 1 }; latest.set(key, e); out.push(e) }
      continue
    }
    if (prev && sameDecision(prev.r, r)) { prev.times += 1; prev.r = r; continue }
    prev = { r, times: 1, first: r.ts, runs: 1 }
    out.push(prev)
  }
  return out.sort((a, b) => b.r.seq - a.r.seq)
}

function sameDecision(a: DecisionRecord, b: DecisionRecord): boolean {
  if (a.kind !== b.kind || a.entity !== b.entity || (a.by.persona ?? a.by.sub) !== (b.by.persona ?? b.by.sub)) return false
  const pa = a.payload, pb = b.payload
  if (a.kind === 'act' || a.kind === 'advise') return JSON.stringify(pa.actions ?? null) === JSON.stringify(pb.actions ?? null) && pa.sentVia === pb.sentVia && pa.subject === pb.subject
  if (a.kind === 'verify') return pa.outcome === pb.outcome && pa.subject === pb.subject
  return false
}

/** The state of one entity's day: five lines, each the latest of its kind. */
export type DayState = {
  entity: string
  actorType: string
  tier: TierId | null
  registered: { by: string; ts: string; approved: boolean } | null
  forecast: { text: string; ts: string; runs: number } | null
  advised: { text: string; ts: string; runs: number } | null
  decided: { by: string; text: string; ts: string; times: number } | null
  checked: { text: string; by: string | null; ts: string } | null
  credited: { text: string; ts: string } | null
}

export function dayStates(records: DecisionRecord[]): DayState[] {
  const groups = new Map<string, DecisionRecord[]>()
  for (const r of records) groups.set(r.entity, [...(groups.get(r.entity) ?? []), r])
  const states: DayState[] = []
  for (const [entity, rows] of groups) {
    const bySeq = [...rows].sort((a, b) => a.seq - b.seq)
    const last = (pred: (r: DecisionRecord) => boolean) => [...bySeq].reverse().find(pred) ?? null
    const count = (pred: (r: DecisionRecord) => boolean) => bySeq.filter(pred).length
    const fc = last((r) => r.kind === 'forecast')
    const ad = last((r) => r.kind === 'advise' && r.payload.subject !== 'plan' && !byPerson(r))
    const de = last((r) => byPerson(r) && (r.kind === 'act' || (r.kind === 'advise' && r.payload.subject === 'plan')))
    const ck = last((r) => r.kind === 'verify' && r.payload.subject !== 'registration')
    const cr = last((r) => r.kind === 'account')
    const en = last((r) => r.kind === 'enrol')
    const approval = last((r) => r.kind === 'verify' && r.payload.subject === 'registration' && r.payload.outcome === 'approved')
    states.push({
      entity,
      actorType: rows[0].actorType,
      tier: fc && isTier(fc.payload.dayTier) ? fc.payload.dayTier : null,
      registered: en ? { by: whoShort(en), ts: en.ts, approved: !!approval || String((en.payload.verifiedBy ?? '')).startsWith('registry') } : null,
      forecast: fc ? { text: forecastText(fc), ts: fc.ts, runs: count((r) => r.kind === 'forecast' && !byPerson(r)) } : null,
      advised: ad ? { text: `${String(ad.payload.audience ?? 'parents')} · ${ad.payload.source === 'agent' ? 'drafted message' : 'standard message'}`, ts: ad.ts, runs: count((r) => r.kind === 'advise' && r.payload.subject !== 'plan' && !byPerson(r)) } : null,
      decided: de ? { by: whoShort(de), text: decidedText(de), ts: de.ts, times: count((r) => byPerson(r) && (r.kind === 'act' || (r.kind === 'advise' && r.payload.subject === 'plan'))) } : null,
      checked: ck ? { text: checkText(ck).replace(/^checked the day: /, ''), by: byPerson(ck) ? whoShort(ck) : null, ts: ck.ts } : null,
      credited: cr ? { text: creditText(cr), ts: cr.ts } : null,
    })
  }
  return orderStates(states)
}

function decidedText(r: DecisionRecord): string {
  const p = r.payload
  if (r.kind === 'advise') return `planned ${(p.cells as unknown[] | undefined)?.length ?? 0} cells: ${actionsText(p.actions)}`
  const as = p.assessment as { coverage?: number; hoursAtRisk?: number } | undefined
  const cov = as && as.hoursAtRisk ? ` · covered ${Math.round((as.coverage ?? 0) * 100)}% of the hours at risk` : ''
  return `${actionsText(p.actions)}${sentVia(p.sentVia).replace(/^, /, ' · ')}${cov}`
}

/** Entities where a person decided first (latest first), then the rest by tier, worst first. */
export function orderStates(states: DayState[]): DayState[] {
  return [...states].sort((a, b) => {
    if (!!a.decided !== !!b.decided) return a.decided ? -1 : 1
    if (a.decided && b.decided) return b.decided.ts.localeCompare(a.decided.ts)
    const ta = a.tier ? TIER_RANK[a.tier] : -1, tb = b.tier ? TIER_RANK[b.tier] : -1
    if (ta !== tb) return tb - ta
    return a.entity.localeCompare(b.entity)
  })
}

/** "2:30–5:50 PM" for a span, "5:50 PM" for a moment. */
export function spanLabel(first: string, last: string): string {
  const a = istClock(first), b = istClock(last)
  return a === b ? b : `${a.replace(/ (AM|PM)$/, '')}–${b}`
}
