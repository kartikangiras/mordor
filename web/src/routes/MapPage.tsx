// /map (free) and /story/:n (chapters) over the shared map. Mounting resets the view to the
// free-map defaults so nothing the last route left behind leaks in; the chapter comes from the
// URL; /map?layers=a,b opens with those layers on (the zones page links that way).
import { useEffect } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import TopBar from '@/components/Map/TopBar'
import Legend from '@/components/Map/Legend'
import TimeSlider from '@/components/Map/TimeSlider'
import DetailPanel from '@/components/Detail/DetailPanel'
import ChapterNav from '@/components/Chapters/ChapterNav'
import { STORY_COUNT } from '@/config/chapters'
import { LAYER_IDS, type LayerId } from '@/config/layers'
import { useStore } from '@/lib/store'
import { useMediaQuery } from '@/lib/useMediaQuery'
import BottomSheet from '@/components/Map/BottomSheet'

export default function MapPage({ story = false }: { story?: boolean }) {
  const error = useStore((s) => s.error)
  const setChapter = useStore((s) => s.setChapter)
  const resetView = useStore((s) => s.resetView)
  const setLayers = useStore((s) => s.setLayers)
  const { n } = useParams()
  const [params] = useSearchParams()
  const mobile = useMediaQuery('(max-width: 639px)')
  const wanted = params.get('layers')
  const chapter = story ? Math.min(STORY_COUNT - 1, Math.max(0, (Number(n) || 1) - 1)) : null
  useEffect(() => {
    resetView()
    if (chapter !== null) { setChapter(chapter); return }
    if (wanted) setLayers(wanted.split(',').filter((id) => id in LAYER_IDS) as LayerId[])
  }, [chapter, wanted, setChapter, resetView, setLayers])
  return (
    <>
      {!story && <TopBar />}
      <ChapterNav />
      {mobile ? <BottomSheet /> : <>{!story && <Legend />}<DetailPanel /></>}
      <TimeSlider />
      {error && (
        <div className="glass glass-tight absolute left-1/2 top-4 z-30 -translate-x-1/2 px-4 py-2 text-[12px] text-fg/80">
          No forecast is published yet. Try again later.
          {import.meta.env.DEV && <span className="font-mono text-[10px] text-mute"> · dev: {error} · run <code>make forecast-local</code></span>}
        </div>
      )}
    </>
  )
}
