// /act/impact — the auditor's and analyst's screen: account the day for every exposure entity,
// read the impact report, open the decisions.
import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { explainError, isSignedIn, roleHome, useAuth } from '@/lib/auth'
import { useStore } from '@/lib/store'
import { getImpact, postAccount, type ImpactReport } from '@/lib/api'
import type { DecisionRecord } from '@/lib/protocol'
import { PhaseButton, Fact, Done } from '@/components/Experience/Phase'
import ActHeader from '@/components/Act/ActHeader'

export default function Impact() {
  const auth = useAuth()
  const { manifest, entities, load } = useStore()
  const [stmts, setStmts] = useState<DecisionRecord[]>([])
  const [totals, setTotals] = useState<ImpactReport | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { if (!manifest) void load() }, [manifest, load])
  useEffect(() => { getImpact().then(setTotals).catch(() => null) }, [])
  const signedIn = isSignedIn(auth)
  if (auth.ready && !signedIn) return <Navigate to="/act" replace />
  if (auth.ready && (auth.role === 'operator' || auth.role === 'verifier')) return <Navigate to={roleHome(auth.role)} replace />
  const actors = (entities?.features ?? []).map((f) => f.properties).filter((a) => a.kind === 'exposure')
  const compute = async () => {
    setBusy(true); setErr(null)
    try {
      const out: DecisionRecord[] = []
      for (const a of actors) { if (!a.date) continue; try { out.push((await postAccount({ entityId: a.id, date: a.date }, auth.headers())).record) } catch (e) { setErr(explainError((e as Error).message, auth)) } }
      setStmts(out)
      setTotals(await getImpact(actors.find((a) => a.date)?.date ?? undefined).catch(() => null))
      setDone(true)
    } finally { setBusy(false) }
  }
  return (
    <div className="min-h-full bg-ink px-3 py-4 text-fg">
      <div className="mx-auto max-w-[640px]">
        <ActHeader title="Impact" />
        <div className="glass p-4">
          <div className="font-mono text-[11px] text-mute">{actors.length} schools, associations and offices with a card</div>
          <div className="mt-2"><PhaseButton active={!done && actors.length > 0} done={done} busy={busy} colour="#60A5FA" onClick={compute}>Issue the impact statements for the day</PhaseButton></div>
          {stmts.map((r) => <Done key={r.id}>{r.entity} · <span className="text-fg">{String(r.payload.value)} {String(r.payload.unit)}</span> · {String(r.payload.status).replace(/_/g, ' ')}{r.payload.outcome ? ` (${String(r.payload.outcome).replace(/_/g, ' ')})` : ''}</Done>)}
          {err && <div className="mt-2 font-mono text-[11px] text-red-300">{err}</div>}
          <div className="mt-3 font-mono text-[10px] text-mute">Unit: people × hours of the windows of concern at T2 or worse. Credited only when the nearest station confirmed the day. A false alarm credits nothing.</div>
        </div>
        {totals && (
          <div className="glass mt-3 p-4">
            <div className="text-[13px] font-semibold text-fg">Every entity, {totals.date}</div>
            <Fact k="decisions logged" v={totals.decisionsLogged} />
            <Fact k="people covered" v={totals.people} />
            <Fact k="statements" v={`${totals.records.verified} verified · ${totals.records.provisional} provisional · ${totals.records.notCredited} not credited`} />
            {Object.entries(totals.records.verifiedByUnit).map(([u, v]) => <Fact key={u} k={u} v={v} />)}
            <div className="mt-2 font-mono text-[11px] text-mute"><Link to="/records" className="underline">today's decisions</Link></div>
          </div>
        )}
      </div>
    </div>
  )
}
