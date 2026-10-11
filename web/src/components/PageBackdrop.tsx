// The backdrop under a reading page (PIVOT_PLAN.md task 43): one NASA Worldview image, dimmed,
// behind glass panels, so the decisions, zones and validation pages speak the landing's language
// instead of sitting on flat ink. The inline placeholder paints first; the image fades in when it
// has decoded. Fixed on wide screens so the content scrolls over it; in flow under 640 px, where
// fixed backgrounds misbehave on iOS. A credit line names the source: NASA imagery is public
// domain, and the page says where it came from.
import { useState } from 'react'
import { BACKDROPS, type BackdropId } from '@/config/backdrops'

export default function PageBackdrop({ image, position = 'center' }: { image: BackdropId; position?: string }) {
  const b = BACKDROPS[image]
  const [ready, setReady] = useState(false)
  return (
    <>
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden sm:fixed sm:inset-x-0 sm:bottom-0 sm:top-[var(--header-h)]" data-backdrop={image}>
        <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: `url(${b.lqip})`, filter: 'brightness(.55) saturate(.85)' }} />
        <img
          src={b.src}
          alt=""
          decoding="async"
          loading="eager"
          {...{ fetchpriority: 'low' }}
          onLoad={() => setReady(true)}
          className="absolute inset-0 h-full w-full object-cover transition-opacity duration-700"
          style={{ objectPosition: position, opacity: ready ? 1 : 0, filter: 'brightness(.55) saturate(.85)' }}
        />
        <div className="absolute inset-0" style={{ background: 'linear-gradient(180deg, rgba(11,13,16,.42) 0%, rgba(11,13,16,.78) 50%, rgba(11,13,16,.96) 100%)' }} />
      </div>
      <div className="pointer-events-none fixed bottom-2 right-3 z-10 font-mono text-[9.5px] uppercase tracking-[0.14em] text-fg/35 max-sm:hidden" data-backdrop-credit>{b.credit}</div>
    </>
  )
}
