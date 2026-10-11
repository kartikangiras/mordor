// Step 8, the medical superintendent: severe air is a medical event. Read the hospital's card,
// then three plain phases - alert the wards, check the stock, keep beds ready - logged as one
// decision; the day closes on the decisions page.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useStore } from '@/lib/store'
import { getMyForecast, postAck } from '@/lib/api'
import type { Card } from '@/lib/protocol'
import { TIERS, type TierId } from '@/lib/aqi'
import { ACTION_LABELS } from '@/lib/labels'
import { PhaseButton, Fact, Done } from '../Phase'
import { pickActor, type StepProps } from './common'
import AssessmentBox from '@/components/Act/AssessmentBox'

const PHASES: { id: string; label: string }[] = [
  { id: 'alert_wards', label: 'Alert the respiratory and emergency wards' },
  { id: 'stock_meds', label: 'Check inhalers, nebulisers and oxygen' },
  { id: 'beds_ready', label: 'Keep beds ready for asthma and COPD' },
]

export default function StepHealth({ area, d, headers, colour, onLeave }: StepProps & { onLeave: () => void }) {
  const entities = useStore((s) => s.entities)
  const actor = pickActor(d, entities, area, { type: 'hospital', kind: 'exposure' })
  const [card, setCard] = useState<Card | null>(null)
  const [doneSteps, setDoneSteps] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [logged, setLogged] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)
  if (!actor || actor.type !== 'hospital') return <div className="font-mono text-[11px] text-mute">No hospital registered here yet.</div>
  const tier = card?.dayTier && card.dayTier in TIERS ? TIERS[card.dayTier as TierId] : null
  const read = async () => {
    setBusy(true); setErr(null)
    try { setCard(await getMyForecast(headers, actor.id)) } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const next = PHASES.find((p) => !doneSteps.includes(p.id))
  const log = async () => {
    if (!card) return
    setBusy(true); setErr(null)
    try { const r = await postAck(actor.id, { runId: card.runId, actions: doneSteps, sentVia: 'noted' }, headers); setLogged(r.record?.seq ?? 0) }
    catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="space-y-2">
      <div className="text-base font-semibold text-fg">{actor.name}</div>
      <PhaseButton active={!card} done={!!card} busy={busy && !card} colour={colour} onClick={read}>Read tonight's card</PhaseButton>
      {card && (
        <>
          <div className="rounded px-3 py-2 text-ink" style={{ background: tier?.colour ?? '#6b7480' }}>
            <div className="text-[11px] opacity-80">{card.date}</div>
            <div className="text-lg font-bold leading-tight">{tier?.label ?? 'No advice yet'}</div>
            <div className="text-[12px]">{card.headline}</div>
          </div>
          <Fact k="beds" v={card.people ?? '—'} />
          <Fact k="peak AQI" v={card.peakAqi ?? '—'} />
          <AssessmentBox entityId={actor.id} runId={card.runId} actions={doneSteps} headers={headers} colour={colour} />
          {PHASES.map((p) => <PhaseButton key={p.id} active={!!next && next.id === p.id && logged === null} done={doneSteps.includes(p.id)} colour={colour} onClick={() => setDoneSteps((x) => [...x, p.id])}>{p.label}</PhaseButton>)}
          {card.message && doneSteps.length > 0 && <div className="rounded border border-line bg-ink p-2 text-[12px] leading-relaxed text-fg">{card.message.hi}<div className="mt-1 text-[11px] text-fg/80">{card.message.en}</div></div>}
          <PhaseButton active={!next && logged === null} done={logged !== null} busy={busy && !!card} colour={colour} onClick={log}>Log the preparation</PhaseButton>
          {logged !== null && <Done>Logged · {doneSteps.map((a) => ACTION_LABELS[a] ?? a).join(', ')} · record #{logged}</Done>}
        </>
      )}
      {err && <div className="font-mono text-[11px] text-red-300">{err}</div>}
      {logged !== null && (
        <>
          <Link to="/records" className="flex h-10 items-center justify-center rounded border border-line font-mono text-[11px] text-fg">Read the day's decisions</Link>
          <PhaseButton active colour={colour} onClick={onLeave}>Finish the walkthrough</PhaseButton>
        </>
      )}
    </div>
  )
}
