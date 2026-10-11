// Declarative story chapters (DESIGN.md §9.3). Navigation ships in M9; the data lives here now
// so the map and the chapters can never disagree about camera or hour.
import type { LayerId } from './layers'

export interface Chapter {
  id: string
  title: string
  camera: { center: [number, number]; zoom: number; pitch?: number }
  layers: LayerId[]
  hour: number
  autoplay?: boolean
  showProtocolCard?: boolean
  showRecords?: boolean
  body: string
}

/** The first six are the public story (about the air); the last two open the walkthrough (about acting). */
export const STORY_COUNT = 6
export const chapters: Chapter[] = [
  { id: 'burning', title: 'Where it is burning',
    camera: { center: [75.6, 30.6], zoom: 6.6, pitch: 0 }, layers: ['fires'], hour: 0,
    body: 'Every dot is a fire VIIRS saw in the last 24 hours across Punjab and Haryana. Size is radiative power.' },
  { id: 'burn-next', title: 'Where it will burn next',
    camera: { center: [74.6, 30.9], zoom: 6.4 }, layers: ['fires', 'burnrisk', 'ndvi'], hour: 0,
    body: 'A 48-hour burning-risk score per 27 km cell: recent fires, trend, what these fields did on these dates in 2024, the NDVI drop that marks a harvested field, and rain in the forecast. Statistical, not a fire model.' },
  { id: 'wind', title: 'Where the wind takes it',
    camera: { center: [76.5, 29.6], zoom: 6.2 }, layers: ['fires', 'wind'], hour: 0,
    body: 'Winds at 925 hPa, the level the smoke actually travels in.' },
  { id: 'arrival', title: 'When it reaches you',
    camera: { center: [77.1, 28.7], zoom: 8.2 }, layers: ['fires', 'wind', 'plume'], hour: 0, autoplay: true,
    body: 'Drag the slider. This is the stubble increment only — the background is already in the air.' },
  { id: 'zones', title: 'Which cities, and how much is the fires',
    camera: { center: [76.3, 29.9], zoom: 6.2 }, layers: ['plume', 'zones'], hour: 3,
    body: 'Seventeen cities ranked by the air they get. For each: the CAMS background, which already holds traffic and industry, our stubble increment on top, and NO2 as the traffic tracer. Shown a few hours in, when the night layer holds the smoke down. Drag the slider and watch the share change.' },
  { id: 'underneath', title: 'Who is underneath it',
    camera: { center: [77.15, 28.68], zoom: 10.5 }, layers: ['plume', 'schools'], hour: 20,
    body: 'Every school in Delhi, coloured by what tomorrow does to it. Click one.' },
  { id: 'decision', title: 'What the school does about it',
    camera: { center: [77.11, 28.71], zoom: 13 }, layers: ['plume', 'schools', 'actors'], hour: 20, showProtocolCard: true,
    body: 'This is the screen the principal sees at 6:30 am. The RWA secretary and the district agriculture officer each get their own.' },
  { id: 'lifecycle', title: 'What happens after the forecast',
    camera: { center: [77.11, 28.71], zoom: 12 }, layers: ['plume', 'actors'], hour: 20, showRecords: true,
    body: 'Every card leaves a plain record: the forecast, the advice that went out, what the principal or secretary actually did, what the nearest station then measured, and what that protected. Impact is credited only when the day was really that bad. Anyone can read the log.' },
]
