// Drives the plume layer only (DESIGN.md §9.2). Play/pause at 4 forecast hours per second.
import { useEffect, useMemo, type CSSProperties } from 'react'
import { useStore } from '@/lib/store'
import { istLabel } from '@/lib/time'
import { typingTarget } from '@/lib/keys'
import { PauseIcon, PlayIcon } from './icons'

const DAY = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', weekday: 'short', day: 'numeric' })

export default function TimeSlider() {
  const manifest = useStore((s) => s.manifest)
  const hour = useStore((s) => s.hour)
  const playing = useStore((s) => s.playing)
  const setHour = useStore((s) => s.setHour)
  const setPlaying = useStore((s) => s.setPlaying)
  const layers = useStore((s) => s.layers)
  const n = manifest?.hours.length ?? 0
  const driven = layers.plume || layers.wind || layers.zones   // what the hour changes

  useEffect(() => {
    if (!playing || n < 2) return
    const id = window.setInterval(() => {
      const cur = useStore.getState().hour
      if (cur + 1 >= n) { setPlaying(false); return }   // stop at the last hour, never loop
      setHour(cur + 1)
    }, 250)
    return () => window.clearInterval(id)
  }, [playing, n, setHour])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (typingTarget(e) || e.shiftKey || e.metaKey || e.ctrlKey || e.altKey) return   // Shift+arrows belong to the chapters
      if (e.key === 'ArrowRight') setHour(useStore.getState().hour + 1)
      if (e.key === 'ArrowLeft') setHour(useStore.getState().hour - 1)
      if (e.key === ' ') { e.preventDefault(); const s = useStore.getState(); if (!s.playing && s.hour >= n - 1) setHour(0); setPlaying(!s.playing) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setHour, setPlaying, n])

  // one tick where the IST date changes, so the track reads as days
  const days = useMemo(() => {
    if (!manifest) return []
    const out: { i: number; label: string }[] = []
    let last = ''
    manifest.hours.forEach((t, i) => { const d = DAY.format(new Date(t)); if (d !== last) { out.push({ i, label: d }); last = d } })
    // a run that starts late in the evening puts the next day's tick a few hours in; keep the day boundary, drop the start
    const n = manifest.hours.length
    return out.filter((d, k) => k === 0 ? !(out[1] && (out[1].i - d.i) / Math.max(1, n - 1) < 0.1) : true)
  }, [manifest])

  if (!manifest || !driven) return null
  const single = n < 2
  const play = () => { if (!playing && hour >= n - 1) setHour(0); setPlaying(!playing) }
  const pct = single ? 0 : (hour / (n - 1)) * 100
  return (
    <div className="glass absolute bottom-4 left-1/2 w-[min(760px,calc(100%-2rem))] -translate-x-1/2 px-4 py-3 max-sm:bottom-3 max-sm:w-[calc(100%-1rem)] max-sm:px-3">
      <div className="flex items-center gap-4 max-sm:gap-3">
        <button
          type="button"
          onClick={play}
          disabled={single}
          aria-label={playing ? 'Pause' : 'Play'}
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition disabled:opacity-40 ${playing ? 'bg-fire text-ink' : 'bg-white/10 text-fg hover:bg-white/15'}`}
        >
          {playing ? <PauseIcon /> : <PlayIcon />}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-3">
            <div className="truncate text-[15px] font-semibold text-fg">{istLabel(manifest.hours[hour])} <span className="font-normal text-mute">IST</span></div>
            <div className="shrink-0 font-mono text-[11px] text-mute">+{hour} h{single ? ' · single-hour run' : <span className="opacity-60"> / {n - 1}</span>}</div>
          </div>
          <input
            type="range"
            min={0}
            max={Math.max(0, n - 1)}
            value={hour}
            onChange={(e) => setHour(Number(e.target.value))}
            onPointerDown={() => setPlaying(false)}
            disabled={single}
            aria-label="Forecast hour"
            className="vd-range"
            style={{ '--p': `${pct}%` } as CSSProperties}
          />
          {!single && (
            <div className="relative h-3 font-mono text-[10px] text-mute">
              {days.map((d) => <span key={d.i} className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: `${(d.i / (n - 1)) * 100}%`, transform: d.i === 0 ? 'none' : undefined }}>{d.label}</span>)}
            </div>
          )}
        </div>
        <div className="hidden shrink-0 font-mono text-[10px] leading-tight text-mute lg:block">← → hour<br />space play</div>
      </div>
    </div>
  )
}
