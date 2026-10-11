// Send to parent groups = WhatsApp deep link (DESIGN.md §6.5); copy and email as fallbacks.
// Every path logs the decision through /ack so the DoE trail is complete.
import { useState } from 'react'
import { waLink, type Message } from '@/lib/protocol'

export default function SendButton({ message, onSent, onEmail, busy, audience, canEmail }: {
  message: Message
  audience?: string
  onSent: (via: 'whatsapp' | 'copy' | 'email') => Promise<void>
  onEmail: () => Promise<string>
  busy: boolean
  /** No SES sender or no address on file means POST /api/me/email answers 501, so the button
   *  would only ever show an error. Offer it when there is somewhere to send. */
  canEmail?: boolean
}) {
  const [note, setNote] = useState<string | null>(null)
  const copy = async () => {
    try { await navigator.clipboard.writeText(`${message.hi}\n\n${message.en}`); setNote('Copied.') } catch { setNote('Copy failed; long-press the message to copy.') }
    await onSent('copy')
  }
  const email = async () => {
    try { setNote(`Emailing ${await onEmail()}…`); await onSent('email'); setNote('Email sent.') } catch (e) { setNote((e as Error).message) }
  }
  return (
    <div className="space-y-2">
      <a href={waLink(message)} target="_blank" rel="noopener" onClick={() => { void onSent('whatsapp') }}
        className="flex h-12 w-full items-center justify-center rounded bg-[#25D366] text-base font-semibold text-ink active:opacity-80">
        Send to {audience ?? 'parent'} groups
      </a>
      <div className={canEmail ? 'grid grid-cols-2 gap-2' : 'grid grid-cols-1 gap-2'}>
        <button type="button" onClick={copy} disabled={busy} className="h-11 rounded border border-line bg-panel text-sm text-fg disabled:opacity-50">Copy</button>
        {canEmail && <button type="button" onClick={email} disabled={busy} className="h-11 rounded border border-line bg-panel text-sm text-fg disabled:opacity-50">Email school</button>}
      </div>
      {note && <div className="font-mono text-[11px] text-mute">{note}</div>}
    </div>
  )
}
