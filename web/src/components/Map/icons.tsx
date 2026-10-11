// 16 px stroke icons for the layer bar. Inline so the bundle carries no icon font.
import type { LayerId } from '@/config/layers'

const PATHS: Record<LayerId, string> = {
  plume: 'M7 18h10a4 4 0 0 0 .5-7.97A6 6 0 0 0 6.1 9.5 4.25 4.25 0 0 0 7 18z',
  fires: 'M12 3c1 3 4 5 4 9a4 4 0 0 1-8 0c0-1.5.5-2.5 1-3 .2 1 .8 1.8 1.5 2 0-3 .5-5.5 1.5-8z',
  wind: 'M3 8h10a2.5 2.5 0 1 0-2.5-2.5M3 12h14a2.5 2.5 0 1 1-2.5 2.5M3 16h8a2 2 0 1 1-2 2',
  stations: 'M12 21v-8M8 13a5 5 0 0 1 8 0M5.5 10.5a9 9 0 0 1 13 0M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z',
  schools: 'M3 21h18M5 21V9l7-5 7 5v12M9 21v-6h6v6',
  actors: 'M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2M9.5 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7M21 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
  zones: 'M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0M12 12m-8 0a8 8 0 1 0 16 0a8 8 0 1 0-16 0',
  burnrisk: 'M4 4h16v16H4zM4 12h16M12 4v16',
  ndvi: 'M5 19c0-8 5-13 14-14-1 9-6 14-14 14zM5 19l7-7',
}

export function LayerIcon({ id, className = 'h-4 w-4' }: { id: LayerId; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={PATHS[id]} />
    </svg>
  )
}

export const PlayIcon = () => <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden><path d="M8 5.5v13l11-6.5z" /></svg>
export const PauseIcon = () => <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden><path d="M7 5h4v14H7zM13 5h4v14h-4z" /></svg>
export const CloseIcon = () => <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden><path d="M6 6l12 12M18 6L6 18" /></svg>
