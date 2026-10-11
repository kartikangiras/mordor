import { useState } from 'react'
import { useStore } from '@/lib/store'
import { getImpact, postAccount, type ImpactReport } from '@/lib/api'
import type { DecisionRecord } from '@/lib/protocol'
import { PhaseButton, Fact, Done } from '../Phase'
import type { StepProps } from './common'

export default function StepValue({ area, d, headers, onComplete, colour, school }: StepProps) {
  const { entities, manifest } = useStore()
  const fromMap = (d.inArea?.actors.length ? d.inArea.actors : (entities?.features ?? []).map((f) => f.properties)).filter((a) => a.kind === 'exposure')
  const actors: { id: string; date: string | null }[] = [...fromMap.map((a) => ({ id: a.id, date: a.date })), ...(school && !fromMap.some((a) => a.id === school.id) ? [{ id: school.id, date: manifest?.schools?.dayDate ?? null }] : [])]
  const [stmts, setStmts] = useState<DecisionRecord[]>([])
  const [totals, setTotals] = useState<ImpactReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const compute = async () => {
    setBusy(true); setErr(null)
    try {
      const out: DecisionRecord[] = []
      for (const a of actors) { if (!a.date) continue; try { out.push((await postAccount({ entityId: a.id, date: a.date }, headers)).record) } catch (e) { setErr((e as Error).message) } }
      setStmts(out)
      const date = actors.find((a) => a.date)?.date ?? undefined
      setTotals(await getImpact(date).catch(() => null))
      setDone(true)
    } finally { setBusy(false) }
  }
  return (
    <div className="space-y-2">
      <div className="font-mono text-[11px] text-mute">{area.name} · {actors.length} exposure actors</div>
      <PhaseButton active={!done} done={done} busy={busy} colour={colour} onClick={compute}>Compute the impact statements</PhaseButton>
      {stmts.map((r) => (
        <Done key={r.id}>{r.entity} · <span className="text-fg">{String(r.payload.value)} {String(r.payload.unit)}</span> · {String(r.payload.status)}{r.payload.outcome ? ` (${String(r.payload.outcome)})` : ''}</Done>
      ))}
      {totals && (
        <div className="pt-1">
          <div className="font-mono text-[11px] text-mute">Every entity, {totals.date}</div>
          <Fact k="decisions logged" v={totals.decisionsLogged} />
          <Fact k="people covered" v={totals.people} />
          <Fact k="statements" v={`${totals.records.verified} verified · ${totals.records.provisional} provisional · ${totals.records.notCredited} not credited`} />
          {Object.entries(totals.records.verifiedByUnit).map(([u, v]) => <Fact key={u} k={u} v={v} />)}
        </div>
      )}
      {err && <div className="font-mono text-[11px] text-red-300">{err}</div>}
      <div className="font-mono text-[10px] text-mute">Unit: people × hours of the windows of concern at T2 or worse. Credited only when the nearest station confirmed the day. A false alarm credits nothing.</div>
      <PhaseButton active={done} colour={colour} onClick={onComplete}>Hand over to Dr. Kapoor →</PhaseButton>
    </div>
  )
}
