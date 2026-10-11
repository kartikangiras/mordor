// Read an advisory aloud with the browser's own speech synthesiser.
//
// Why: the message is written for parents, and a meaningful share of the recipients read Hindi
// slowly or not at all. Speech costs nothing here - no AWS service, no key, no network - and it
// is the only part of the notify path that works while no model key is configured, because it reads
// whatever text the card already has (template or agent).
//
// Support is uneven: Web Speech API is absent in some browsers and some Android WebViews, and
// voice lists load asynchronously in Chrome. Every entry point therefore degrades to "no voice"
// rather than throwing, and the caller is expected to hide the control when `canSpeak()` is false.

export type SpeakLang = 'hi' | 'en'

const LOCALE: Record<SpeakLang, string> = { hi: 'hi-IN', en: 'en-IN' }

export function canSpeak(): boolean {
  try {
    return typeof window !== 'undefined' && 'speechSynthesis' in window
      && typeof window.SpeechSynthesisUtterance === 'function'
  } catch {
    return false
  }
}

/** Chrome populates voices asynchronously; resolve once they arrive, or give up quietly. */
function voices(): Promise<SpeechSynthesisVoice[]> {
  if (!canSpeak()) return Promise.resolve([])
  const have = window.speechSynthesis.getVoices()
  if (have.length) return Promise.resolve(have)
  return new Promise((resolve) => {
    const done = () => resolve(window.speechSynthesis.getVoices())
    const timer = window.setTimeout(done, 1000)
    window.speechSynthesis.addEventListener('voiceschanged', () => {
      window.clearTimeout(timer)
      done()
    }, { once: true })
  })
}

async function pickVoice(lang: SpeakLang): Promise<SpeechSynthesisVoice | null> {
  const want = LOCALE[lang]
  const all = await voices()
  // exact locale, then same language, then nothing: an en-GB voice reading Hindi is worse
  // than silence, so Hindi never falls back to a non-Hindi voice.
  return all.find((v) => v.lang === want)
    ?? all.find((v) => v.lang?.toLowerCase().startsWith(`${lang}-`))
    ?? (lang === 'en' ? all.find((v) => v.lang?.toLowerCase().startsWith('en')) ?? null : null)
}

/** True when a voice exists for this language on this device. */
export async function hasVoiceFor(lang: SpeakLang): Promise<boolean> {
  return (await pickVoice(lang)) !== null
}

export function stopSpeaking(): void {
  if (!canSpeak()) return
  try {
    window.speechSynthesis.cancel()
  } catch {
    /* some WebViews throw on cancel with an empty queue */
  }
}

/**
 * Speak `text` in `lang`. Resolves when playback ends, is cancelled, or cannot start.
 * Never rejects: a missing voice is a normal outcome, not an error to surface to a principal.
 */
export function speak(text: string, lang: SpeakLang): Promise<void> {
  if (!canSpeak() || !text.trim()) return Promise.resolve()
  return new Promise<void>((resolve) => {
    void pickVoice(lang).then((voice) => {
      if (!voice) return resolve()
      try {
        stopSpeaking()
        const u = new SpeechSynthesisUtterance(text)
        u.voice = voice
        u.lang = voice.lang || LOCALE[lang]
        u.rate = 0.95       // advisories are read slightly slow on purpose
        u.pitch = 1
        u.onend = () => resolve()
        u.onerror = () => resolve()
        window.speechSynthesis.speak(u)
      } catch {
        resolve()
      }
    })
  })
}
