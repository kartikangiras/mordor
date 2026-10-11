// One MapLibre instance for every map surface (/, /map, /story). Before this, each route owned
// its own MapRoot, so every navigation tore the map down, rebuilt it, and refetched the manifest
// plus eight layer files. Routes under this shell only switch overlays and the camera; the map
// and its loaded data survive the navigation.
import { Outlet } from 'react-router-dom'
import MapRoot from '@/components/Map/MapRoot'

export default function MapShell() {
  return (
    <div className="relative h-full w-full overflow-hidden bg-ink">
      <MapRoot />
      <Outlet />
    </div>
  )
}
