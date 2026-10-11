// The actor side's own line: who is acting, in which role, the role's screens, and sign out.
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { isSignedIn, useAuth, viewerName } from '@/lib/auth'

const TABS: Record<string, { to: string; label: string }[]> = {
  operator: [{ to: '/act/card', label: 'Card' }],
  verifier: [{ to: '/act/queue', label: 'Queue' }, { to: '/act/impact', label: 'Impact' }],
  auditor: [{ to: '/act/queue', label: 'Queue' }, { to: '/act/impact', label: 'Impact' }],
  analyst: [{ to: '/act/queue', label: 'Queue' }, { to: '/act/impact', label: 'Impact' }],
}

export default function ActHeader({ title }: { title: string }) {
  const auth = useAuth()
  const navigate = useNavigate()
  if (!isSignedIn(auth)) return null
  const tabs = TABS[auth.role ?? ''] ?? []
  return (
    <div className="mb-4">
      <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-[11px] text-mute">
        <div>acting as <span className="text-fg">{viewerName(auth)}</span> · {auth.role}{auth.persona ? ' · demo' : ''}</div>
        <div className="flex items-center gap-3">
          <Link to="/records" className="underline hover:text-fg">decisions</Link>
          <button type="button" onClick={() => { auth.signOut(); navigate('/act') }} className="h-9 underline hover:text-fg">sign out</button>
        </div>
      </div>
      <div className="mt-2 flex items-center gap-3">
        <h1 className="text-xl font-semibold text-fg">{title}</h1>
        {tabs.length > 1 && (
          <nav className="ml-auto flex gap-1" aria-label="Your screens">
            {tabs.map((t) => <NavLink key={t.to} to={t.to} className={({ isActive }) => `h-8 rounded-lg px-3 text-[12px] font-medium leading-8 ${isActive ? 'bg-white/10 text-fg' : 'text-mute hover:text-fg'}`}>{t.label}</NavLink>)}
          </nav>
        )}
      </div>
    </div>
  )
}
