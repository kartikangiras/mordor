import type { LayerSpecification, StyleSpecification } from 'maplibre-gl'
import streets from './streets.json'

export const LAYER_IDS = {
  plume: 'plume',
  fires: 'fires',
  wind: 'wind',
  stations: 'stations',
  schools: 'schools',
  zones: 'zones',
  burnrisk: 'burnrisk',
  ndvi: 'ndvi',
  actors: 'actors',
} as const
export type LayerId = keyof typeof LAYER_IDS

// Keyless sources that make the fallback basemap rich (DESIGN.md §4.6): full-colour imagery drawn at
// twice the detail, OpenFreeMap vector tiles for crisp roads, boundaries and labels (OpenStreetMap data,
// OpenMapTiles schema), and the AWS Open Data terrain tiles (Terrarium encoding) for relief and 3D.
export const IMAGERY_TILES = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
export const TERRAIN_TILES = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'
export const VECTOR_TILEJSON = 'https://tiles.openfreemap.org/planet'
export const GLYPHS = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf'
export const SPRITE = 'https://tiles.openfreemap.org/sprites/ofm_f384/ofm'

/** Amazon Location Service style when configured (DESIGN.md §4.6); otherwise the rich keyless
 *  fallback: imagery + vector streets and labels + terrain DEM (used for hillshade and 3D). */
export function basemapStyle(): string | StyleSpecification {
  const env = import.meta.env
  if (env.VITE_LOCATION_STYLE_URL) return env.VITE_LOCATION_STYLE_URL
  if (env.VITE_LOCATION_API_KEY) {
    const region = env.VITE_AWS_REGION || 'us-east-1'
    const style = env.VITE_LOCATION_STYLE || 'Satellite'
    return `https://maps.geo.${region}.amazonaws.com/v2/styles/${style}/descriptor?key=${env.VITE_LOCATION_API_KEY}`
  }
  return {
    version: 8,
    glyphs: GLYPHS,
    sprite: SPRITE,
    sources: {
      // 256 px tiles declared at 128 px: the map fetches one zoom level deeper, so the imagery is sharp on every screen
      imagery: { type: 'raster', tiles: [IMAGERY_TILES], tileSize: 128, maxzoom: 18, attribution: 'Imagery © Esri, Maxar, Earthstar Geographics' },
      openmaptiles: { type: 'vector', url: VECTOR_TILEJSON },
      dem: { type: 'raster-dem', tiles: [TERRAIN_TILES], tileSize: 256, maxzoom: 15, encoding: 'terrarium', attribution: 'Terrain: AWS Open Data / Mapzen' },
      demShade: { type: 'raster-dem', tiles: [TERRAIN_TILES], tileSize: 256, maxzoom: 15, encoding: 'terrarium' },
    },
    layers: [
      { id: 'basemap', type: 'raster', source: 'imagery', paint: { 'raster-saturation': -0.08, 'raster-brightness-max': 0.92, 'raster-contrast': 0.08, 'raster-resampling': 'linear' } },
      { id: 'hillshade', type: 'hillshade', source: 'demShade', paint: { 'hillshade-exaggeration': 0.45, 'hillshade-shadow-color': '#05060a', 'hillshade-highlight-color': 'rgba(255,255,255,0.14)', 'hillshade-accent-color': '#1a1410' } },
      ...(streets.layers as LayerSpecification[]),
    ],
    terrain: { source: 'dem', exaggeration: 1.3 },
    light: { anchor: 'viewport', color: '#ffffff', intensity: 0.45, position: [1.15, 210, 30] },
    sky: { 'sky-color': '#0b1020', 'horizon-color': '#2a2320', 'fog-color': '#0b0d10', 'fog-ground-blend': 0.6, 'horizon-fog-blend': 0.7, 'sky-horizon-blend': 0.6, 'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 8, 0.6, 12, 0.2] },
  }
}

export const INITIAL_VIEW = { center: [77.15, 28.72] as [number, number], zoom: 8.3 }   // Delhi; the fires are one zoom-out away

/** The landing's slow camera path across the domain: the fields, the corridor, the city. */
export const LANDING_WAYPOINTS: { center: [number, number]; zoom: number; pitch: number; bearing: number }[] = [
  { center: [75.4, 30.6], zoom: 8.8, pitch: 42, bearing: -20 },   // Punjab fields
  { center: [76.6, 29.7], zoom: 8.4, pitch: 40, bearing: 10 },    // the corridor through Haryana
  { center: [77.18, 28.64], zoom: 10.6, pitch: 48, bearing: -35 }, // Delhi
  { center: [76.4, 30.3], zoom: 9.0, pitch: 44, bearing: 25 },    // Patiala fields
]

/** What a viewer calls each layer (PIVOT_PLAN.md P19): no vendor or model words on a public surface. */
export const LAYER_WORDS: Record<LayerId, string> = { plume: 'smoke', fires: 'fires', wind: 'wind', stations: 'stations', schools: 'schools', actors: 'people', zones: 'zones', burnrisk: 'burn risk', ndvi: 'crop cover' }
