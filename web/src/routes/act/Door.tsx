// /act — the only place that signs in or, in a demo build, picks a persona. After sign-in the
// viewer goes to their role's screen (PIVOT_PLAN.md §2 "Single actor door").
import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { authMode, demoMode, isSignedIn, roleHome, useAuth } from '@/lib/auth'
import { DEMO_NOTE, PERSONAS } from '@/lib/experience'
import Avatar from '@/components/Act/Avatar'

export default function Door() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const signedIn = isSignedIn(auth)
  useEffect(() => { if (auth.ready && signedIn) navigate(roleHome(auth.role), { replace: true }) }, [auth.ready, signedIn, auth.role, navigate])
  if (auth.ready && signedIn) return <Navigate to={roleHome(auth.role)} replace />
  const personas = Object.values(PERSONAS)
  return (
    <div className="min-h-full bg-ink px-4 py-6 text-fg">
      <div className="mx-auto max-w-[520px]">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-fire">Act</div>
        <h1 className="text-2xl font-semibold tracking-tight">For people who act</h1>
        <p className="mt-1 text-[13px] leading-relaxed text-mute">Principals, residents' associations, district agriculture offices, hospitals, air-quality officers and the Directorate. Everyone else needs no account: the forecast, the map and the decisions are public.</p>

        {!auth.ready && <div className="mt-4 h-40 animate-pulse rounded-xl bg-panel" />}

        {auth.ready && authMode === 'cognito' && (
          <form className="glass mt-5 space-y-3 p-4" onSubmit={async (e) => { e.preventDefault(); try { await auth.signIn(email.trim(), password) } catch { /* shown */ } }}>
            <div className="text-[13px] font-medium text-fg">Sign in</div>
            <input className="hairline h-11 w-full rounded-lg bg-ink px-3 text-base" type="email" placeholder="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
            <input className="hairline h-11 w-full rounded-lg bg-ink px-3 text-base" type="password" placeholder="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <button type="submit" className="h-12 w-full rounded-lg bg-fire text-base font-semibold text-ink">Sign in</button>
            {auth.error && <div className="font-mono text-[11px] text-red-300">{auth.error}</div>}
          </form>
        )}
        {auth.ready && authMode === 'none' && !demoMode && <div className="glass mt-5 p-4 font-mono text-[12px] text-mute">Sign-in is not configured for this build.</div>}

        {auth.ready && demoMode && (
          <div className="mt-5">
            <div className="mb-2 text-[13px] font-medium text-fg">Try it as one of the seven</div>
            <div className="grid gap-2 sm:grid-cols-2">
              {personas.map((p) => (
                <button key={p.name} type="button" disabled={!!busy} onClick={async () => { setBusy(p.name); setErr(null); try { await auth.signInAs(p); navigate(roleHome(p.role)) } catch (e) { setErr((e as Error).message) } finally { setBusy(null) } }} className="glass glass-tight flex min-h-14 items-center gap-3 px-3 text-left transition hover:border-white/20 disabled:opacity-60">
                  <Avatar p={p} size={36} />
                  <span className="min-w-0"><span className="block truncate text-[13px] text-fg">{p.name} <span className="text-mute">· {p.title}</span></span><span className="block truncate font-mono text-[10px] text-mute">{p.org} · {p.role}</span></span>
                </button>
              ))}
            </div>
            {err && <div className="mt-2 font-mono text-[11px] text-red-300">{err}</div>}
            {busy && <div className="mt-2 font-mono text-[11px] text-mute">signing in as {busy}…</div>}
            <Link to="/act/walk" className="mt-3 flex h-12 items-center justify-center gap-3 rounded-full bg-fire px-6 text-[14px] font-semibold text-ink transition hover:bg-[#ffc46a]">Start the walkthrough <span className="h-2 w-2 animate-pulse rounded-full bg-[#d7263d]" /></Link>
            <div className="mt-2 text-center font-mono text-[10px] text-mute">eight steps · seven people · a record at every step</div>
            <p className="mt-4 font-mono text-[10.5px] leading-relaxed text-mute" data-demo-note>{DEMO_NOTE}</p>
          </div>
        )}
      </div>
    </div>
  )
}
