// Layer 2: arrows on the 0.5° grid, rotated by bearing and scaled by speed (DESIGN.md §9.2).
// Static arrows; animated particles are a stretch goal (FUTURE.md).
import { useEffect } from 'react'
import type maplibregl from 'maplibre-gl'
import type { GeoJSONSource } from 'maplibre-gl'
import type { FeatureCollection, Point } from 'geojson'
import { LAYER_IDS } from '@/config/layers'
import { mapAlive } from '@/lib/maputil'
import { useStore } from '@/lib/store'

const ID = LAYER_IDS.wind
const ICON = 'wind-arrow'

function arrowImage(): ImageData {
  const s = 32, c = document.createElement('canvas')
  c.width = c.height = s
  const g = c.getContext('2d')!
  g.clearRect(0, 0, s, s)
  g.fillStyle = 'rgba(232,235,239,0.9)'
  g.strokeStyle = 'rgba(11,13,16,0.9)'
  g.lineWidth = 1.5
  g.beginPath(); g.moveTo(s / 2, 2); g.lineTo(s - 6, s - 4); g.lineTo(s / 2, s * 0.68); g.lineTo(6, s - 4); g.closePath()
  g.fill(); g.stroke()
  return g.getImageData(0, 0, s, s)
}

export default function WindLayer({ map }: { map: maplibregl.Map }) {
  const wind = useStore((s) => s.wind)
  const hour = useStore((s) => s.hour)
  const visible = useStore((s) => s.layers.wind)

  useEffect(() => {
    if (!wind) return
    const h = Math.min(hour, wind.hours.length - 1)
    const features: FeatureCollection<Point, { bearing: number; speed: number }> = { type: 'FeatureCollection', features: [] }
    wind.lats.forEach((lat, i) => wind.lons.forEach((lon, j) => {
      const u = wind.u[h][i][j], v = wind.v[h][i][j]
      const speed = Math.hypot(u, v)
      const bearing = (Math.atan2(u, v) * 180) / Math.PI  // direction the air moves TO, clockwise from north
      features.features.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] }, properties: { bearing, speed } })
    }))
    if (!mapAlive(map)) return
    if (map.getSource(ID)) {
      (map.getSource(ID) as GeoJSONSource).setData(features)
    } else {
      if (!map.hasImage(ICON)) map.addImage(ICON, arrowImage(), { pixelRatio: 2 })
      map.addSource(ID, { type: 'geojson', data: features })
      map.addLayer({
        id: ID, type: 'symbol', source: ID,
        layout: {
          'icon-image': ICON, 'icon-rotate': ['get', 'bearing'], 'icon-rotation-alignment': 'map', 'icon-allow-overlap': true,
          'icon-size': ['interpolate', ['linear'], ['get', 'speed'], 0, 0.35, 5, 0.7, 12, 1.2],
        },
        paint: { 'icon-opacity': ['interpolate', ['linear'], ['get', 'speed'], 0, 0.25, 3, 0.9] },
      })
      map.setLayoutProperty(ID, 'visibility', visible ? 'visible' : 'none')
    }
  }, [map, wind, hour])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (mapAlive(map) && map.getLayer(ID)) map.setLayoutProperty(ID, 'visibility', visible ? 'visible' : 'none')
  }, [map, visible, wind])

  useEffect(() => () => {
    if (!mapAlive(map)) return
    if (map.getLayer(ID)) map.removeLayer(ID)
    if (map.getSource(ID)) map.removeSource(ID)
  }, [map])

  return null
}
