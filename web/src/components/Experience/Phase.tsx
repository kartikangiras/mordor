// A guided phase: a pulsing call to action until done, then a quiet tick. The whole experience
// is built from these so every step reads the same way.
import type { ReactNode } from 'react'

export function PhaseButton({ children, onClick, active, done, busy, colour = '#ffb347' }: { children: ReactNode; onClick: () => void; active: boolean; done?: boolean; busy?: boolean; colour?: string }) {
  if (done) return <div className="flex h-10 items-center gap-2 rounded border border-line px-3 font-mono text-[11px] text-mute"><span style={{ color: colour }}>✓</span>{children}</div>
  return (
    <button type="button" onClick={onClick} disabled={!active || busy}
      className="flex h-11 w-full items-center justify-center gap-2 rounded border px-3 font-mono text-[12px] font-semibold text-ink transition disabled:opacity-30"
      style={{ background: active ? colour : '#262c34', borderColor: colour, animation: active && !busy ? 'vd-pulse 2s ease-in-out infinite' : undefined, boxShadow: active ? `0 0 0 0 ${colour}` : undefined }}>
      {busy ? 'working…' : children}
    </button>
  )
}

export function Fact({ k, v }: { k: string; v: ReactNode }) {
  return <div className="flex justify-between gap-3 border-t border-line py-1 font-mono text-[11px]"><span className="text-mute">{k}</span><span className="text-right text-fg">{v}</span></div>
}

export function Done({ children }: { children: ReactNode }) {
  return <div className="mt-2 rounded border border-line bg-ink p-2 font-mono text-[11px] text-mute">{children}</div>
}
