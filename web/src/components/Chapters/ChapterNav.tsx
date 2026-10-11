// Declarative chapters (DESIGN.md §9.3). The chapter is the URL (/story/:n): prev/next are
// navigations and leaving goes to the map, so back and refresh both land where the reader was.
// Chapters are read-only: the layers they switch on show as chips, not toggles.
// Chapter 7 hands the map off to the decision: the demo school's public card.
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { demoMode } from '@/lib/auth'
import { STORY_COUNT, chapters } from '@/config/chapters'
import { LAYER_WORDS } from '@/config/layers'
import { useStore } from '@/lib/store'
import { getPublicCard, getRecordsIndex, getSchoolCard } from '@/lib/api'
import type { PublicCard } from '@/lib/protocol'
import { typingTarget } from '@/lib/keys'
import ProtocolCard from '@/components/Protocol/ProtocolCard'
import ChapterCopy from './ChapterCopy'
import RecordsPanel from './RecordsPanel'
import { CloseIcon, LayerIcon } from '@/components/Map/icons'
import Legend from '@/components/Map/Legend'
import { TIERS } from '@/lib/aqi'

/** The story (chapters 1–6 at /story/:n) or the walkthrough's intro (chapters 7–8 at /act/walk). */
export default function ChapterNav({ mode = 'story', lastLabel, onLast }: { mode?: 'story' | 'intro'; lastLabel?: string; onLast?: () => void } = {}) {
  const first = mode === 'story' ? 0 : STORY_COUNT
  const end = mode === 'story' ? STORY_COUNT - 1 : chapters.length - 1
  const chapter = useStore((s) => s.chapter)
  const setChapter = useStore((s) => s.setChapter)
  const manifest = useStore((s) => s.manifest)
  const [card, setCard] = useState<PublicCard | null>(null)
  const [recordsEntity, setRecordsEntity] = useState<string | null>(null)
  const [keyOpen, setKeyOpen] = useState(true)   // the colour key is part of reading a chapter
  const schools = useStore((s) => s.schools)
  const zones = useStore((s) => s.zones)
  const flyTo = useStore((s) => s.flyTo)
  const stat = (id: string): string | null => {
    if (!manifest) return null
    switch (id) {
      case 'burning': return `${manifest.fires.count.toLocaleString('en-IN')} detections in the last 24 h`
      case 'arrival': return `${manifest.hours.length - 1} hours ahead · 5 km cells`
      case 'zones': return zones ? `${zones.zones.length} cities ranked` : null
      case 'underneath': return manifest.schools?.named ? `${manifest.schools.named.toLocaleString('en-IN')} schools on the map` : null
      case 'lifecycle': return manifest.calibration.stations ? `${manifest.calibration.stations} stations in the hindcast` : null
      default: return null
    }
  }
  const navigate = useNavigate()
  const go = useCallback((i: number) => {
    const j = Math.min(end, Math.max(first, i))
    if (mode === 'story') navigate(`/story/${j + 1}`); else setChapter(j)
  }, [navigate, setChapter, mode, first, end])
  const exit = useCallback(() => navigate(mode === 'story' ? '/map' : '/act'), [navigate, mode])   // the target's mount resets the view

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (chapter === null || typingTarget(e) || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'ArrowRight' && e.shiftKey) go(chapter + 1)
      if (e.key === 'ArrowLeft' && e.shiftKey) go(chapter - 1)
      if (e.key === 'Escape') exit()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [chapter, go, exit])

  const show = chapter !== null && chapters[chapter]?.showProtocolCard
  const showRecords = chapter !== null && chapters[chapter]?.showRecords
  // chapter 7: the worst school for tomorrow, wherever it is; the camera follows it
  useEffect(() => {
    if (!show || !manifest) { setCard(null); return }
    const rank = (t: string | null) => (t && t in TIERS ? Object.keys(TIERS).indexOf(t) : -1)
    const worst = [...(schools?.features ?? [])].sort((a, b) => rank(b.properties.dayTier) - rank(a.properties.dayTier) || (b.properties.peakAqi ?? 0) - (a.properties.peakAqi ?? 0))[0]
    const demo = manifest.demoSchools?.find((d) => d.startsWith('osm-')) ?? manifest.demoSchools?.[0]
    let alive = true
    ;(async () => {
      const c = (worst ? await getSchoolCard(worst.properties.id) : null) ?? (demo ? await getPublicCard(manifest, demo) : null)
      if (!alive) return
      setCard(c)
      const f = worst && c?.schoolId === worst.properties.id ? worst : schools?.features.find((x) => x.properties.id === c?.schoolId)
      if (f) flyTo([f.geometry.coordinates[0], f.geometry.coordinates[1]], 13)
    })()
    return () => { alive = false }
  }, [show, manifest, schools, flyTo])
  // chapter 8: the entity with the most decisions today
  useEffect(() => {
    if (!showRecords) return
    const fallback = manifest?.entities?.ids.find((id) => id.startsWith('rwa-')) ?? manifest?.entities?.ids[0] ?? null
    getRecordsIndex().then((idx) => {
      const counts = new Map<string, number>()
      for (const r of idx.records) if (r.by.persona || !(r.kind === 'forecast' || r.kind === 'advise')) counts.set(r.entity, (counts.get(r.entity) ?? 0) + 1)
      const best = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0]
      setRecordsEntity(best ?? fallback)
    }).catch(() => setRecordsEntity(fallback))
  }, [showRecords, manifest])
  useEffect(() => { setKeyOpen(true) }, [chapter])

  if (chapter === null || chapter < first || chapter > end) return null
  const ch = chapters[chapter]
  const last = chapter === end
  const finish = () => (onLast ? onLast() : exit())
  return (
    <>
      <div className="glass absolute left-4 top-4 max-h-[calc(100%-7rem)] w-[min(340px,calc(100%-2rem))] overflow-y-auto p-5 max-sm:left-2 max-sm:top-2 max-sm:w-[calc(100%-1rem)]">
        <div className="mb-3 flex gap-1" aria-hidden>{chapters.slice(first, end + 1).map((c, i) => <span key={c.id} className={`h-1 flex-1 rounded-full ${first + i <= chapter ? 'bg-fire' : 'bg-white/10'}`} />)}</div>
        <ChapterCopy index={chapter} n={chapter - first + 1} total={end - first + 1} kicker={mode === 'story' ? 'chapter' : 'before you begin'} />
        {stat(ch.id) && <div className="mt-2 font-mono text-[11px] text-fire">{stat(ch.id)}</div>}
        {last && mode === 'story' && (
          <div className="pulse-ring mt-3 rounded-xl border border-fire/50 bg-fire/10 p-3" data-story-end>
            <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-fire">the story ends here</div>
            <div className="mt-1 text-[15px] font-semibold leading-tight text-fg">Be a responsible citizen. Do your part.</div>
            <div className="mt-1 text-[12px] leading-relaxed text-mute">Principals, residents' associations, district offices and hospitals each hold a card and a decision. Walk the eight steps and leave a record — or go and see the changes around you yourself.</div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <Link to={demoMode ? '/act/walk' : '/act'} className="flex h-11 items-center justify-center gap-2 rounded-lg bg-fire text-[13px] font-semibold text-ink hover:bg-[#ffc46a]">Action plan <span className="h-2 w-2 animate-pulse rounded-full bg-[#d7263d]" /></Link>
              <Link to="/map" className="hairline flex h-11 items-center justify-center rounded-lg text-[13px] font-medium text-fg hover:bg-white/5">Explore the map</Link>
            </div>
          </div>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-1.5" aria-label="Layers in this chapter">
          {ch.layers.map((id) => <span key={id} className="hairline inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 font-mono text-[10px] uppercase tracking-wider text-fg/80"><LayerIcon id={id} className="h-3 w-3 text-fire" />{LAYER_WORDS[id]}</span>)}
          <button type="button" onClick={() => setKeyOpen((o) => !o)} aria-expanded={keyOpen} className="h-7 rounded-full px-2 font-mono text-[10px] uppercase tracking-wider text-mute hover:text-fg">{keyOpen ? 'key ▴' : 'key ▾'}</button>
        </div>
        {keyOpen && <div className="mt-2 max-h-56 overflow-y-auto rounded-lg bg-black/25 p-2"><Legend inline /></div>}
        <div className="mt-4 flex items-center gap-2">
          <button type="button" onClick={() => go(chapter - 1)} disabled={chapter === first} className="hairline h-10 rounded-lg px-3 text-[12px] font-medium text-fg hover:bg-white/5 disabled:opacity-40">← prev</button>
          {!(last && mode === 'story') && <button type="button" onClick={() => (last ? finish() : go(chapter + 1))} className="h-10 flex-1 rounded-lg bg-fire px-3 text-[12px] font-semibold text-ink hover:bg-[#ffc46a]">{last ? (lastLabel ?? 'Open the map') : 'next →'}</button>}
          <button type="button" onClick={exit} className="hairline flex h-10 w-10 items-center justify-center rounded-lg text-mute hover:bg-white/5 hover:text-fg" title="Escape" aria-label={mode === 'story' ? 'Leave the story' : 'Back to the door'}><CloseIcon /></button>
        </div>
        <div className="mt-3 font-mono text-[10px] text-mute max-sm:hidden">shift + arrows · chapters &nbsp; space · play</div>
      </div>
      {show && card && (
        <div className="absolute bottom-24 right-4 top-20 w-[min(400px,calc(100%-2rem))] overflow-y-auto rounded-2xl max-sm:inset-x-2 max-sm:top-52">
          <ProtocolCard readOnly actions={card.defaultActions} card={{ ...card, school: { id: card.schoolId, name: card.name, name_hi: card.name_hi, hours: card.schoolHoursIst as [string, string] | undefined, dismissal: card.dismissalIst as [string, string] | undefined, hasPurifiers: !!card.hasPurifiers } }} />
        </div>
      )}
      {showRecords && recordsEntity && <RecordsPanel entity={recordsEntity} />}
      {show && !card && (
        <div className="glass glass-tight absolute right-4 top-20 p-3 font-mono text-[11px] text-mute">No demo card in this run yet.</div>
      )}
    </>
  )
}
