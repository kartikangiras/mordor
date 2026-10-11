// The one header every route renders (PIVOT_PLAN.md §2 "Shell"). It replaces three navs that
// disagreed with each other and vanished inside the experience: the landing's 11px link row, the
// map's TopBar links, and /me's brand-only header. Links are router NavLinks (no reloads), sized
// for touch, state-aware (aria-current), and the identity chip reads the auth store so it can
// never say "sign in" to a signed-in person.
import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { brand } from '@/config/brand'
import { demoMode, isSignedIn, useAuth, viewerName } from '@/lib/auth'
import RunPopover from './RunPopover'

const LINKS: { to: string; label: string; end?: boolean; accent?: boolean }[] = [
  { to: '/', label: 'Forecast', end: true },
  { to: '/map', label: 'Map' },
  { to: '/story', label: 'Story' },
  { to: '/zones', label: 'Zones' },
  { to: '/validation', label: 'Validation' },
  { to: '/records', label: 'Decisions' },
  { to: demoMode ? '/act/walk' : '/act', label: 'Action plan', accent: true },
]

const linkClass = (accent?: boolean) => ({ isActive }: { isActive: boolean }) =>
  `flex h-11 items-center px-3 text-[13px] font-medium transition ${isActive ? 'text-fg shadow-[inset_0_-2px_0_0_var(--color-fire)]' : accent ? 'text-fire hover:text-fg' : 'text-mute hover:text-fg'}`

export default function Header() {
  const auth = useAuth()
  const [open, setOpen] = useState(false)
  const signedIn = isSignedIn(auth)
  const who = signedIn ? `${viewerName(auth)} · ${auth.role ?? 'operator'}` : 'Sign in'

  return (
    <header className="relative z-50 flex h-[var(--header-h)] shrink-0 items-center gap-2 border-b border-white/8 bg-ink/85 px-3 backdrop-blur-xl sm:px-4">
      <Link to="/" className="flex items-baseline gap-2 pr-2" onClick={() => setOpen(false)}>
        <img src="/brand/mark-64.png" alt="" width={28} height={28} className="h-7 w-7 translate-y-[6px]" />
        <span className="text-[17px] font-semibold tracking-tight text-fg">{brand.name}</span>
        <span className="text-xs text-mute max-sm:hidden">{brand.nameHi}</span>
      </Link>

      <nav className="flex flex-1 items-center max-sm:hidden" aria-label="Primary">
        {LINKS.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end} className={linkClass(l.accent)}>{l.label}</NavLink>
        ))}
      </nav>

      <div className="ml-auto flex items-center gap-2">
      <RunPopover />
      <Link
        to="/act"
        onClick={() => setOpen(false)}
        className={`flex h-9 max-w-[46vw] items-center truncate rounded-full border px-3.5 text-[12px] font-medium ${signedIn ? 'border-fire/60 bg-fire/10 text-fg' : 'border-white/10 bg-white/5 text-fg/80 hover:bg-white/10 hover:text-fg'}`}
        title={signedIn ? 'Your screen' : 'Sign in'}
      >
        {who}
      </Link>
      </div>

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="primary-menu"
        aria-label="Menu"
        className="hidden h-9 w-9 items-center justify-center rounded-lg border border-white/10 text-sm text-mute max-sm:flex"
      >
        {open ? '✕' : '≡'}
      </button>

      {open && (
        <nav id="primary-menu" aria-label="Primary" className="absolute left-0 right-0 top-full z-50 flex flex-col border-b border-white/8 bg-ink/95 p-2 shadow-xl backdrop-blur-xl sm:hidden">
          {LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.end} className={linkClass(l.accent)} onClick={() => setOpen(false)}>{l.label}</NavLink>
          ))}
        </nav>
      )}
    </header>
  )
}
