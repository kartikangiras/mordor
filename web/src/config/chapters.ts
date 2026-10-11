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
  more?: string              // the longer read, under the body
}

/** The first six are the public story (about the air); the last two open the walkthrough (about acting). */
export const STORY_COUNT = 6
export const chapters: Chapter[] = [
  { id: 'burning', title: 'Where it is burning',
    camera: { center: [75.6, 30.6], zoom: 6.6, pitch: 0 }, layers: ['fires'], hour: 0,
    body: "Every October the paddy stubble of Punjab and Haryana burns, and the satellites see it the same night. Every dot is a fire VIIRS saw in the last 24 hours; size is radiative power — how hard it burns.",
    more: "Detections reach the map within three hours of the overpass. VIIRS passes twice a day, so a fire lit and finished between passes is invisible: what you see is a floor, not a count. Each one becomes a source of smoke for the next 48 hours." },
  { id: 'burn-next', title: 'Where it will burn next',
    camera: { center: [74.6, 30.9], zoom: 6.4 }, layers: ['fires', 'burnrisk', 'ndvi'], hour: 0,
    body: "A 48-hour burning-risk score per 27 km cell: recent fires, their trend, what these fields did on these dates in 2024, the drop in crop cover that marks a harvested field, and rain in the forecast.",
    more: "Statistical, not a fire model — it ranks where the next fires are likely, cell by cell, so a district office can send balers and nodal officers before the match is struck rather than after the smoke has left." },
  { id: 'wind', title: 'Where the wind takes it',
    camera: { center: [76.5, 29.6], zoom: 6.2 }, layers: ['fires', 'wind'], hour: 0,
    body: "Winds at 925 hPa, the level the smoke actually travels in — roughly 750 m up, above the night-time inversion that holds the ground air still.",
    more: "Each fire becomes parcels of smoke carried by this wind for 48 hours; the arrows point downwind. When they turn south-east over Haryana, Delhi's next day is already written — the smoke takes a night to arrive." },
  { id: 'arrival', title: 'When it reaches you',
    camera: { center: [77.1, 28.7], zoom: 8.2 }, layers: ['fires', 'wind', 'plume'], hour: 0, autoplay: true,
    body: "Drag the slider. Hour by hour, on a 5 km grid, this is how much the fires add on top of the background already in the air — and when it arrives.",
    more: "This increment is what we forecast and the only thing we claim skill on; the background comes from CAMS and is consumed as is. The band around every value is a split-conformal interval fitted on held-out days, so a principal sees how sure the number is." },
  { id: 'zones', title: 'Which cities, and how much is the fires',
    camera: { center: [76.3, 29.9], zoom: 6.2 }, layers: ['plume', 'zones'], hour: 3,
    body: "Seventeen cities ranked by the air they get. For each: the CAMS background, which already holds traffic and industry, our stubble increment on top, and NO2 as the traffic tracer. Shown a few hours in, when the night layer holds the smoke down.",
    more: "The share tells you how much of tomorrow is the fires and how much is the city itself — and the two need different decisions. Drag the slider and watch the share change through the night." },
  { id: 'underneath', title: 'Who is underneath it',
    camera: { center: [77.15, 28.68], zoom: 10.5 }, layers: ['plume', 'schools'], hour: 20,
    body: "Every school in Delhi, coloured by what tomorrow does to it during school hours and the pickup. Click one.",
    more: "The forecast is read at each school through its hours of concern and turned into a tier a principal can act on — normal, caution, indoors, restrict, closure advisory — anchored to CAQM's GRAP stages. The same is done for residents' associations, district offices and hospitals." },
  { id: 'decision', title: 'What the school does about it',
    camera: { center: [77.11, 28.71], zoom: 13 }, layers: ['plume', 'schools', 'actors'], hour: 20, showProtocolCard: true,
    body: "This is the screen the principal sees at 6:30 am. The RWA secretary, the district agriculture officer and the hospital's medical superintendent each get their own.",
    more: "Register, read the card, choose the actions, send the message: each step a person takes leaves a plain record with a name and a time, readable by anyone — and an assessment of what the chosen actions protect." },
  { id: 'lifecycle', title: 'What happens after the forecast',
    camera: { center: [77.11, 28.71], zoom: 12 }, layers: ['plume', 'actors'], hour: 20, showRecords: true,
    body: "Every card leaves a plain record: the forecast, the advice that went out, what the principal or secretary actually did, what the nearest station then measured, and what that protected.",
    more: "Every run is scored against the monitors the next day; the fit, its errors and the interval sit on the validation page and in the footer of every card, bad days included. Impact is credited only when the station confirmed the day — a false alarm credits nothing." },
]
