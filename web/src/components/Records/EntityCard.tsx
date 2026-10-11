// One entity's day in five lines (PIVOT_PLAN.md task 44): forecast, advised or registered,
// decided, checked, credited — the latest of each kind, a count instead of a repeat. Used by the
// decisions page and the walkthrough's report.
import { Link } from 'react-router-dom'
import { TIERS } from '@/lib/aqi'
import { istClock } from '@/lib/time'
import { TYPE_LABELS, type DayState } from '@/lib/records'

function Line({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="contents">
      <dt className="pt-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-mute">{label}</dt>
      <dd className={`pt-1.5 text-[13px] leading-snug ${muted ? 'text-mute' : 'text-fg'}`}>{value}</dd>
    </div>
  )
}

export default function EntityCard({ s, name }: { s: DayState; name: string }) {
  const tier = s.tier ? TIERS[s.tier] : null
  return (
    <section className="glass glass-tight p-4" data-entity-card={s.entity}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <Link to={`/records/${encodeURIComponent(s.entity)}`} className="text-[15px] font-semibold text-fg hover:underline">{name}</Link>
        <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-mute">
          <span>{TYPE_LABELS[s.actorType] ?? s.actorType}</span>
          {tier && <span className="rounded px-1.5 py-0.5 font-semibold text-ink" style={{ background: tier.colour }}>{tier.label}</span>}
        </div>
      </div>
      <dl className="mt-2 grid grid-cols-[86px_1fr] gap-x-3 border-t border-white/8">
        <Line label="Forecast" value={s.forecast ? `${s.forecast.text} · run ${istClock(s.forecast.ts)}` : 'no card for today'} muted={!s.forecast} />
        {s.advised
          ? <Line label="Advised" value={s.advised.text} />
          : s.registered
            ? <Line label="Registered" value={`by ${s.registered.by}, ${istClock(s.registered.ts)}${s.registered.approved ? ' · approved' : ' · awaiting approval'}`} />
            : <Line label="Advised" value="no advisory yet" muted />}
        <Line label="Decided" value={s.decided ? `${s.decided.by} · ${s.decided.text} · ${istClock(s.decided.ts)}${s.decided.times > 1 ? ` · logged ${s.decided.times} times today` : ''}` : 'no decision yet'} muted={!s.decided} />
        <Line label="Checked" value={s.checked ? `${s.checked.text}${s.checked.by ? ` · ${s.checked.by}, ${istClock(s.checked.ts)}` : ''}` : 'pending — the station confirms the day tomorrow'} muted={!s.checked} />
        <Line label="Credited" value={s.credited ? s.credited.text : 'nothing credited yet'} muted={!s.credited} />
      </dl>
    </section>
  )
}
