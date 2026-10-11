// "About this run": the one place run metadata lives (PIVOT_PLAN.md P11/P18). The legend, the
// detail panel and the cards no longer repeat it.
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useStore } from '@/lib/store'
import { fmtMetric } from '@/lib/aqi'
import { istLabel } from '@/lib/time'

export default function RunPopover() {
  const m = useStore((s) => s.manifest)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('mousedown', onDown); window.addEventListener('keydown', onKey)
    return () => { window.removeEventListener('mousedown', onDown); window.removeEventListener('keydown', onKey) }
  }, [open])
  if (!m) return null
  const cal = m.calibration
  return (
    <div ref={ref} className="relative max-sm:hidden">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="dialog" className="hairline flex h-9 items-center gap-2 rounded-full px-3 font-mono text-[11px] text-mute hover:text-fg">
        <span className="live-dot" />run {istLabel(m.generatedAt)}
      </button>
      {open && (
        <div role="dialog" aria-label="About this run" className="glass absolute right-0 top-11 z-50 w-80 p-4 text-[12px] leading-relaxed text-mute">
          <div className="text-[13px] font-semibold text-fg">About this run</div>
          <div className="mt-1 font-mono text-[10.5px]">{m.runId} · {istLabel(m.generatedAt)} IST · {m.hours.length - 1} h ahead</div>
          <div className="mt-2">
            {cal.k === null ? 'Not calibrated: the smoke image shows relative density.' : `Fit against stations: R² ${fmtMetric(cal.r2)}, MAE ${fmtMetric(cal.mae, 0)} µg/m³${cal.stations ? ` over ${cal.stations} stations, ${cal.window}` : ''}.`}{' '}
            <Link to="/validation" className="text-fg underline" onClick={() => setOpen(false)}>Validation →</Link>
          </div>
          <div className="mt-2 font-mono text-[10.5px]">fires NASA FIRMS VIIRS · winds Open-Meteo 925 hPa · background CAMS · stations OpenAQ · schools OpenStreetMap · tiers anchored to CAQM GRAP</div>
          <div className="mt-2 text-[11px]">{m.disclaimer}</div>
        </div>
      )}
    </div>
  )
}
