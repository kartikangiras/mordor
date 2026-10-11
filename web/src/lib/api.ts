// Three fetches, no data library (DESIGN.md §9). Relative URLs in the manifest are resolved
// against VITE_CDN_BASE so the same manifest works on CloudFront and on the vite dev server.
import type { FeatureCollection, Point } from 'geojson'

export interface Manifest {
  runId: string
  generatedAt: string
  domain: [number, number, number, number]
  imageCorners: [[number, number], [number, number], [number, number], [number, number]]
  hours: string[]
  overlayUrl: string
  gridUrl: string
  firesUrl: string
  backgroundUrl?: string
  schoolsUrl?: string
  windUrl?: string
  zonesUrl?: string
  burningUrl?: string
  ndvi?: { layer: string; date: string; prevDate: string; tileTemplate: string; colormapEntries: number } | null
  protocolUrl?: string
  demoSchools?: string[]
  entitiesUrl?: string
  entities?: { count: number; byType: Record<string, number>; ids: string[] } | null
  schools?: { count: number; named: number; calibrated: boolean; byTier: Record<string, number>; dayDate: string | null } | null
  overlay: { mode: 'cpcb' | 'relative'; vmax: number; units: string; note?: string; low?: string; high?: string; stops?: { from: number; colour: string }[] }
  calibration: { k: number | null; tauHours: number; kH: number; seed: number; status: string; r2: number | null; mae: number | null; bias?: number | null; window: string | null; stations: number | null; windLevel?: string | null }
  stats: Record<string, unknown>
  fires: { count: number; window: string; source: string }
  disclaimer: string
}

export type FireProps = { frp: number; confidence: string; satellite: string; daynight: string; acqUtc: string; source: string }

export type DaySummary = { date: string; tier: string | null; peakAqi: number | null; peakHourIst: string | null }
export type SchoolProps = { id: string; name: string; name_hi?: string | null; dayTier: string | null; dayDate: string | null; peakAqi: number | null; peakHourIst: string | null; days: DaySummary[]; demo?: boolean; onboarded?: boolean }
export type SchoolsLayer = FeatureCollection<Point, SchoolProps> & { runId: string; calibrated: boolean; schoolHoursIst: [string, string]; dismissalIst: [string, string] }
export type Background = { lats: number[]; lons: number[]; hours: string[]; units: string; source: string; pm25: number[][][] }
export type GridHour = { t: string; hour: number; units: string; shape: [number, number]; max: number; values: number[] }

const CDN = (import.meta.env.VITE_CDN_BASE ?? '').replace(/\/$/, '')
const API = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

export function cdnUrl(relative: string): string {
  if (/^https?:/.test(relative)) return relative
  return `${CDN}/${relative.replace(/^\//, '')}`
}

export function overlayUrl(m: Manifest, hour: number): string {
  return cdnUrl(m.overlayUrl.replace('{hh}', String(hour).padStart(2, '0')))
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url, { cache: 'no-cache' })
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`)
  return r.json() as Promise<T>
}

export async function getLatest(): Promise<Manifest> {
  if (API) {
    try { return await getJson<Manifest>(`${API}/latest`) } catch (e) { console.warn('api/latest failed, falling back to CDN', e) }
  }
  const ptr = await getJson<{ runId: string }>(cdnUrl('runs/latest.json'))
  return getJson<Manifest>(cdnUrl(`runs/${ptr.runId}/manifest.json`))
}

export function getFires(m: Manifest): Promise<FeatureCollection<Point, FireProps>> {
  return getJson(cdnUrl(m.firesUrl))
}

export function getSchools(m: Manifest): Promise<SchoolsLayer | null> {
  return m.schoolsUrl ? getJson<SchoolsLayer>(cdnUrl(m.schoolsUrl)) : Promise.resolve(null)
}

export function getBackground(m: Manifest): Promise<Background | null> {
  return m.backgroundUrl ? getJson<Background>(cdnUrl(m.backgroundUrl)) : Promise.resolve(null)
}

export type WindSeries = { lats: number[]; lons: number[]; hours: string[]; units: string; u: number[][][]; v: number[][][] }
/** `tier` separates regulatory monitors from low-cost sensor networks; the map and the popup
 *  must say which one a reading came from (see services/ingest_cpcb/openaq_live.py). */
export type StationTier = 'reference' | 'low_cost'
export type StationSnapshot = { fetchedAt: string | null; sources?: { dataGovIn?: { ok: boolean; error?: string }; openaq?: { stations?: number; providers?: Record<string, number> } }; stations: { id: string; name: string; city: string; lat: number; lon: number; pm25: number; pm10?: number | null; observedAt: string; isStale: boolean; tier?: StationTier; provider?: string | null; source?: string }[] }

export type ZoneNow = { pm25Background: number; pm25Fire: number | null; pm25Total: number | null; aqi: number; tier: string; no2: number | null; no2Band: string | null }
export type ZonePeak = ZoneNow & { hour: number; t: string; stubbleShare: number | null }
export type Zone = { id: string; name: string; name_hi: string; lat: number; lon: number; radiusKm: number; population: number; region: string; calibrated: boolean
  now: ZoneNow; peak: ZonePeak; arrivalHour: number | null; arrivalT: string | null; worstTier: string
  hourly: { pm25Fire: number[] | null; pm25Background: number[]; no2: number[] | null } }
export type ZonesFile = { runId: string; hours: string[]; calibrated: boolean; arrivalThreshold: number; note: string; rankingNow: string[]; rankingPeak: string[]; zones: Zone[] }
export type BurnProps = { i: number; j: number; name: string; fires24: number; fires48: number; frp24: number; trend: number; climatologyPerDay: number | null; ndviChange: number | null; rain48mm: number | null; score: number; category: 'Low' | 'Moderate' | 'High' | 'Extreme'; components: { recent: number; trend: number; season: number; vegetation: number; rain: number } }
export type BurningFile = FeatureCollection<import('geojson').Polygon, BurnProps> & { generatedFor: string; cellDeg: number; method: string; inputs: Record<string, number | boolean>; topBurning: (BurnProps & { lat: number; lon: number })[]; topRisk: Omit<BurnProps, 'components'>[]; ndvi?: { layer: string; date: string; prevDate: string; tileTemplate: string } }

export type ActorProps = { id: string; name: string; name_hi?: string | null; type: 'school' | 'rwa' | 'agri_officer' | 'hospital'; kind: 'exposure' | 'source'; typeLabel: string; personTitle: string; persona?: string | null; dayTier: string | null; date: string | null; headline: string; peakAqi: number | null; cells: number; burningNow: number | null; demo: boolean; onboarded: boolean; radiusKm?: number | null }
export type EntitiesFile = FeatureCollection<Point, ActorProps> & { runId: string }
export function getEntities(m: Manifest): Promise<EntitiesFile | null> {
  return m.entitiesUrl ? getJson<EntitiesFile>(cdnUrl(m.entitiesUrl)).catch(() => null) : Promise.resolve(null)
}

export function getZones(m: Manifest): Promise<ZonesFile | null> {
  return m.zonesUrl ? getJson<ZonesFile>(cdnUrl(m.zonesUrl)).catch(() => null) : Promise.resolve(null)
}
export function getBurning(m: Manifest): Promise<BurningFile | null> {
  return m.burningUrl ? getJson<BurningFile>(cdnUrl(m.burningUrl)).catch(() => null) : Promise.resolve(null)
}

export function getWind(m: Manifest): Promise<WindSeries | null> {
  return m.windUrl ? getJson<WindSeries>(cdnUrl(m.windUrl)) : Promise.resolve(null)
}

export function getStations(): Promise<StationSnapshot | null> {
  return API ? getJson<StationSnapshot>(`${API}/stations/latest`).catch(() => null) : Promise.resolve(null)
}

/** Tomorrow's card for any mapped school, built by the API from the run (no file on the CDN needed). */
export const getSchoolCard = (id: string) => authed<import('./protocol').PublicCard>(`/schools/${encodeURIComponent(id)}/card`, { method: 'GET' }, {}).catch(() => null)
export function getPublicCard(m: Manifest, schoolId: string): Promise<import('./protocol').PublicCard | null> {
  return m.protocolUrl ? getJson<import('./protocol').PublicCard>(cdnUrl(m.protocolUrl.replace('{schoolId}', schoolId))).catch(() => null) : Promise.resolve(null)
}

export function getValidation(): Promise<ValidationReport> {
  if (API) return getJson<ValidationReport>(`${API}/validation`).catch(() => getJson<ValidationReport>(cdnUrl('validation/latest/report.json')))
  return getJson<ValidationReport>(cdnUrl('validation/latest/report.json'))
}

export type Metrics = { n: number; r2: number | null; mae: number | null; bias: number | null; corr: number | null }
export type Eval = { model: Metrics; camsOnly: Metrics; incrementCorr?: number | null }
export interface ValidationReport {
  experimentId: string; k: number; kAnomaly?: number; r2: number | null; mae: number | null; bias: number | null; window: string; fitDays: number; testDays: number
  stations: number; stationsDelhi: number; windLevel: string; fires: string; fittedAt: string; disclaimer: string
  metrics: { fit: Eval; test: Eval; byLead: Record<string, Eval>; hitRate: { hits: number; misses: number; falseAlarms: number; correctNegatives: number; pod: number | null; far: number | null; accuracy: number | null; threshold: string; informative?: boolean }; peakTiming: { events: number; meanAbsHours: number | null; medianAbsHours: number | null } }
  perStation: { id: number; name: string; lat: number; lon: number; delhi: boolean; distanceToDelhiKm: number; n: number; r2: number | null; mae: number | null; bias: number | null; corr: number | null; camsOnlyMae: number | null; camsOnlyR2: number | null }[]
  scatter: [number, number][]
  episodes: { id: number; name: string; t: string[]; obs: number[]; bg: number[]; pred: number[]; fire: number[] }[]
  narrative: { right: string; wrong: string }
  runs: { day: string; fires: number; particles: number; seconds: number }[]
}

// ---- principal (auth headers from lib/auth) ---------------------------------------------------
async function authed<T>(path: string, init: RequestInit, headers: Record<string, string>): Promise<T> {
  const r = await fetch(`${API || '/api'}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...headers, ...(init.headers as Record<string, string> | undefined) } })
  const body = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(body?.error?.message ?? `HTTP ${r.status}`)
  return body as T
}
export const getMyForecast = (h: Record<string, string>, entity?: string) => authed<import('./protocol').Card>(`/me/forecast${entity ? `?entity=${encodeURIComponent(entity)}` : ''}`, { method: 'GET' }, h)
export const postAck = (schoolId: string, body: { runId: string; actions: string[]; sentVia: string | null }, h: Record<string, string>) =>
  authed<{ ok: boolean; log: import('./protocol').LogEntry; message: import('./protocol').Message; record?: import('./protocol').DecisionRecord }>(`/actors/${encodeURIComponent(schoolId)}/ack`, { method: 'POST', body: JSON.stringify(body) }, h)
export const postEmail = (runId: string, h: Record<string, string>) => authed<{ ok: boolean; to: string }>('/me/email', { method: 'POST', body: JSON.stringify({ runId }) }, h)
export const getGuidelines = () => authed<{ tiers: import('@/config/publicGuidelines').Guidelines; anchor: string; note: string }>('/guidelines', { method: 'GET' }, {}).then((g) => g.tiers).catch(() => null)
export const getRoles = () => authed<import('./protocol').RolesInfo>('/roles', { method: 'GET' }, {})
export const getEntityRecords = (entity: string) => authed<import('./protocol').EntityRecords>(`/records/${encodeURIComponent(entity)}`, { method: 'GET' }, {})
export const getRecordsIndex = (date?: string) => authed<import('./protocol').RecordsIndex>(`/records${date ? `?date=${date}` : ''}`, { method: 'GET' }, {})
export const getPending = (h: Record<string, string>) => authed<{ role: string; pending: import('./protocol').PendingVerification[] }>('/verifier/pending', { method: 'GET' }, h)
export const postConfirm = (body: { entityId: string; date: string; outcome: string; evidence: string; observedPeakPm25?: number | null }, h: Record<string, string>) => authed<{ ok: boolean; record: import('./protocol').DecisionRecord }>('/verifier/confirm', { method: 'POST', body: JSON.stringify(body) }, h)
export type ImpactReport = { date: string; schools: number; students: number; studentsProtected?: number; peopleProtected?: number; plan?: { offices: number; cells: number; areaKm2: number; radiusKm: number }; hospitalsAlerted?: number; bedsReady?: number; people: number; byType: Record<string, number>; outdoorHoursAvoided: number; decisionsLogged: number; records: { impactStatements: number; verified: number; provisional: number; notCredited: number; verifiedByUnit: Record<string, number> }; method: string }
export const getImpact = (date?: string) => authed<ImpactReport>(`/impact${date ? `?date=${date}` : ''}`, { method: 'GET' }, {})
export type InspectReport = { entityId: string; name: string; type: string; station: { id: number; name: string; distanceKm: number } | null; nearestCell: (BurnProps & { distanceKm: number }) | null; hours: [string, string] | null; dismissal: [string, string] | null; registration: import('./protocol').DecisionRecord | null; approval: import('./protocol').DecisionRecord | null }
export type ObserveReport = { entityId: string; date: string | null; station: { id: number; name: string; distanceKm: number } | null; outcome: string; hoursObserved: number; reason?: string; observed?: { peakPm25: number; peakAqi: number; tier: string; hoursAtT2plus: number; hoursObserved: number } | null; forecast?: { tier: string | null; peakAqi: number | null } }
export const postRegister = (body: { entityId: string }, h: Record<string, string>) => authed<{ ok: boolean; record: import('./protocol').DecisionRecord; existing: boolean }>('/actors/register', { method: 'POST', body: JSON.stringify(body) }, h)
export const getInspect = (entityId: string, h: Record<string, string>) => authed<InspectReport>(`/verifier/inspect/${encodeURIComponent(entityId)}`, { method: 'GET' }, h)
export const postApprove = (body: { entityId: string; checks: string[]; note?: string }, h: Record<string, string>) => authed<{ ok: boolean; record: import('./protocol').DecisionRecord }>('/verifier/approve', { method: 'POST', body: JSON.stringify(body) }, h)
export const postPlan = (entityId: string, body: { runId: string; cells: unknown[]; hoursToProtect: unknown[]; actions: string[]; weather?: unknown }, h: Record<string, string>) => authed<{ ok: boolean; record: import('./protocol').DecisionRecord }>(`/actors/${encodeURIComponent(entityId)}/plan`, { method: 'POST', body: JSON.stringify(body) }, h)
export const getObserve = (entityId: string, h: Record<string, string>, date?: string) => authed<ObserveReport>(`/verifier/observe/${encodeURIComponent(entityId)}${date ? `?date=${date}` : ''}`, { method: 'GET' }, h)
export const postAccount = (body: { entityId: string; date: string }, h: Record<string, string>) => authed<{ ok: boolean; record: import('./protocol').DecisionRecord }>('/records/account', { method: 'POST', body: JSON.stringify(body) }, h)
export type Assessment = { kind: 'exposure' | 'source'; actorType: string; tier: string | null; peakAqi: number | null; date: string | null; coverage: number; people: number; unit: string; chosen: string[]; missing: { id: string; label: string; weight: number }[]; hoursAtRisk?: number; protectedHours?: number; exposedHours?: number; cellsAtRisk?: number; cellsActioned?: number; value: number; narrative: { en: string; source: 'agent' | 'template' } }
export const postAssess = (entityId: string, body: { runId: string; actions: string[] }, h: Record<string, string>) => authed<Assessment>(`/actors/${encodeURIComponent(entityId)}/assess`, { method: 'POST', body: JSON.stringify(body) }, h)
export const getMe = (h: Record<string, string>) => authed<{ schoolId: string | null; entityId: string | null; role: string; roleDescription: string; email: string | null; dev: boolean; runId: string; school: import('./protocol').Card['school'] | null }>('/me', { method: 'GET' }, h)

export function getGridHour(m: Manifest, hour: number): Promise<GridHour> {
  return getJson<GridHour>(cdnUrl(m.gridUrl.replace('{hh}', String(hour).padStart(2, '0'))))
}
