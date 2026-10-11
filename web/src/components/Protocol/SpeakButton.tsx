// Play the advisory aloud, Hindi first. Hidden entirely when the device has no suitable voice,
// so nobody is offered a control that does nothing (see lib/speak.ts).
import { useEffect, useState } from 'react'
import { canSpeak, hasVoiceFor, speak, stopSpeaking, type SpeakLang } from '@/lib/speak'
import type { Message } from '@/lib/protocol'

export default function SpeakButton({ message }: { message: Message }) {
  const [available, setAvailable] = useState<Record<SpeakLang, boolean>>({ hi: false, en: false })
  const [playing, setPlaying] = useState<SpeakLang | null>(null)

  useEffect(() => {
    let live = true
    if (!canSpeak()) return
    void Promise.all([hasVoiceFor('hi'), hasVoiceFor('en')]).then(([hi, en]) => {
      if (live) setAvailable({ hi, en })
    })
    return () => {
      live = false
      stopSpeaking()
    }
  }, [])

  const play = async (lang: SpeakLang) => {
    if (playing) {
      stopSpeaking()
      setPlaying(null)
      return
    }
    setPlaying(lang)
    await speak(lang === 'hi' ? message.hi : message.en, lang)
    setPlaying(null)
  }

  const langs = (['hi', 'en'] as SpeakLang[]).filter((l) => available[l])
  if (!langs.length) return null

  return (
    <div className="flex gap-2">
      {langs.map((l) => (
        <button
          key={l}
          type="button"
          onClick={() => void play(l)}
          aria-label={playing === l ? 'Stop reading the advisory aloud' : `Read the advisory aloud in ${l === 'hi' ? 'Hindi' : 'English'}`}
          className="flex h-10 flex-1 items-center justify-center gap-2 rounded border border-line bg-panel font-mono text-[12px] text-fg active:opacity-80"
        >
          <span aria-hidden>{playing === l ? '■' : '▶'}</span>
          {playing === l ? 'Stop' : `Listen · ${l === 'hi' ? 'हिंदी' : 'English'}`}
        </button>
      ))}
    </div>
  )
}
