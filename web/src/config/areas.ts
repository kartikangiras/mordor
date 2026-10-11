// Preset areas for the guided experience (DESIGN.md §9.7): the 17 exposure zones plus the
// districts that burn. A visitor can also type coordinates. Radius is what "the area" means
// for every per-area number: fires, cells, actors and zones within it.
export interface Area { id: string; name: string; lat: number; lon: number; radiusKm: number; kind: 'city' | 'district'; region: string }

export const AREAS: Area[] = [
  { id: 'delhi', name: 'Delhi', lat: 28.61, lon: 77.21, radiusKm: 30, kind: 'city', region: 'Delhi' },
  { id: 'rohini', name: 'Rohini, Delhi', lat: 28.71, lon: 77.11, radiusKm: 8, kind: 'city', region: 'Delhi' },
  { id: 'gurugram', name: 'Gurugram', lat: 28.46, lon: 77.03, radiusKm: 15, kind: 'city', region: 'Haryana' },
  { id: 'noida', name: 'Noida · Ghaziabad', lat: 28.62, lon: 77.38, radiusKm: 15, kind: 'city', region: 'Uttar Pradesh' },
  { id: 'chandigarh', name: 'Chandigarh', lat: 30.73, lon: 76.78, radiusKm: 20, kind: 'city', region: 'Chandigarh' },
  { id: 'ludhiana', name: 'Ludhiana', lat: 30.90, lon: 75.86, radiusKm: 25, kind: 'city', region: 'Punjab' },
  { id: 'amritsar', name: 'Amritsar', lat: 31.63, lon: 74.87, radiusKm: 25, kind: 'city', region: 'Punjab' },
  { id: 'sangrur', name: 'Sangrur district', lat: 30.25, lon: 75.84, radiusKm: 45, kind: 'district', region: 'Punjab' },
  { id: 'patiala', name: 'Patiala district', lat: 30.34, lon: 76.39, radiusKm: 40, kind: 'district', region: 'Punjab' },
  { id: 'moga', name: 'Moga · Faridkot', lat: 30.75, lon: 75.0, radiusKm: 40, kind: 'district', region: 'Punjab' },
  { id: 'bathinda', name: 'Bathinda · Mansa', lat: 30.1, lon: 75.15, radiusKm: 40, kind: 'district', region: 'Punjab' },
  { id: 'tarntaran', name: 'Tarn Taran · Firozpur', lat: 31.2, lon: 74.8, radiusKm: 40, kind: 'district', region: 'Punjab' },
  { id: 'karnal', name: 'Karnal · Kaithal', lat: 29.75, lon: 76.7, radiusKm: 40, kind: 'district', region: 'Haryana' },
  { id: 'sirsa', name: 'Sirsa · Fatehabad', lat: 29.52, lon: 75.25, radiusKm: 40, kind: 'district', region: 'Haryana' },
]

export const PERSONA_DEFAULT_AREA: Record<string, string> = { Priya: 'sangrur', Anita: 'rohini', Rekha: 'rohini', Gurpreet: 'sangrur', 'Dr. Mehta': 'delhi', 'Ms. Rao': 'delhi' }
