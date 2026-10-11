// /act/card — the operator's protocol card (exposure) or source card, with ack and send.
import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { explainError, isSignedIn, roleHome, useAuth } from '@/lib/auth'
import { getMe, getMyForecast, postAck, postEmail } from '@/lib/api'
import type { Card as CardT } from '@/lib/protocol'
import ProtocolCard from '@/components/Protocol/ProtocolCard'
import SourceCard from '@/components/Protocol/SourceCard'
import ActHeader from '@/components/Act/ActHeader'
import Footer from '@/components/Footer'
import AssessmentBox from '@/components/Act/AssessmentBox'

export default function Card() {
  const auth = useAuth()
  const [me, setMe] = useState<Awaited<ReturnType<typeof getMe>> | null>(null)
  const [card, setCard] = useState<CardT | null>(null)
  const [actions, setActions] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string | null>(null)
  const signedIn = isSignedIn(auth)
  useEffect(() => {
    if (!auth.ready || !signedIn) return
    setError(null); setCard(null); setMe(null)
    const h = auth.headers()
    getMe(h).then(async (m) => { setMe(m); if (m.entityId) { const c = await getMyForecast(h); setCard(c); setActions(c.acked?.actions ?? c.defaultActions) } }).catch((e) => setError(explainError((e as Error).message, auth)))
  }, [auth.ready, signedIn, auth.token, auth.schoolId, auth.role])  // eslint-disable-line react-hooks/exhaustive-deps
  if (auth.ready && !signedIn) return <Navigate to="/act" replace />
  if (auth.ready && auth.role && auth.role !== 'operator') return <Navigate to={roleHome(auth.role)} replace />
  const ack = async (via: 'whatsapp' | 'copy' | 'email') => {
    if (!card) return
    setBusy(true)
    try {
      const r = await postAck(card.school.id, { runId: card.runId, actions, sentVia: via }, auth.headers())
      setCard({ ...card, acked: r.log, log: [r.log, ...card.log.filter((l) => l.runId !== r.log.runId)], message: r.message })
      setNote(`Logged as record #${r.record?.seq ?? '?'}`)
    } catch (e) { setError(explainError((e as Error).message, auth)) } finally { setBusy(false) }
  }
  const sendEmail = async () => { const r = await postEmail(card!.runId, auth.headers()); return r.to }
  const toggle = (id: string) => setActions((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]))
  return (
    <div className="min-h-full bg-ink px-3 py-4 text-fg">
      <div className="mx-auto max-w-[480px]">
        <ActHeader title="Your card" />
        {error && <div className="rounded-lg border border-red-900 bg-panel p-3 font-mono text-[12px] text-red-300">{error}</div>}
        {!error && !me && <div className="h-96 animate-pulse rounded-xl bg-panel" />}
        {me && !me.entityId && <div className="glass p-3 font-mono text-xs text-mute">This login has no school, association or office attached yet. Ask the team to onboard one.</div>}
        {card && (card.kind === 'source'
          ? <SourceCard card={card} actions={actions} busy={busy} onToggle={toggle} onSent={ack} onEmail={sendEmail} />
          : <ProtocolCard card={card} actions={actions} busy={busy} onToggle={toggle} onSent={ack} onEmail={sendEmail} />)}
        {card && card.kind !== 'source' && <div className="mt-3"><AssessmentBox entityId={card.school.id} runId={card.runId} actions={actions} headers={auth.headers()} onAdd={toggle} /></div>}
        {note && <div className="mt-2 font-mono text-[11px] text-mute">{note} · <Link to={`/records/${encodeURIComponent(card?.school.id ?? '')}`} className="underline">see the decisions</Link></div>}
        <Footer runId={card?.runId ?? me?.runId} calibration={card?.calibration ?? null} />
      </div>
    </div>
  )
}
