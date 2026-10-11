// The one viewer (PIVOT_PLAN.md §1, §6): a Cognito user when the pool is configured, or - only
// in a build with VITE_DEMO_MODE=1 - a chosen demo persona sent as X-Dev-* headers, which the
// API honours only when its DemoAuth parameter is on. Restored once at the app root; every
// surface reads it from here.
import { create } from 'zustand'
import { AuthenticationDetails, CognitoUser, CognitoUserPool } from 'amazon-cognito-identity-js'

const POOL_ID = import.meta.env.VITE_COGNITO_USER_POOL_ID as string | undefined
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID as string | undefined
const DEV_KEY = 'mordor.devSchoolId'
const DEV_ROLE_KEY = 'mordor.devRole'
const DEV_PERSONA_KEY = 'mordor.devPersona'
const DEMO_PASSWORD = import.meta.env.VITE_DEMO_PASSWORD as string | undefined   // the seven fictional personas' shared Cognito password; public by design in a demo build

/** Persona picker and walkthrough exist only in a build that asked for them. */
export const demoMode = import.meta.env.VITE_DEMO_MODE === '1'
export const authMode: 'cognito' | 'dev' | 'none' = POOL_ID && CLIENT_ID ? 'cognito' : demoMode ? 'dev' : 'none'
const pool = authMode === 'cognito' ? new CognitoUserPool({ UserPoolId: POOL_ID!, ClientId: CLIENT_ID! }) : null

export type Role = 'operator' | 'verifier' | 'auditor' | 'analyst'
/** Where a role lands after the door. */
export const roleHome = (role: string | null): string => (role === 'operator' ? '/act/card' : role === 'verifier' ? '/act/queue' : role ? '/act/impact' : '/act')

interface AuthState {
  ready: boolean
  token: string | null
  email: string | null
  schoolId: string | null
  role: string | null
  persona: string | null          // demo persona name, never set for a Cognito user
  error: string | null
  restore: () => Promise<void>
  signIn: (email: string, password: string) => Promise<void>
  signInDev: (schoolId: string | null, role?: string, persona?: string | null) => void
  /** Become one of the demo personas: a real Cognito sign-in when the pool is configured, X-Dev headers otherwise. */
  signInAs: (p: { name: string; role: string; entityId: string | null; email: string | null }) => Promise<void>
  signOut: () => void
  headers: () => Record<string, string>
}

export const useAuth = create<AuthState>((set, get) => ({
  ready: false, token: null, email: null, schoolId: null, role: null, persona: null, error: null,
  restore: async () => {
    // a demo persona chosen earlier in this browser (only in a demo build); a Cognito session wins over it
    const demo = () => {
      if (!demoMode) { set({ ready: true }); return }
      let id: string | null = null, role: string | null = null, persona: string | null = null
      try { id = localStorage.getItem(DEV_KEY); role = localStorage.getItem(DEV_ROLE_KEY); persona = localStorage.getItem(DEV_PERSONA_KEY) } catch { /* private mode */ }
      set({ ready: true, schoolId: id, role, persona })
    }
    if (authMode !== 'cognito') { demo(); return }
    const user = pool!.getCurrentUser()
    if (!user) { demo(); return }
    user.getSession((err: Error | null, session: { isValid: () => boolean; getIdToken: () => { getJwtToken: () => string; payload: Record<string, string> } } | null) => {
      if (err || !session || !session.isValid()) { demo(); return }
      const id = session.getIdToken()
      let persona: string | null = null
      if (demoMode) { try { persona = localStorage.getItem(DEV_PERSONA_KEY) } catch { /* ignore */ } }
      set({ ready: true, token: id.getJwtToken(), email: id.payload.email ?? null, schoolId: id.payload['custom:school_id'] ?? null, role: id.payload['custom:role'] ?? (id.payload['custom:school_id'] ? 'operator' : null), persona })
    })
  },
  signIn: (email, password) => new Promise((resolve, reject) => {
    if (!pool) { reject(new Error('Sign-in is not configured for this build.')); return }
    const user = new CognitoUser({ Username: email, Pool: pool })
    user.authenticateUser(new AuthenticationDetails({ Username: email, Password: password }), {
      onSuccess: (session) => {
        const id = session.getIdToken()
        set({ token: id.getJwtToken(), email: id.payload.email ?? email, schoolId: id.payload['custom:school_id'] ?? null, role: id.payload['custom:role'] ?? (id.payload['custom:school_id'] ? 'operator' : null), persona: null, error: null })
        resolve()
      },
      onFailure: (err) => { set({ error: err.message }); reject(err) },
      newPasswordRequired: () => { set({ error: 'A new password is required; ask the team to reset it.' }); reject(new Error('new password required')) },
    })
  }),
  signInDev: (schoolId, role = 'operator', persona = null) => {
    if (!demoMode) return
    try {
      if (schoolId) localStorage.setItem(DEV_KEY, schoolId); else localStorage.removeItem(DEV_KEY)
      localStorage.setItem(DEV_ROLE_KEY, role)
      if (persona) localStorage.setItem(DEV_PERSONA_KEY, persona); else localStorage.removeItem(DEV_PERSONA_KEY)
    } catch { /* ignore */ }
    set({ schoolId, role, persona, token: null, email: null, error: null })
  },
  signInAs: async (p) => {
    if (!demoMode) throw new Error('The demo personas are not enabled in this build.')
    const role = p.role
    if (authMode === 'cognito') {
      if (!p.email || !DEMO_PASSWORD) throw new Error('This build has no demo credentials (VITE_DEMO_PASSWORD).')
      await get().signIn(p.email, DEMO_PASSWORD)
      try { localStorage.setItem(DEV_PERSONA_KEY, p.name) } catch { /* ignore */ }
      set({ persona: p.name })
      return
    }
    get().signInDev(p.entityId, role, p.name)
  },
  signOut: () => {
    pool?.getCurrentUser()?.signOut()
    try { localStorage.removeItem(DEV_KEY); localStorage.removeItem(DEV_ROLE_KEY); localStorage.removeItem(DEV_PERSONA_KEY) } catch { /* ignore */ }
    set({ token: null, email: null, schoolId: null, role: null, persona: null })
  },
  headers: () => {
    const { token, schoolId, role } = get()
    const h: Record<string, string> = {}
    if (token) h.Authorization = `Bearer ${token}`
    else if (demoMode) { if (schoolId) h['X-Dev-School-Id'] = schoolId; if (role) h['X-Dev-Role'] = role }
    return h
  },
}))

/** Signed in, by either identity. */
export const isSignedIn = (a: Pick<AuthState, 'token' | 'role'>) => !!(a.token || a.role)
/** What the chip and the "acting as" line call the viewer. */
export const viewerName = (a: Pick<AuthState, 'persona' | 'email' | 'schoolId'>) => a.persona ?? a.email ?? a.schoolId ?? 'demo'
/** An API error in words the viewer can act on: a 401 for a demo persona means the API's demo switch is off. */
export const explainError = (message: string, a: Pick<AuthState, 'persona' | 'token'>): string =>
  /401|sign in to use/i.test(message)
    ? (a.persona ? 'The demo personas are not switched on for this API (the stack was deployed with DemoAuth=0). Sign in with a real account, or ask the team to enable the demo.' : 'Your session has expired. Sign in again.')
    : message
