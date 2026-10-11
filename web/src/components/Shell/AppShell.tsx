// Layout route for the whole app: the header on every surface, identity restored exactly once
// at the root (it used to be restored only on /me, so a returning signed-in visitor who landed on
// / sent unauthenticated headers to the step APIs until they visited /me), and a body that fills
// the rest of the viewport so map overlays are confined below the header rather than over it.
import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import Header from './Header'
import { useAuth } from '@/lib/auth'

export default function AppShell() {
  const restore = useAuth((s) => s.restore)
  useEffect(() => { void restore() }, [restore])
  return (
    <div className="flex h-full flex-col bg-ink text-fg">
      <Header />
      <div className="relative min-h-0 flex-1">
        <Outlet />
      </div>
    </div>
  )
}
