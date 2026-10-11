// The district agriculture officer's card: the cells most likely to burn in the next 48 h and
// what the office does about it. Same shape as the exposure card: headline, list, actions, message.
import { useState } from 'react'
import { BURN_CATS } from '@/lib/aqi'
import type { Card, PublicCard } from '@/lib/protocol'
import MessageBox from './MessageBox'
import SendButton from './SendButton'

type Props = {
  card: (Card | PublicCard) & { school?: Card['school'] }
  readOnly?: boolean
  actions: string[]
  onToggle?: (id: string) => void
  onSent?: (via: 'whatsapp' | 'copy' | 'email') => Promise<void>
  onEmail?: () => Promise<string>
  busy?: boolean
}

export default function SourceCard({ card, readOnly, actions, onToggle, onSent, onEmail, busy }: Props) {
  const [why, setWhy] = useState(false)
  const risk = card.dayTier as unknown as string | null
  const cat = BURN_CATS.find((c) => c.label === risk) ?? BURN_CATS[0]
  const name = 'school' in card && card.school ? card.school.name : (card as PublicCard).name
  const message = 'message' in card ? card.message : undefined
  return (
    <div className="mx-auto w-full max-w-[420px] pb-8 font-sans">
      <div className="rounded-t px-4 py-3 text-ink" style={{ background: cat.colour }}>
        <div className="text-[13px] font-semibold opacity-90">{name}</div>
        <div className="text-[12px] opacity-80">{card.date} · next 48 hours · {card.district ?? ''}</div>
        <div className="mt-1 text-2xl font-bold leading-tight">Burning risk · {risk ?? "—"}</div>
        <div className="text-[12px] opacity-90">{card.anchor}</div>
      </div>
      <div className="space-y-4 rounded-b border border-t-0 border-line bg-panel p-4">
        <p className="text-lg font-semibold leading-snug text-fg">{card.headline}</p>
        <div className="space-y-1">
          {(card.cells ?? []).map((c, i) => {
            const cc = BURN_CATS.find((x) => x.label === c.category) ?? BURN_CATS[0]
            return (
              <div key={`${c.i}-${c.j}`} className="flex items-center justify-between rounded border border-line px-3 py-2 font-mono text-[12px]">
                <span className="text-fg">{i + 1}. {c.name} <span className="text-mute">{c.distanceKm} km</span></span>
                <span><span className="rounded px-1.5 py-0.5 text-[10px] font-semibold text-ink" style={{ background: cc.colour }}>{c.score} {c.category}</span> <span className="text-mute">{c.fires24} fires/24 h{c.ndviChange !== null ? ` · NDVI ${c.ndviChange.toFixed(2)}` : ''}</span></span>
              </div>
            )
          })}
          {(card.cells ?? []).length === 0 && <div className="font-mono text-[12px] text-mute">no risk cells within the district radius</div>}
        </div>
        <div className="space-y-1">
          {(card.actions ?? []).map((a) => (
            <label key={a.id} className="flex min-h-11 items-center gap-3 rounded border border-line px-3">
              <input type="checkbox" className="h-5 w-5 accent-[#ffb347]" checked={actions.includes(a.id)} disabled={readOnly} onChange={() => onToggle?.(a.id)} />
              <span className="text-[14px] text-fg">{a.label} <span className="text-mute">· {a.hi}</span></span>
            </label>
          ))}
        </div>
        {message && <MessageBox message={message} />}
        {message && !readOnly && onSent && onEmail && <SendButton message={message} onSent={onSent} onEmail={onEmail} busy={!!busy} audience={card.audience} canEmail={!!card.school?.email} />}
        <div>
          <button type="button" onClick={() => setWhy(!why)} className="h-10 font-mono text-[12px] text-mute underline">Why this?{why ? ' ▴' : ' ▾'}</button>
          {why && (
            <div className="mt-1 rounded border border-line bg-ink p-3 font-mono text-[11px] leading-relaxed text-mute">
              Score 0–100 per 27 km cell: recent fires (0–35), trend (0–15), what these fields did on these dates in 2024 (0–25), NDVI drop since the last composite (0–15), minus forecast rain (0–10). Statistical, not a fire-behaviour model. Run {card.runId}.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
