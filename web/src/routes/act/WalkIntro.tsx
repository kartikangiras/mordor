// /act/walk — the two chapters that open the walkthrough (what the school does, what happens
// after the forecast; PIVOT_PLAN.md D3), then the door into step 1. Demo builds only.
import { useEffect } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import ChapterNav from '@/components/Chapters/ChapterNav'
import TimeSlider from '@/components/Map/TimeSlider'
import { STORY_COUNT } from '@/config/chapters'
import { demoMode } from '@/lib/auth'
import { EXP_STEPS, readProgress, stepOpen } from '@/lib/experience'
import { useStore } from '@/lib/store'

export default function WalkIntro() {
  const navigate = useNavigate()
  const { setChapter, setMapMode, resetView } = useStore()
  useEffect(() => { setMapMode('interactive'); resetView(); setChapter(STORY_COUNT); return () => { resetView() } }, [setChapter, setMapMode, resetView])
  if (!demoMode) return <Navigate to="/act" replace />
  const done = readProgress()
  const firstOpen = EXP_STEPS.findIndex((_, i) => !done[i] && stepOpen(i, done))
  const resume = firstOpen > 0
  return (
    <>
      <ChapterNav mode="intro" lastLabel={resume ? `Continue at step ${firstOpen + 1}` : 'Begin the walkthrough'} onLast={() => navigate(`/act/walk/${Math.max(1, firstOpen + 1)}`)} />
      <TimeSlider />
    </>
  )
}
