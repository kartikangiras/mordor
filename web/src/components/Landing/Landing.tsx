// The front page over the cinematic map, told the way a story site tells it: a sparse hero with
// one call to action and the platforms it runs on, then one full-screen chapter per scroll stop,
// each a single card with one number from the current run. Platform names are text, not logos:
// the Powered-by-AWS logo and the NASA insignia both carry usage terms this page does not meet.
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { demoMode } from '@/lib/auth'
import { useStore } from '@/lib/store'
import { PERSONAS } from '@/lib/experience'
import { TIERS, type TierId } from '@/lib/aqi'
import { istLabel } from '@/lib/time'
import type { Manifest } from '@/lib/api'
import { AmazonLogo, AwsLogo, NasaLogo } from './brandLogos'

const AWS_STACK = [
  { file: 'lambda', label: 'Lambda' }, { file: 'step-functions', label: 'Step Functions' }, { file: 's3', label: 'S3' }, { file: 'cloudfront', label: 'CloudFront' },
  { file: 'dynamodb', label: 'DynamoDB' }, { file: 'cognito', label: 'Cognito' }, { file: 'eventbridge', label: 'EventBridge' }, { file: 'api-gateway', label: 'API Gateway' },
]
const fmt = (n: number | null | undefined) => (n === null || n === undefined ? '—' : n.toLocaleString('en-IN'))
const PEOPLE = Object.values(PERSONAS).length

type Slide = { n: string; kicker: string; title: string; body: string; stat: (m: Manifest | null) => string; cap: string; cta: string; to: string; colour: string }
const SLIDES: Slide[] = [
  { n: '01', kicker: 'Punjab, tonight', title: 'The Fires', colour: '#ff6b35',
    body: 'Every October the paddy stubble burns, and the satellites see it the same night. Each detection is a point on our map within three hours, sized by how hard it burns.',
    stat: (m) => fmt(m?.fires.count), cap: 'VIIRS detections, last 24 h', cta: 'View the fire map', to: '/map' },
  { n: '02', kicker: 'The wind, the next two days', title: 'The Forecast', colour: '#ffb347',
    body: 'Each fire becomes smoke parcels carried by the 925 hPa wind. Hour by hour, on a 5 km grid, the forecast says how much the fires will add on top of the city’s background, and when it arrives.',
    stat: (m) => (m ? `${m.hours.length - 1} h` : '—'), cap: 'ahead, every hour, 5 km cells', cta: 'Walk the chapters', to: '/story' },
  { n: '03', kicker: 'Who is underneath it', title: 'The Schools', colour: '#10b981',
    body: 'The forecast is read at every school in the domain, through school hours and dismissal, and turned into a tier a principal can act on: normal, caution, indoors, restrict, closure advisory.',
    stat: (m) => fmt(m?.schools?.named), cap: 'schools on the map, from OpenStreetMap', cta: 'See the exposure zones', to: '/zones' },
  { n: '04', kicker: 'The next morning', title: 'The Check', colour: '#818cf8',
    body: 'Every run is scored against the monitors the next day. The fit, its errors and its interval sit on the validation page and in the footer of every card, bad days included.',
    stat: (m) => fmt(m?.calibration.stations), cap: 'stations in the hindcast', cta: 'Read the validation', to: '/validation' },
  { n: '05', kicker: 'What was done about it', title: 'The Decision', colour: '#e8ebef',
    body: 'A principal acknowledges, a colony closes its park, an officer verifies against the station. Every step leaves a plain record with a name and a time, and the next day’s check closes it.',
    stat: () => String(PEOPLE), cap: 'people in the loop, analyst to verifier', cta: 'See the decisions', to: '/records' },
]
const LAST = SLIDES.length + 1   // hero + slides + step-in

export default function Landing({ error }: { error: string | null }) {
  const manifest = useStore((s) => s.manifest)
  const zones = useStore((s) => s.zones)
  const worst = zones ? zones.zones.find((z) => z.id === zones.rankingPeak[0]) ?? null : null
  const worstTier = worst && worst.worstTier in TIERS ? (worst.worstTier as TierId) : null
  const scroller = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(0)

  // which stop is on screen (drives the dots), and the card reveal
  useEffect(() => {
    const root = scroller.current
    if (!root) return
    const sections = [...root.querySelectorAll<HTMLElement>('[data-stop]')]
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) { setActive(Number((e.target as HTMLElement).dataset.stop)); e.target.classList.add('in') }
      }
    }, { root, threshold: 0.55 })
    sections.forEach((s) => io.observe(s))
    return () => io.disconnect()
  }, [])
  const go = (i: number) => scroller.current?.querySelector<HTMLElement>(`[data-stop="${Math.max(0, Math.min(LAST, i))}"]`)?.scrollIntoView({ behavior: 'smooth' })

  return (
    <>
      <div ref={scroller} className="absolute inset-0 snap-y snap-mandatory overflow-y-auto overscroll-contain">
        {/* hero */}
        <section data-stop={0} className="reveal in relative flex min-h-full snap-start flex-col items-center justify-center px-6 pb-16 pt-5 text-center">
          <div className="hero-glow" />
          <img src="/brand/mark-512.png" alt="" width={96} height={96} className="relative h-24 w-24 max-sm:h-20 max-sm:w-20" style={{ filter: 'drop-shadow(0 0 28px rgba(255,107,53,0.35))' }} />
          <div className="relative mt-3 font-mono text-[11px] uppercase tracking-[0.3em] text-fire">■ mordor · धुआँ · Punjab → Delhi, October</div>
          <h1 className="relative mt-5 text-fg" style={{ fontSize: 'clamp(2.6rem, 8vw, 6.5rem)', fontWeight: 300, letterSpacing: '-0.045em', lineHeight: 0.95 }}>
            Tomorrow's smoke,<br /><em className="font-display italic text-fire">as a decision.</em>
          </h1>
          <p className="relative mt-5 max-w-xl text-[15px] leading-relaxed text-fg/65">Tonight's stubble smoke, hour by hour, for the next two days.</p>
          {worst && worstTier && (
            <div className="relative mt-3 flex flex-wrap items-center justify-center gap-x-2 font-mono text-[11px] uppercase tracking-[0.18em] text-fg/70">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: TIERS[worstTier].colour }} />
              <span>worst in 48 h · {worst.name} · {TIERS[worstTier].label}{worst.peak?.t ? ` · ${istLabel(worst.peak.t)}` : ''}</span>
            </div>
          )}
          <div className="relative mt-7 flex flex-wrap items-center justify-center gap-3">
            <Link to="/story/1" className="flex h-12 items-center gap-3 rounded-full px-7 font-mono text-[12px] uppercase tracking-[0.18em] text-fg transition hover:scale-[1.04]" style={{ background: 'rgba(255,255,255,0.06)', border: '1.5px solid rgba(255,255,255,0.28)', backdropFilter: 'blur(10px)' }}>
              Explore the story <span className="h-2 w-2 rounded-full bg-fire" />
            </Link>
            <Link to={demoMode ? '/act/walk' : '/act'} className="flex h-12 items-center gap-3 rounded-full px-7 font-mono text-[12px] uppercase tracking-[0.18em] text-fg transition hover:scale-[1.04]" style={{ background: 'rgba(255,179,71,0.16)', border: '1.5px solid rgba(255,179,71,0.55)', backdropFilter: 'blur(10px)' }}>
              Action plan <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-[#d7263d]" />
            </Link>
          </div>
          {error && <div className="relative mt-4 font-mono text-xs text-red-300">No run available: {error}</div>}
          <div className="relative mt-8 font-mono text-[10px] uppercase tracking-[0.3em] text-mute">■ Powered by</div>
          <div className="relative mt-4 flex items-center justify-center gap-12 text-fg/85 max-sm:gap-8">
            <AwsLogo className="h-9 w-auto max-sm:h-7" />
            <NasaLogo className="h-8 w-auto max-sm:h-6" />
            <AmazonLogo className="h-8 w-auto max-sm:h-6" />
          </div>
          <div className="relative mt-6 flex flex-wrap items-start justify-center gap-x-5 gap-y-3 max-sm:gap-x-3">
            {AWS_STACK.map((s) => (
              <div key={s.file} className="flex w-[68px] flex-col items-center gap-1.5 max-sm:w-[64px]">
                <img src={`/logos/aws/${s.file}.svg`} alt={s.label} width={40} height={40} className="h-9 w-9 rounded-[9px] shadow-[0_8px_24px_-8px_rgba(0,0,0,0.8)]" />
                <span className="text-center font-mono text-[9px] uppercase leading-tight tracking-[0.12em] text-mute">{s.label}</span>
              </div>
            ))}
          </div>
        </section>

        {/* chapters */}
        {SLIDES.map((s, i) => (
          <section key={s.n} data-stop={i + 1} className="reveal relative flex h-full snap-start items-center px-6 max-sm:items-end max-sm:pb-24">
            <div className="pointer-events-none absolute inset-0" style={{ background: 'linear-gradient(90deg, rgba(11,13,16,0) 35%, rgba(11,13,16,0.6) 70%, rgba(11,13,16,0.85) 100%)' }} />
            <div className="card glass relative ml-auto w-[min(520px,100%)] p-8 max-sm:p-6 lg:mr-[4vw]">
              <div className="font-mono text-[11px] uppercase tracking-[0.3em]" style={{ color: s.colour }}>■ Chapter {s.n}</div>
              <div className="mt-1.5 font-mono text-[11px] uppercase tracking-[0.2em] text-mute">{s.kicker}</div>
              <h2 className="mt-5 text-fg" style={{ fontSize: 'clamp(2.4rem, 5vw, 3.6rem)', fontWeight: 300, letterSpacing: '-0.035em', lineHeight: 1 }}>{s.title}</h2>
              <p className="mt-5 text-[15px] leading-relaxed text-fg/80">{s.body}</p>
              <div className="mt-7 font-mono text-[56px] font-light leading-none tracking-tight max-sm:text-[44px]" style={{ color: s.colour }}>{s.stat(manifest)}</div>
              <div className="mt-2 font-mono text-[11px] uppercase tracking-[0.2em] text-mute">{s.cap}</div>
              <Link to={s.to} className="mt-7 inline-flex h-11 items-center gap-3 rounded-full border border-white/20 px-6 font-mono text-[12px] uppercase tracking-[0.15em] text-fg transition hover:border-white/50 hover:bg-white/5">
                {s.cta} <span className="h-2 w-2 rounded-full" style={{ background: s.colour }} />
              </Link>
            </div>
          </section>
        ))}

        {/* step in */}
        <section data-stop={LAST} className="reveal relative flex h-full snap-start flex-col items-center justify-center px-6 text-center">
          <div className="pointer-events-none absolute inset-0 bg-ink/60" />
          <div className="card relative">
            <div className="font-mono text-[11px] uppercase tracking-[0.3em] text-fire">■ Chapter 06</div>
            <h2 className="mt-5 text-fg" style={{ fontSize: 'clamp(2.6rem, 6vw, 4.5rem)', fontWeight: 300, letterSpacing: '-0.04em', lineHeight: 1 }}>Step in</h2>
            <p className="mx-auto mt-5 max-w-lg text-[15px] leading-relaxed text-fg/75">Everything above is live. Walk the eight steps of one bad day with the seven people in the loop, each ending in a decision that leaves a record.</p>
            <Link to={demoMode ? '/act/walk' : '/act'} className="glass mx-auto mt-9 flex w-[min(460px,100%)] items-center justify-between px-6 py-4 text-left transition hover:border-fire/50">
              <span>
                <span className="block text-[18px] font-medium text-fg">{demoMode ? 'Enter the walkthrough' : 'For people who act'}</span>
                <span className="block font-mono text-[11px] text-mute">{demoMode ? '8 steps · seven people · a record at every step' : 'sign in to your card, queue or impact screen'}</span>
              </span>
              <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-[#d7263d]" />
            </Link>
            <div className="mx-auto mt-14 max-w-2xl font-mono text-[10px] leading-relaxed text-mute/80">
              Built on AWS. Data: NASA FIRMS, Copernicus CAMS, Open-Meteo, OpenAQ, © OpenStreetMap contributors. A hackathon project, not affiliated with or endorsed by NASA, Amazon or AWS. Not for medical decisions.
            </div>
          </div>
        </section>
      </div>

      {/* bottom chrome, fixed over the scroll */}
      <div className="pointer-events-none absolute bottom-5 left-6 z-10 font-mono text-[10px] uppercase leading-relaxed tracking-[0.2em] text-mute max-sm:hidden">■ 2026<br />Tomorrow's smoke</div>
      <div className="absolute bottom-5 left-1/2 z-10 flex -translate-x-1/2 items-center gap-2">
        <button type="button" onClick={() => go(active - 1)} disabled={active === 0} aria-label="Previous" className="hairline flex h-9 w-9 items-center justify-center rounded-full text-fg disabled:opacity-30 hover:bg-white/5">‹</button>
        <div className="flex items-center gap-2 px-1" role="tablist" aria-label="Sections">
          {Array.from({ length: LAST + 1 }, (_, i) => (
            <button key={i} type="button" role="tab" aria-selected={active === i} aria-label={i === 0 ? 'Top' : i === LAST ? 'Step in' : SLIDES[i - 1].title} onClick={() => go(i)} className={`h-2 w-2 rounded-full transition ${active === i ? 'scale-125 bg-fire' : 'bg-white/30 hover:bg-white/60'}`} />
          ))}
        </div>
        <button type="button" onClick={() => go(active + 1)} disabled={active === LAST} aria-label="Next" className="hairline flex h-9 w-9 items-center justify-center rounded-full text-fg disabled:opacity-30 hover:bg-white/5">›</button>
      </div>
      <div className={`pointer-events-none absolute bottom-12 right-6 z-10 font-mono text-[10px] uppercase tracking-[0.3em] text-mute transition max-sm:hidden ${active === LAST ? 'opacity-0' : ''}`}>scroll ↓</div>
    </>
  )
}
