// The principal's one screen (DESIGN.md §9.5). 360 px design width, nothing else on the page.
import { useState } from 'react'
import { TIERS, fmtMetric, type TierId } from '@/lib/aqi'
import { ACTIONS as SCHOOL_ACTIONS, type Card, type PublicCard } from '@/lib/protocol'
import { istLabel } from '@/lib/time'
import WindowStrip from './WindowStrip'
import MessageBox from './MessageBox'
import SendButton from './SendButton'
import DosePanel from './DosePanel'

const DATE_FMT = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', weekday: 'long', day: 'numeric', month: 'long' })

type Props = {
  card: Card | (PublicCard & { school: { id: string; name: string; name_hi?: string | null; hours?: [string, string]; dismissal?: [string, string]; hasPurifiers: boolean; personTitle?: string; email?: string | null } })
  readOnly?: boolean
  actions: string[]
  onToggle?: (id: string) => void
  onSent?: (via: 'whatsapp' | 'copy' | 'email') => Promise<void>
  onEmail?: () => Promise<string>
  busy?: boolean
}

export default function ProtocolCard({ card, readOnly, actions, onToggle, onSent, onEmail, busy }: Props) {
  const [why, setWhy] = useState(false)
  const tier = card.dayTier ? TIERS[card.dayTier as TierId] : null
  const message = 'message' in card ? card.message : undefined
  const log = 'log' in card ? card.log : []
  const ACTIONS = card.actions ?? SCHOOL_ACTIONS
  const proto = (card.protocol ?? {}) as Record<string, string | undefined>
  const protoRows = Object.entries(proto).filter(([k]) => k !== 'grapAnchor' && k !== 'advisory')
  const date = card.date ? DATE_FMT.format(new Date(card.date + 'T12:00:00+05:30')) : '—'
  return (
    <div className="mx-auto w-full max-w-[420px] pb-8 font-sans">
      {/* 1. name, date, tier band */}
      <div className="rounded-t px-4 py-3 text-ink" style={{ background: tier?.colour ?? '#6b7480' }}>
        <div className="text-[13px] font-semibold opacity-90">{card.school.name}{card.school.name_hi ? ` · ${card.school.name_hi}` : ''}{card.school.personTitle ? <span className="opacity-70"> · {card.school.personTitle}</span> : null}</div>
        <div className="text-[12px] opacity-80">{date}</div>
        <div className="mt-1 text-2xl font-bold leading-tight">{tier ? `${card.dayTier} · ${tier.label}` : 'No tier yet'}</div>
        {card.protocol?.grapAnchor && <div className="text-[12px] opacity-90">GRAP {card.protocol.grapAnchor}</div>}
      </div>

      <div className="space-y-4 rounded-b border border-t-0 border-line bg-panel p-4">
        {/* 2. headline */}
        <p className="text-lg font-semibold leading-snug text-fg">{card.headline}</p>
        {card.protocol?.advisory && <p className="rounded border border-line bg-ink p-2 text-[13px] text-fg">{card.protocol.advisory}</p>}

        {/* 3. window strip */}
        <WindowStrip windows={card.windows} schoolHours={card.school.hours} dismissal={card.school.dismissal} strip={card.strip} />

        {/* 3a. what the number is worth, and what it costs to breathe */}
        <DosePanel dose={'dose' in card ? card.dose : null} interval={'interval' in card ? card.interval : null} />

        {/* 4. actions */}
        <div className="space-y-1">
          {ACTIONS.map((a) => (
            <label key={a.id} className={`flex min-h-11 items-center gap-3 rounded border border-line px-3 ${readOnly ? '' : 'active:bg-ink'}`}>
              <input type="checkbox" className="h-5 w-5 accent-[#ffb347]" checked={actions.includes(a.id)} disabled={readOnly} onChange={() => onToggle?.(a.id)} />
              <span className="text-[14px] text-fg">{a.label} <span className="text-mute">· {a.hi}</span></span>
            </label>
          ))}
          {card.protocol && (
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 pt-1 font-mono text-[11px] text-mute">
              {protoRows.map(([k, v]) => <span key={k}>{k}: <span className="text-fg">{v}</span></span>)}
            </div>
          )}
        </div>

        {/* 5 + 6. message and send */}
        {message && <MessageBox message={message} />}
        {message && !readOnly && onSent && onEmail && <SendButton message={message} onSent={onSent} onEmail={onEmail} busy={!!busy} audience={card.audience} canEmail={!!card.school?.email} />}

        {/* 7. why this */}
        <div>
          <button type="button" onClick={() => setWhy(!why)} className="h-10 font-mono text-[12px] text-mute underline">Why this?{why ? ' ▴' : ' ▾'}</button>
          {why && (
            <div className="mt-1 space-y-1 rounded border border-line bg-ink p-3 font-mono text-[11px] leading-relaxed text-mute">
              <div>peak AQI {card.peakAqi ?? '—'}{'interval' in card && card.interval ? ` (${card.interval.level} range ${card.interval.aqiLo}–${card.interval.aqiHi})` : ''} during school hours · outdoor hours cancelled {card.outdoorHoursCancelled}</div>
              <div>run {card.runId}</div>
              {card.calibration && <div>k {card.calibration.k === null ? 'not fitted' : card.calibration.k.toExponential(2)} · R² {fmtMetric(card.calibration.r2)} · MAE {fmtMetric(card.calibration.mae, 0)} · {card.calibration.stations} stations, {card.calibration.window}</div>}
              <div>Stubble-fire increment (ours, 5 km) + CAMS background (~40 km) → CPCB PM2.5 sub-index → tier → CAQM GRAP stage. A simplified transport model; not for medical decisions.</div>
              {card.hourly.length > 0 && (
                <div className="max-h-40 overflow-y-auto">
                  {card.hourly.filter((h) => h.tier).map((h) => (
                    <div key={h.t} className="flex justify-between"><span>{istLabel(h.t)}</span><span>{h.pm25Total ?? '—'}{h.pm25Lo != null ? ` (${h.pm25Lo}–${h.pm25Hi})` : ''} µg/m³ · AQI {h.aqi} · {h.tier}</span></div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 8. yesterday's log */}
        {log.length > 0 && (
          <div className="border-t border-line pt-2 font-mono text-[11px] text-mute">
            {log.slice(0, 2).map((l) => (
              <div key={l.runId}>{l.date}: {l.dayTier ?? '—'} · {l.actions.join(', ') || 'no actions'} · {l.sentVia ?? 'not sent'} · {istLabel(l.ackedAt)}</div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
