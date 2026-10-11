// The honesty footer every non-map page carries (DESIGN.md §13.2): the run and its fit, once.
// Renders nothing without a run: pages that show no forecast carry no forecast caveat.
import { Link } from 'react-router-dom'
import { fmtMetric } from '@/lib/aqi'
import { istLabel } from '@/lib/time'

export default function Footer({ runId, generatedAt, calibration, disclaimer, label = 'run' }: {
  runId?: string | null
  generatedAt?: string | null
  calibration?: { k: number | null; r2: number | null; mae: number | null; window?: string | null; stations?: number | null } | null
  disclaimer?: string | null
  label?: string
}) {
  if (!runId) return null
  return (
    <footer className="mt-6 border-t border-line pt-3 font-mono text-[10px] leading-relaxed text-mute">
      <div>{label} {runId}{generatedAt ? ` · ${istLabel(generatedAt)} IST` : ''}</div>
      {calibration && (
        <div>fit: R² {fmtMetric(calibration.r2)} · MAE {fmtMetric(calibration.mae, 0)} µg/m³{calibration.stations ? ` · ${calibration.stations} stations, ${calibration.window}` : ''} · <Link to="/validation" className="underline">how it was checked</Link></div>
      )}
      {disclaimer && <div>{disclaimer}</div>}
      <div>fires NASA FIRMS VIIRS · winds Open-Meteo 925 hPa · background CAMS · schools OpenStreetMap · tiers anchored to CAQM GRAP</div>
    </footer>
  )
}
