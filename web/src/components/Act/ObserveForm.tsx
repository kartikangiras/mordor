// Pull the station readings for an entity-day and record the outcome: the verifier's form,
// shared by /act/queue and the walkthrough's step 6. Replaces the old window.prompt.
import { useState } from 'react'
import { getObserve, postConfirm, type ObserveReport } from '@/lib/api'
import { PhaseButton, Fact, Done } from '@/components/Experience/Phase'
import { OUTCOME_LABELS } from '@/lib/labels'

const OUTCOMES: { id: string; label: string }[] = [{ id: 'confirmed', label: 'Confirmed' }, { id: 'not_confirmed', label: 'Not confirmed' }, { id: 'missed', label: 'Missed' }, { id: 'moot', label: 'Moot' }]

export default function ObserveForm({ entityId, date, cardSaid, headers, colour = '#10B981', onDone }: { entityId: string; date?: string; cardSaid?: string; headers: Record<string, string>; colour?: string; onDone?: (seq: number, outcome: string) => void }) {
  const [obs, setObs] = useState<ObserveReport | null>(null)
  const [evidence, setEvidence] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<{ seq: number; outcome: string } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const fetchObs = async () => {
    setBusy(true); setErr(null)
    try { const o = await getObserve(entityId, headers, date); setObs(o); setEvidence(o.observed ? `${o.station?.name}: peak ${o.observed.peakPm25} µg/m³ (AQI ${o.observed.peakAqi}) in the windows, ${o.observed.hoursAtT2plus} h at T2+` : o.reason ?? '') }
    catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const confirm = async (outcome: string) => {
    const d = obs?.date ?? date
    if (!d) { setErr('No day to check yet for this entity: it needs a card first.'); return }
    setBusy(true); setErr(null)
    try { const r = await postConfirm({ entityId, date: d, outcome, evidence: evidence || 'officer judgement', observedPeakPm25: obs?.observed?.peakPm25 ?? null }, headers); setDone({ seq: r.record.seq, outcome }); onDone?.(r.record.seq, outcome) }
    catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const label = (o: string) => OUTCOMES.find((x) => x.id === o)?.label ?? OUTCOME_LABELS[o] ?? o.replace(/_/g, ' ')
  return (
    <div className="space-y-2">
      {cardSaid && <Fact k="card said" v={cardSaid} />}
      <PhaseButton active={!obs} done={!!obs} busy={busy && !obs} colour={colour} onClick={fetchObs}>Fetch the station readings</PhaseButton>
      {obs && (
        <div>
          <Fact k="station" v={obs.station ? `${obs.station.name} · ${obs.station.distanceKm} km` : 'none within 25 km'} />
          <Fact k="hours observed in the windows" v={obs.observed?.hoursObserved ?? obs.hoursObserved} />
          <Fact k="observed" v={obs.observed ? `peak ${obs.observed.peakPm25} µg/m³ · AQI ${obs.observed.peakAqi} · ${obs.observed.tier}` : obs.reason ?? label(obs.outcome)} />
          <Fact k="automatic assessment" v={<span className="text-fire">{label(obs.outcome)}</span>} />
          <textarea value={evidence} onChange={(e) => setEvidence(e.target.value)} disabled={!!done} className="mt-1 h-16 w-full rounded border border-line bg-ink p-2 font-mono text-[11px] text-fg" placeholder="evidence: station, reading, time" />
          {!done && (
            <div className="grid grid-cols-2 gap-1 pt-1">
              {OUTCOMES.map((o) => <PhaseButton key={o.id} active={!busy} busy={busy} colour={o.id === 'confirmed' ? colour : '#3a414b'} onClick={() => confirm(o.id)}>{o.label}</PhaseButton>)}
            </div>
          )}
          {done && <Done>Outcome check · {label(done.outcome)} · record #{done.seq}{done.outcome === 'not_confirmed' ? ' · nothing will be credited for this day' : ''}</Done>}
        </div>
      )}
      {err && <div className="font-mono text-[11px] text-red-300">{err}</div>}
    </div>
  )
}
