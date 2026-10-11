// Inspect a registration and approve it: the verifier's form, shared by /act/queue and the
// walkthrough's step 3 so both are the same screen.
import { useEffect, useState } from 'react'
import { getInspect, postApprove, type InspectReport } from '@/lib/api'
import { PhaseButton, Fact, Done } from '@/components/Experience/Phase'

export const CHECKS = [
  { id: 'ndvi', label: 'Vegetation drop at the nearest cell is consistent with harvest or burning' },
  { id: 'station', label: 'A CPCB station within 25 km can check the outcome the next day' },
  { id: 'hours', label: 'The hours of concern match the school day' },
]

export default function InspectForm({ entityId, name, headers, colour = '#10B981', onDone }: { entityId: string; name?: string; headers: Record<string, string>; colour?: string; onDone?: (seq: number) => void }) {
  const [rep, setRep] = useState<InspectReport | null>(null)
  const [checked, setChecked] = useState<Record<string, boolean>>({})
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { setRep(null); setDone(null); getInspect(entityId, headers).then(setRep).catch((e) => setErr((e as Error).message)) }, [entityId])  // eslint-disable-line react-hooks/exhaustive-deps
  const already = rep?.approval ?? null
  const allChecked = CHECKS.every((c) => checked[c.id])
  const approve = async () => {
    setBusy(true); setErr(null)
    try { const r = await postApprove({ entityId, checks: CHECKS.map((c) => c.id) }, headers); setDone(r.record.seq); onDone?.(r.record.seq) }
    catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="space-y-2">
      {name && <div className="text-base font-semibold text-fg">{name}</div>}
      <Fact k="registration" v={rep?.registration ? `record #${rep.registration.seq} · ${String(rep.registration.payload.verifiedBy ?? rep.registration.by.role)}` : rep ? 'none on record' : '…'} />
      <Fact k="nearest cell" v={rep?.nearestCell ? `${rep.nearestCell.name} · crop cover ${rep.nearestCell.ndviChange ?? '—'} · ${rep.nearestCell.category}` : '—'} />
      <Fact k="nearest station" v={rep?.station ? `${rep.station.name} · ${rep.station.distanceKm} km` : rep ? 'none within 25 km' : '—'} />
      <Fact k="hours" v={rep?.hours ? `${rep.hours.join('–')} · ${rep.dismissal?.join('–')}` : '—'} />
      {already ? <Done>Already approved · record #{already.seq}</Done> : (
        <>
          <div className="pt-1 font-mono text-[11px] text-mute">Checklist</div>
          {CHECKS.map((c) => (
            <label key={c.id} className="flex min-h-10 items-start gap-2 rounded border border-line px-2 py-1.5 font-mono text-[11px] text-fg">
              <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[#10B981]" checked={!!checked[c.id]} disabled={done !== null} onChange={() => setChecked((x) => ({ ...x, [c.id]: !x[c.id] }))} />
              <span>{c.label}</span>
            </label>
          ))}
          <PhaseButton active={allChecked && done === null} done={done !== null} busy={busy} colour={colour} onClick={approve}>Approve the registration</PhaseButton>
          {done !== null && <Done>Registration approved · record #{done} · the school now gets a card every morning</Done>}
        </>
      )}
      {err && <div className="font-mono text-[11px] text-red-300">{err}</div>}
    </div>
  )
}
