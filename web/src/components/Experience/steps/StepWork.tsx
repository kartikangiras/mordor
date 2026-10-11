// Step 5, the RWA secretary: read tonight's card, confirm the actions, log them. Three plain
// phases, like every other step; WhatsApp is an optional link that gates nothing.
import { useState } from 'react'
import { useStore } from '@/lib/store'
import { getMyForecast, postAck } from '@/lib/api'
import { waLink, type Card } from '@/lib/protocol'
import { TIERS, type TierId } from '@/lib/aqi'
import { ACTION_LABELS } from '@/lib/labels'
import { PhaseButton, Fact, Done } from '../Phase'
import { pickActor, type StepProps } from './common'
import AssessmentBox from '@/components/Act/AssessmentBox'

export default function StepWork({ area, d, headers, onComplete, colour }: StepProps) {
  const entities = useStore((s) => s.entities)
  const actor = pickActor(d, entities, area, { type: 'rwa', kind: 'exposure' })
  const [phase, setPhase] = useState(1)
  const [card, setCard] = useState<Card | null>(null)
  const [actions, setActions] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)
  if (!actor) return <div className="font-mono text-[11px] text-mute">No residents' association registered here yet.</div>
  const tier = card?.dayTier && card.dayTier in TIERS ? TIERS[card.dayTier as TierId] : null
  const read = async () => {
    setBusy(true); setErr(null)
    try { const c = await getMyForecast(headers, actor.id); setCard(c); setActions(c.acked?.actions ?? c.defaultActions); setPhase(2) }
    catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const log = async () => {
    if (!card) return
    setBusy(true); setErr(null)
    try { const r = await postAck(actor.id, { runId: card.runId, actions, sentVia: 'noted' }, headers); setDone(r.record?.seq ?? 0); setPhase(4) }
    catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="space-y-2">
      <div className="text-base font-semibold text-fg">{actor.name}</div>
      <PhaseButton active={phase === 1} done={phase > 1} busy={busy && phase === 1} colour={colour} onClick={read}>Read tonight's card</PhaseButton>
      {card && (
        <>
          <div className="rounded px-3 py-2 text-ink" style={{ background: tier?.colour ?? '#6b7480' }}>
            <div className="text-[11px] opacity-80">{card.date}</div>
            <div className="text-lg font-bold leading-tight">{tier?.label ?? 'No advice yet'}</div>
            <div className="text-[12px]">{card.headline}</div>
          </div>
          <Fact k="people reached" v={card.people ?? '—'} />
          <AssessmentBox entityId={actor.id} runId={card.runId} actions={actions} headers={headers} onAdd={phase > 2 ? undefined : (id) => setActions((x) => (x.includes(id) ? x : [...x, id]))} colour={colour} />
          {(card.actions ?? []).map((a) => (
            <label key={a.id} className="flex min-h-10 items-center gap-2 rounded border border-line px-2 font-mono text-[11px] text-fg">
              <input type="checkbox" className="h-4 w-4 accent-[#F472B6]" checked={actions.includes(a.id)} disabled={phase > 2} onChange={() => setActions((x) => (x.includes(a.id) ? x.filter((y) => y !== a.id) : [...x, a.id]))} />
              <span>{a.label}</span>
            </label>
          ))}
        </>
      )}
      <PhaseButton active={phase === 2} done={phase > 2} colour={colour} onClick={() => setPhase(3)}>Confirm the actions</PhaseButton>
      {card && phase >= 3 && (
        <div className="rounded border border-line bg-ink p-2 text-[12px] leading-relaxed text-fg">{card.message.hi}<div className="mt-1 text-[11px] text-fg/80">{card.message.en}</div>
          <div className="mt-1 flex items-center justify-between font-mono text-[10px] text-mute"><span>{card.message.chars} / 400 · {card.message.source === 'agent' ? 'drafted automatically' : card.message.source === 'template' ? 'standard text' : 'cached'}</span><a href={waLink(card.message)} target="_blank" rel="noopener" className="underline hover:text-fg">open in WhatsApp</a></div>
        </div>
      )}
      <PhaseButton active={phase === 3} done={phase > 3} busy={busy && phase === 3} colour={colour} onClick={log}>Log the actions</PhaseButton>
      {done !== null && <Done>Logged · {actions.map((a) => ACTION_LABELS[a] ?? a).join(', ') || 'no actions'} · record #{done}</Done>}
      {err && <div className="font-mono text-[11px] text-red-300">{err}</div>}
      <PhaseButton active={phase === 4} colour={colour} onClick={onComplete}>Hand over to Dr. Mehta →</PhaseButton>
    </div>
  )
}
