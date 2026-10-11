// / — the public front page over the cinematic map. The walkthrough lives behind the actor
// door (/act/walk); nothing on this surface writes.
import { useEffect } from 'react'
import Landing from '@/components/Landing/Landing'
import { useStore } from '@/lib/store'

export default function Front() {
  const error = useStore((s) => s.error)
  const setMapMode = useStore((s) => s.setMapMode)
  const resetView = useStore((s) => s.resetView)
  useEffect(() => { setMapMode('cinematic'); return () => { setMapMode('interactive'); resetView() } }, [setMapMode, resetView])
  return (
    <div className="absolute inset-0 overflow-hidden">
      <div className="pointer-events-none absolute inset-0" style={{ background: 'radial-gradient(ellipse at center, rgba(11,13,16,0.25) 10%, rgba(11,13,16,0.85) 100%)' }} />
      <Landing error={error} />
    </div>
  )
}
