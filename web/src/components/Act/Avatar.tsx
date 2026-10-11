// A persona's picture: the place they work, not a face (the seven are fictional, and a stock
// face would read as a real person). The photos come from Wikimedia Commons by way of
// tools/fetch_avatars.sh, which also writes the credits; Priya's is the Mordor mark. If the image
// is missing the initial in the persona's colour stands in, as before.
import { useState } from 'react'
import type { Persona } from '@/lib/experience'

export default function Avatar({ p, size = 40 }: { p: Persona; size?: number }) {
  const [failed, setFailed] = useState(false)
  if (failed) {
    return <div className="flex shrink-0 items-center justify-center rounded-lg text-base font-semibold" style={{ width: size, height: size, background: `${p.colour}22`, color: p.colour }} aria-hidden>{p.name.replace('Dr. ', '').replace('Ms. ', '')[0]}</div>
  }
  return (
    <img
      src={p.avatar}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
      data-avatar={p.name}
      className="shrink-0 rounded-lg object-cover"
      style={{ width: size, height: size, boxShadow: `0 0 0 2px ${p.colour}66`, background: `${p.colour}22` }}
    />
  )
}
