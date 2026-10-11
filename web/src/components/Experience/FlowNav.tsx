import { EXP_STEPS, PERSONAS, stepOpen } from '@/lib/experience'

/** The step rail. Steps unlock in order: a locked step shows who has to finish first. */
export default function FlowNav({ step, complete, onGo, onLeave, onReset }: { step: number; complete: Record<number, boolean>; onGo: (i: number) => void; onLeave: () => void; onReset?: () => void }) {
  return (
    <div className="pointer-events-none absolute left-4 right-4 top-4 z-30 flex justify-center">
    <div className="glass pointer-events-auto flex max-w-full items-center gap-0.5 overflow-x-auto !rounded-full px-1.5 py-1 font-mono text-[10px]" role="navigation" aria-label="Steps">
      {EXP_STEPS.map((s, i) => {
        const p = PERSONAS[s.persona]
        const open = stepOpen(i, complete)
        const firstMissing = EXP_STEPS.findIndex((_, k) => k < i && !complete[k])
        const title = open ? `${s.title} · ${p.name}` : `Locked until ${PERSONAS[EXP_STEPS[firstMissing].persona].name} finishes ${EXP_STEPS[firstMissing].short}`
        return (
          <button key={s.id} type="button" onClick={() => open && onGo(i)} disabled={!open} aria-disabled={!open} title={title}
            className={`flex h-8 shrink-0 items-center gap-1 rounded-full px-2 transition ${i === step ? 'bg-white/10 text-fg' : complete[i] ? 'text-fg' : open ? 'text-mute hover:text-fg' : 'cursor-not-allowed text-mute/50'}`}>
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: i === step || complete[i] ? p.colour : '#3a414b' }} />
            {i + 1} {s.short}{complete[i] ? ' ✓' : ''}
          </button>
        )
      })}
      <span className="mx-0.5 h-5 w-px shrink-0 bg-white/10" aria-hidden />
      {onReset && <button type="button" onClick={onReset} className="h-8 w-8 shrink-0 rounded-full text-mute hover:text-fg" title="Start over" aria-label="Start over">↺</button>}
      <button type="button" onClick={onLeave} className="h-8 w-8 shrink-0 rounded-full text-mute hover:text-fg" title="Leave the walkthrough" aria-label="Leave the walkthrough">✕</button>
    </div>
    </div>
  )
}
