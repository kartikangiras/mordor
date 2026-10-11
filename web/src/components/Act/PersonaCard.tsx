// The person who performs a walkthrough step, as the top block of the step panel (PIVOT_PLAN
// NAV-2): no overlay, no timer, the header and the rail stay reachable.
import type { ExpStep, Persona } from '@/lib/experience'
import Avatar from './Avatar'

export default function PersonaCard({ persona: p, step: st }: { persona: Persona; step: ExpStep }) {
  return (
    <div className="mb-3 rounded-xl p-3" style={{ background: `${p.colour}14`, border: `1px solid ${p.colour}44` }}>
      <div className="flex items-center gap-3">
        <Avatar p={p} size={40} />
        <div className="min-w-0">
          <div className="truncate text-[14px] font-semibold text-fg">{p.name} <span className="font-normal text-mute">· {p.title}</span></div>
          <div className="truncate text-[11px] text-mute">{p.org}</div>
        </div>
      </div>
      <p className="mt-2 text-[13px] leading-relaxed text-fg/85">{st.mission}</p>
    </div>
  )
}
