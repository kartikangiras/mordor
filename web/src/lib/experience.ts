// The eight steps of the walkthrough: each is introduced by the person who performs it,
// with a mission in our own words, and each ends with a decision that leaves a plain record.
import type { LayerId } from '@/config/layers'

export interface Persona { name: string; title: string; org: string; role: 'analyst' | 'operator' | 'verifier' | 'auditor'; entityId: string | null; colour: string; email: string | null }

export const PERSONAS: Record<string, Persona> = {
  Priya: { name: 'Priya', title: 'Forecast analyst', org: 'Mordor', role: 'analyst', entityId: null, colour: '#818CF8', email: 'priya.demo@example.com' },
  Anita: { name: 'Anita', title: 'Principal', org: 'Kendriya Vidyalaya, Rohini', role: 'operator', entityId: 'osm-way-388242027', colour: '#FB923C', email: 'anita.demo@example.com' },
  'Dr. Mehta': { name: 'Dr. Mehta', title: 'Air-quality officer', org: 'Delhi Pollution Control Committee', role: 'verifier', entityId: null, colour: '#10B981', email: 'mehta.demo@example.com' },
  Gurpreet: { name: 'Gurpreet', title: 'District agriculture officer', org: 'Sangrur', role: 'operator', entityId: 'dao-demo-sangrur', colour: '#F59E0B', email: 'gurpreet.demo@example.com' },
  Rekha: { name: 'Rekha', title: 'RWA secretary', org: 'Rohini Sector 3', role: 'operator', entityId: 'rwa-demo-rohini', colour: '#F472B6', email: 'rekha.demo@example.com' },
  'Ms. Rao': { name: 'Ms. Rao', title: 'Deputy director', org: 'Directorate of Education', role: 'auditor', entityId: null, colour: '#60A5FA', email: 'rao.demo@example.com' },
  'Dr. Kapoor': { name: 'Dr. Kapoor', title: 'Medical superintendent', org: 'District Hospital, Rohini', role: 'operator', entityId: 'hosp-demo-rohini', colour: '#F87171', email: 'kapoor.demo@example.com' },
}

export interface ExpStep {
  id: 'landscape' | 'community' | 'inspection' | 'plan' | 'work' | 'proof' | 'value' | 'health'
  n: number
  title: string
  short: string
  persona: string
  mission: string
  layers: LayerId[]
  zoomDelta: number
  pitch: number
  bearing: number
  hour?: number
}

export const EXP_STEPS: ExpStep[] = [
  { id: 'landscape', n: 1, title: 'The Landscape', short: 'Survey', persona: 'Priya', mission: 'Survey the fields. Find where it is burning tonight, read the vegetation, and pick the area that matters today.', layers: ['fires'], zoomDelta: -0.4, pitch: 55, bearing: -20 },
  { id: 'community', n: 2, title: 'The Community', short: 'Register', persona: 'Anita', mission: 'Your school is downwind. Register it with its hours and its students, so tomorrow\'s forecast becomes a card you can act on.', layers: ['schools', 'actors', 'zones'], zoomDelta: 0.6, pitch: 50, bearing: -30 },
  { id: 'inspection', n: 3, title: 'The Inspection', short: 'Approve', persona: 'Dr. Mehta', mission: 'A registration just came in. Cross-reference the vegetation drop, check the nearest station, and approve it.', layers: ['ndvi', 'burnrisk', 'actors'], zoomDelta: 0, pitch: 45, bearing: 0 },
  { id: 'plan', n: 4, title: 'The Plan', short: 'Plan', persona: 'Gurpreet', mission: 'Read the model for your district, check the weather, and mark the cells that need balers before they burn.', layers: ['plume', 'burnrisk', 'actors'], zoomDelta: 0, pitch: 40, bearing: 15, hour: 20 },
  { id: 'work', n: 5, title: 'The Work', short: 'Act', persona: 'Rekha', mission: 'Tonight the air turns Very Poor. Pause the evening play, switch the gensets off, and tell your residents in one message.', layers: ['plume', 'actors'], zoomDelta: 0.8, pitch: 55, bearing: -25, hour: 20 },
  { id: 'proof', n: 6, title: 'The Check', short: 'Check', persona: 'Dr. Mehta', mission: 'Was it as bad as the card said? Pull the station readings and confirm the outcome, or mark it a false alarm.', layers: ['plume', 'stations', 'actors'], zoomDelta: 0, pitch: 35, bearing: 0, hour: 20 },
  { id: 'value', n: 7, title: 'The Value', short: 'Impact', persona: 'Ms. Rao', mission: 'Credit what was earned: protected student-hours and resident-hours, only for the days the stations confirmed.', layers: ['actors'], zoomDelta: 0, pitch: 30, bearing: 0 },
  { id: 'health', n: 8, title: 'The Ward', short: 'Health', persona: 'Dr. Kapoor', mission: 'Severe air is a medical event. Put the respiratory and emergency wards on alert, check the stock of inhalers and oxygen, and keep beds ready for asthma and COPD cases.', layers: ['plume', 'actors'], zoomDelta: 0.6, pitch: 50, bearing: -20, hour: 20 },
]

export function zoomForRadius(km: number): number {
  return km <= 10 ? 11 : km <= 20 ? 10 : km <= 30 ? 9.2 : km <= 45 ? 8.4 : 7.6
}

const PROGRESS_KEY = 'vd-exp-complete'
export function readProgress(): Record<number, boolean> { try { return JSON.parse(sessionStorage.getItem(PROGRESS_KEY) ?? '{}') } catch { return {} } }
export function writeProgress(p: Record<number, boolean>) { try { sessionStorage.setItem(PROGRESS_KEY, JSON.stringify(p)) } catch { /* private mode */ } }
/** The school the visitor chose in step 2; steps 3 and 7 act on it. */
export type SchoolPick = { id: string; name: string; name_hi?: string | null; lat: number; lon: number }
const WALK_KEY = 'vd-walk'
export function readWalk(): { school: SchoolPick | null } { try { return { school: null, ...JSON.parse(sessionStorage.getItem(WALK_KEY) ?? '{}') } } catch { return { school: null } } }
export function writeWalk(w: { school: SchoolPick | null }) { try { sessionStorage.setItem(WALK_KEY, JSON.stringify(w)) } catch { /* private mode */ } }
/** Steps unlock one at a time: i is open when every step before it is complete. */
export function stepOpen(i: number, complete: Record<number, boolean>): boolean { for (let k = 0; k < i; k++) if (!complete[k]) return false; return true }

/** Said once, where it matters (PIVOT_PLAN.md task 48): the demo entities and people are fictional; the air is real. */
export const DEMO_NOTE = 'Rohini Sector 3 RWA, District Hospital Rohini and the Sangrur office are fictional, and the people who act on them are the seven walkthrough personas; forecasts, stations and schools are real.'
