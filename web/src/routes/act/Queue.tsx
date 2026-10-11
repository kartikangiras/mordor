// /act/queue — the verifier's pending entity-days: inspect and approve a registration, pull the
// station readings and record the outcome. Auditors and analysts read the same queue.
import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { explainError, isSignedIn, roleHome, useAuth } from '@/lib/auth'
import { getPending } from '@/lib/api'
import type { PendingVerification } from '@/lib/protocol'
import { TIERS, type TierId } from '@/lib/aqi'
import { ACTION_LABELS } from '@/lib/labels'
import ActHeader from '@/components/Act/ActHeader'
import InspectForm from '@/components/Act/InspectForm'
import ObserveForm from '@/components/Act/ObserveForm'

export default function Queue() {
  const auth = useAuth()
  const [pending, setPending] = useState<PendingVerification[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<{ key: string; what: 'inspect' | 'observe' } | null>(null)
  const signedIn = isSignedIn(auth)
  const reload = useCallback(() => { getPending(auth.headers()).then((r) => { setPending(r.pending); setError(null) }).catch((e) => setError(explainError((e as Error).message, auth))) }, [auth])
  useEffect(() => { if (auth.ready && signedIn) reload() }, [auth.ready, signedIn, auth.token, auth.schoolId, auth.role, reload])
  if (auth.ready && !signedIn) return <Navigate to="/act" replace />
  if (auth.ready && auth.role === 'operator') return <Navigate to={roleHome(auth.role)} replace />
  const canAct = auth.role === 'verifier'
  const tierLabel = (t: string | null) => (t && t in TIERS ? TIERS[t as TierId].label : '—')
  return (
    <div className="min-h-full bg-ink px-3 py-4 text-fg">
      <div className="mx-auto max-w-[640px]">
        <ActHeader title="Awaiting an outcome" />
        {error && <div className="rounded-lg border border-red-900 bg-panel p-3 font-mono text-[12px] text-red-300">{error}</div>}
        {!error && pending === null && <div className="h-40 animate-pulse rounded-xl bg-panel" />}
        {pending && (
          <>
            <div className="mb-3 text-[13px] text-mute">{pending.length} {pending.length === 1 ? 'day' : 'days'} awaiting an outcome · <Link to="/records" className="underline">today's decisions</Link>{!canAct && <span> · read-only for {auth.role}s</span>}</div>
            <div className="space-y-2">
              {pending.map((p) => {
                const key = `${p.entityId}-${p.date}`
                const isOpen = open?.key === key
                return (
                  <div key={key} className="glass p-4">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <div className="text-[14px] font-semibold text-fg">{p.name}</div>
                      <div className="font-mono text-[11px] text-mute">{p.date}</div>
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-mute">
                      <span>forecast <span className="text-fg">{tierLabel(p.dayTier)}</span></span>
                      <span>{p.acted ? `acted: ${(p.actions ?? []).map((a) => ACTION_LABELS[a] ?? a).join(', ') || 'no actions'}` : 'not acted'}</span>
                      <span className="text-fire">{p.status.replace(/_/g, ' ')}</span>
                    </div>
                    {p.reason && <div className="mt-1 text-[11px] text-mute">{p.reason}</div>}
                    {canAct && (
                      <div className="mt-3 flex gap-2">
                        <button type="button" onClick={() => setOpen(isOpen && open?.what === 'inspect' ? null : { key, what: 'inspect' })} className={`hairline h-9 rounded-lg px-3 text-[12px] font-medium ${isOpen && open?.what === 'inspect' ? 'bg-white/10 text-fg' : 'text-fg/80 hover:bg-white/5'}`}>Registration</button>
                        <button type="button" onClick={() => setOpen(isOpen && open?.what === 'observe' ? null : { key, what: 'observe' })} className={`hairline h-9 rounded-lg px-3 text-[12px] font-medium ${isOpen && open?.what === 'observe' ? 'bg-white/10 text-fg' : 'text-fg/80 hover:bg-white/5'}`}>Outcome</button>
                      </div>
                    )}
                    {isOpen && open?.what === 'inspect' && <div className="mt-3 border-t border-white/8 pt-3"><InspectForm entityId={p.entityId} headers={auth.headers()} onDone={reload} /></div>}
                    {isOpen && open?.what === 'observe' && <div className="mt-3 border-t border-white/8 pt-3"><ObserveForm entityId={p.entityId} date={p.date} cardSaid={`${tierLabel(p.dayTier)} · ${p.date}`} headers={auth.headers()} onDone={reload} /></div>}
                  </div>
                )
              })}
              {pending.length === 0 && <div className="glass p-4 text-[13px] text-mute">Nothing waiting. Outcomes appear here the morning after a card went out.</div>}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
