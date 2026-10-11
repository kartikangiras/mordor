import type { Message } from '@/lib/protocol'
import SpeakButton from './SpeakButton'

export default function MessageBox({ message }: { message: Message }) {
  return (
    <div className="rounded border border-line bg-ink p-3">
      <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-fg">{message.hi}</p>
      <p className="mt-2 whitespace-pre-wrap text-[13px] leading-relaxed text-fg/90">{message.en}</p>
      <div className="mt-2"><SpeakButton message={message} /></div>
      <div className="mt-2 flex justify-between font-mono text-[10px] text-mute">
        <span>{message.chars} / 400 characters</span>
        <span>{message.source === 'agent' ? 'drafted automatically' : message.source === 'template' ? 'standard text' : 'cached'}</span>
      </div>
    </div>
  )
}
