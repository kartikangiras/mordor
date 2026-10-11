// Types for the principal card (DESIGN.md §8 GET /api/schools/{id}/forecast, §9.5).
import type { TierId } from './aqi'

export type Window = { fromIst: string; toIst: string; tier: TierId; peakAqi: number | null }
/** Split-conformal band around the peak hour of concern (services/protocol/interval.py). */
export type Interval = { hourIst: string; pm25: number; pm25Lo: number; pm25Hi: number; aqi: number; aqiLo: number; aqiHi: number; halfWidth: number | null; level: string; basis: string }
/** Inhaled PM2.5 mass over the hours the card covers. Outdoor air, no infiltration assumed. */
export type Dose = { totalUg: number; schoolHoursUg: number; dismissalUg: number; dismissalShare: number | null; hours: number; worstHour: { hourIst: string; pm25: number; activity: string; ug: number }; worstHourShare: number | null; breathingRatesM3PerH: Record<string, number>; basis: string }
export type Protocol = { outdoor: string; windows: string; masks: string; assembly: string; grapAnchor: string; advisory?: string }
export type Message = { hi: string; en: string; chars: number; source: 'agent' | 'template' | 'cache'; cached?: boolean }
export type HourlyRow = { t: string; pm25Background: number; pm25Fire?: number; pm25Total?: number; aqi?: number; tier?: TierId; pm25Lo?: number; pm25Hi?: number; aqiLo?: number; aqiHi?: number; halfWidth?: number | null }
export type LogEntry = { runId: string; date: string; dayTier: TierId | null; actions: string[]; sentVia: string | null; ackedAt: string; shownAt: string }

export type ActorKind = 'exposure' | 'source'
export type ActorTypeId = 'school' | 'rwa' | 'agri_officer'
export type RiskCell = { i: number; j: number; name: string; fires24: number; fires48: number; frp24: number; trend: number; ndviChange: number | null; rain48mm: number | null; score: number; category: string; lat: number; lon: number; distanceKm: number }

export interface Card {
  actorType?: ActorTypeId
  kind?: ActorKind
  actions?: { id: string; label: string; hi: string }[]
  anchor?: string
  cells?: RiskCell[]
  burningNow?: number
  audience?: string
  people?: number | null
  impactUnit?: string
  district?: string
  strip?: [string, string]
  school: { id: string; name: string; name_hi?: string | null; lat: number; lon: number; hours?: [string, string]; dismissal?: [string, string]; hasPurifiers: boolean; email?: string | null; students?: number | null; type?: ActorTypeId; typeLabel?: string; personTitle?: string; residents?: number | null; machines?: number | null; district?: string | null; persona?: string | null }
  runId: string
  date: string | null
  hourly: HourlyRow[]
  dayTier: TierId | null
  windows: Window[]
  protocol: Protocol | null
  headline: string
  defaultActions: string[]
  peakAqi: number | null
  outdoorHoursCancelled: number
  message: Message
  calibration?: { k: number | null; status: string; r2: number | null; mae: number | null; window: string | null; stations: number | null; conformal?: { q80?: number; q90?: number; n?: number; basis?: string } | null } | null
  interval?: Interval | null
  dose?: Dose | null
  log: LogEntry[]
  acked: LogEntry | null
}

/** Public, contact-free card the pipeline publishes for demo/onboarded schools (chapter 5, /school/:id). */
export type PublicCard = Omit<Card, 'school' | 'message' | 'log' | 'acked'> & { schoolId: string; entityId?: string; actorLabel?: string; personTitle?: string; persona?: string | null; name: string; name_hi?: string | null; message?: Message; demo: boolean; onboarded: boolean; schoolHoursIst?: [string, string]; dismissalIst?: [string, string]; hasPurifiers?: boolean }

export const ACTIONS: { id: string; label: string; hi: string }[] = [
  { id: 'pt_indoors', label: 'Outdoor PT and games moved indoors', hi: 'खेल-कूद अंदर' },
  { id: 'windows_shut', label: 'Windows shut', hi: 'खिड़कियाँ बंद' },
  { id: 'masks', label: 'Masks offered / distributed', hi: 'मास्क' },
  { id: 'assembly_indoor', label: 'Assembly indoors or cancelled', hi: 'सभा अंदर' },
]

export function waLink(m: Message): string {
  return `https://wa.me/?text=${encodeURIComponent(`${m.hi}\n\n${m.en}`)}`
}

/** Plain decision records (DESIGN.md §13.5): what was forecast, advised, done, measured, and protected. */
export type RecordKind = 'enrol' | 'forecast' | 'advise' | 'act' | 'verify' | 'account'
export const RECORD_STEPS: { kind: RecordKind; label: string; who: string }[] = [
  { kind: 'enrol', label: 'Register', who: 'operator' },
  { kind: 'forecast', label: 'Forecast', who: 'analyst' },
  { kind: 'advise', label: 'Advise', who: 'analyst' },
  { kind: 'act', label: 'Act', who: 'operator' },
  { kind: 'verify', label: 'Check', who: 'air-quality officer' },
  { kind: 'account', label: 'Impact', who: 'analyst' },
]
export type DecisionRecord = { id: string; schema: string; kind: RecordKind; entity: string; actorType: string; seq: number; ts: string; date: string; runId: string | null; by: { role: string; name?: string; sub?: string; persona?: string | null }; payload: Record<string, unknown> }
export type EntityRecords = { entity: string; records: DecisionRecord[]; steps: RecordKind[]; labels: Record<RecordKind, string> }
export type RecordsIndex = { date: string; records: DecisionRecord[] }

/** One readable line per record, shared by the day log, the chapter panel and the experience. */
export function recordDetail(r: DecisionRecord): string {
  const p = r.payload
  const s = (k: string) => (p[k] === undefined || p[k] === null ? '—' : String(p[k]))
  switch (r.kind) {
    case 'enrol': return `${s('type')} · ${s('people')} people · ${p.subject === 'registration' && p.approved ? 'approved' : 'registered'}`
    case 'forecast': return `tier ${s('dayTier')} · peak AQI ${s('peakAqi')} · ${s('headline')}`
    case 'advise': return p.subject === 'plan' ? `plan · ${(p.cells as unknown[] | undefined)?.length ?? 0} cells · ${(p.actions as string[] | undefined)?.join(', ') ?? ''}` : `${s('source')} message to ${s('audience')} · ${s('chars')} chars`
    case 'act': return `${(p.actions as string[] | undefined)?.join(', ') || 'no actions'} · via ${s('sentVia')}`
    case 'verify': return `${s('outcome')}${p.evidence ? ` · ${s('evidence')}` : p.reason ? ` · ${s('reason')}` : ''}`
    case 'account': return `${s('value')} ${s('unit')} · ${s('status')}`
  }
}
export type RolesInfo = { roles: Record<string, string>; actorTypes: Record<string, { label: string; kind: ActorKind; personTitle: string; anchor: string; impactUnit: string }>; personas: { name: string; role: string; title: string; org: string; entityId: string | null }[]; note: string }
export type PendingVerification = { entityId: string; name: string; type: string; date: string; dayTier: string | null; acted: boolean; actions: string[] | null; status: string; reason: string | null }
