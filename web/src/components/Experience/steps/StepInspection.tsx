import { useStore } from '@/lib/store'
import { PhaseButton } from '../Phase'
import InspectForm from '@/components/Act/InspectForm'
import { pickActor, type StepProps } from './common'
import { useState } from 'react'

export default function StepInspection({ area, d, headers, onComplete, colour, school }: StepProps) {
  const entities = useStore((s) => s.entities)
  const fallback = pickActor(d, entities, area, { type: 'school', kind: 'exposure' })
  const actor = school ? { id: school.id, name: school.name } : fallback ? { id: fallback.id, name: fallback.name } : null
  const [done, setDone] = useState(false)
  if (!actor) return <div className="font-mono text-[11px] text-mute">Nothing to inspect.</div>
  return (
    <div className="space-y-2">
      <InspectForm entityId={actor.id} name={actor.name} headers={headers} colour={colour} onDone={() => setDone(true)} />
      <PhaseButton active={done} colour={colour} onClick={onComplete}>Hand over to Gurpreet →</PhaseButton>
    </div>
  )
}
