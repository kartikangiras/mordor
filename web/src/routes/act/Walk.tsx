// /act/walk/:n — the demo walkthrough: eight steps over the map, each performed by one of the
// seven people. The step is the URL; entering a step makes its persona the one viewer (header
// chip and API headers agree); progress lives in sessionStorage and the walk resumes at the
// first incomplete step. Demo builds only.
import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import TimeSlider from '@/components/Map/TimeSlider'
import FlowNav from '@/components/Experience/FlowNav'
import PersonaCard from '@/components/Act/PersonaCard'
import { useAreaData } from '@/components/Experience/useAreaData'
import StepLandscape from '@/components/Experience/steps/StepLandscape'
import StepCommunity from '@/components/Experience/steps/StepCommunity'
import StepInspection from '@/components/Experience/steps/StepInspection'
import StepPlan from '@/components/Experience/steps/StepPlan'
import StepWork from '@/components/Experience/steps/StepWork'
import StepProof from '@/components/Experience/steps/StepProof'
import StepValue from '@/components/Experience/steps/StepValue'
import StepHealth from '@/components/Experience/steps/StepHealth'
import { AREAS } from '@/config/areas'
import { EXP_STEPS, PERSONAS, readProgress, readWalk, stepOpen, writeProgress, writeWalk, type SchoolPick } from '@/lib/experience'
import { demoMode, useAuth } from '@/lib/auth'
import { useStore } from '@/lib/store'
import { haversineKm } from '@/lib/grid'

export default function Walk() {
  const { n } = useParams()
  const navigate = useNavigate()
  const auth = useAuth()
  const { area, setArea, setExpStep, manifest, entities, fires, setMapMode, resetView } = useStore()
  const [complete, setComplete] = useState<Record<number, boolean>>(readProgress)
  const [school, setSchool] = useState<SchoolPick | null>(() => readWalk().school)
  const onSchool = (s: SchoolPick) => { setSchool(s); writeWalk({ school: s }) }
  const [authErr, setAuthErr] = useState<string | null>(null)
  const d = useAreaData(area, school ? [school.id] : [])
  const firstOpen = Math.min(EXP_STEPS.length - 1, Math.max(0, EXP_STEPS.findIndex((_, i) => !complete[i]) === -1 ? EXP_STEPS.length - 1 : EXP_STEPS.findIndex((_, i) => !complete[i])))
  const wanted = n === undefined ? null : Math.min(EXP_STEPS.length - 1, Math.max(0, (Number(n) || 1) - 1))
  const step = wanted === null || !stepOpen(wanted, complete) ? firstOpen : wanted

  // the map: interactive for the walk, back to the free-map defaults on leave
  useEffect(() => { setMapMode('interactive'); return () => { resetView(); setExpStep(null) } }, [setMapMode, resetView, setExpStep])
  // the URL is the step; a missing or locked step goes to the first open one
  useEffect(() => { if (wanted === null || wanted !== step) navigate(`/act/walk/${step + 1}`, { replace: true }) }, [wanted, step, navigate])
  // the persona of the step is the viewer, and the area follows their place
  useEffect(() => {
    const st = EXP_STEPS[step]
    const p = PERSONAS[st.persona]
    if (useAuth.getState().persona !== p.name) { setAuthErr(null); void auth.signInAs(p).catch((e) => setAuthErr((e as Error).message)) }
    const ent = p.entityId ? entities?.features.find((f) => f.properties.id === p.entityId) : null
    // the school step keeps the area chosen in step 1; the other operators work at their own entity
    if (ent && st.id !== 'community') setArea({ id: `entity-${ent.properties.id}`, name: ent.properties.name, lat: ent.geometry.coordinates[1], lon: ent.geometry.coordinates[0], radiusKm: ent.properties.type === 'agri_officer' ? (ent.properties.radiusKm ?? 45) : 15, kind: ent.properties.type === 'agri_officer' ? 'district' : 'city', region: ent.properties.typeLabel })
    else if (!useStore.getState().area) {
      let start = AREAS[0]
      if (fires) { const counts = AREAS.map((a) => ({ a, n: fires.features.filter((f) => haversineKm(a.lat, a.lon, f.geometry.coordinates[1], f.geometry.coordinates[0]) <= a.radiusKm).length })); start = counts.sort((x, y) => y.n - x.n)[0]?.a ?? start }
      setArea(start)
    }
    setExpStep(step)
  }, [step, entities, fires])  // eslint-disable-line react-hooks/exhaustive-deps

  if (!demoMode) return <Navigate to="/act" replace />
  const st = EXP_STEPS[step]
  const persona = PERSONAS[st.persona]
  const headers = auth.headers()
  // a step's calls must go out as its own persona: the switch is a real sign-in, so wait for it
  const asPersona = auth.persona === persona.name
  const next = () => { const done = { ...complete, [step]: true }; setComplete(done); writeProgress(done); if (step < EXP_STEPS.length - 1) navigate(`/act/walk/${step + 2}`) }
  const startOver = () => { writeProgress({}); setComplete({}); writeWalk({ school: null }); setSchool(null); navigate('/act/walk/1') }
  const leave = () => navigate('/map')
  const common = { area: area ?? AREAS[0], d, headers, onComplete: next, colour: persona.colour, school, onSchool }
  const body = st.id === 'landscape' ? <StepLandscape {...common} onArea={setArea} />
    : st.id === 'community' ? <StepCommunity {...common} />
    : st.id === 'inspection' ? <StepInspection {...common} />
    : st.id === 'plan' ? <StepPlan {...common} />
    : st.id === 'work' ? <StepWork {...common} />
    : st.id === 'proof' ? <StepProof {...common} />
    : st.id === 'value' ? <StepValue {...common} />
    : <StepHealth {...common} onLeave={leave} />
  const doneCount = EXP_STEPS.filter((_, i) => complete[i]).length
  return (
    <>
      <style>{`@keyframes vd-pulse{0%,100%{box-shadow:0 0 0 0 rgba(255,179,71,0)}50%{box-shadow:0 0 0 6px rgba(255,179,71,0.25)}}`}</style>
      <FlowNav step={step} complete={complete} onGo={(i) => navigate(`/act/walk/${i + 1}`)} onLeave={leave} onReset={doneCount ? startOver : undefined} />
      <div className="glass absolute bottom-24 left-4 top-16 w-[min(400px,calc(100%-2rem))] overflow-y-auto p-5 max-sm:inset-x-2 max-sm:top-auto max-sm:bottom-20 max-sm:max-h-[60%] max-sm:w-auto">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-mute">step {st.n} of {EXP_STEPS.length} · {st.title}</div>
        <div className="mt-2"><PersonaCard persona={st.id === 'community' && school ? { ...persona, title: 'Principal', org: school.name } : persona} step={st} /></div>
        {complete[step] && <div className="mb-3 rounded-lg bg-white/[0.04] px-3 py-2 font-mono text-[11px] text-mute">Done in this session. You can do it again, or <button type="button" onClick={() => navigate(`/act/walk/${firstOpen + 1}`)} className="underline hover:text-fg">continue at step {firstOpen + 1}</button>.</div>}
        {asPersona ? <div key={step}>{body}</div> : authErr
          ? <div className="rounded-lg border border-red-900 bg-panel p-3 font-mono text-[11px] text-red-300">Could not sign in as {persona.name}: {authErr}</div>
          : <div className="space-y-2"><div className="font-mono text-[11px] text-mute">signing in as {persona.name}…</div><div className="h-32 animate-pulse rounded-lg bg-white/[0.04]" /></div>}
        {manifest && <div className="mt-3 border-t border-white/8 pt-2 font-mono text-[10px] text-mute">{area?.name} · <Link to="/map" className="underline">Map</Link> · <Link to="/records" className="underline">Decisions</Link></div>}
      </div>
      {(st.id === 'plan' || st.id === 'work' || st.id === 'proof' || st.id === 'health') && <TimeSlider />}
    </>
  )
}
