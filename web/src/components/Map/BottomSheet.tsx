// Under 640 px the legend, the guidelines and the detail panel share one sheet above the slider
// (PIVOT_PLAN.md P3): tabs, one scroll, collapsible to its tab row. Selecting a school opens
// the Detail tab.
import { useEffect, useState } from 'react'
import { useStore } from '@/lib/store'
import Legend from './Legend'
import DetailPanel from '@/components/Detail/DetailPanel'
import GuidelinesPanel from '@/components/Public/GuidelinesPanel'

type Tab = 'key' | 'todo' | 'detail'

export default function BottomSheet() {
  const selected = useStore((s) => s.selected)
  const chapter = useStore((s) => s.chapter)
  const manifest = useStore((s) => s.manifest)
  const [tab, setTab] = useState<Tab>('key')
  const [open, setOpen] = useState(false)
  useEffect(() => { if (selected) { setTab('detail'); setOpen(true) } else if (tab === 'detail') setTab('key') }, [selected])  // eslint-disable-line react-hooks/exhaustive-deps
  if (!manifest) return null
  const tabs: { id: Tab; label: string }[] = [{ id: 'key', label: chapter !== null ? 'Key' : 'Legend' }]
  if (chapter === null) tabs.push({ id: 'todo', label: 'What to do' })
  if (selected) tabs.push({ id: 'detail', label: 'School' })
  return (
    <div className="glass absolute inset-x-2 bottom-[110px] z-20 flex max-h-[44vh] flex-col">
      <div className="flex items-center gap-1 px-2 py-1.5" role="tablist" aria-label="Panel">
        {tabs.map((t) => <button key={t.id} type="button" role="tab" aria-selected={tab === t.id && open} onClick={() => { setTab(t.id); setOpen(tab !== t.id || !open) }} className={`h-8 rounded-lg px-2.5 text-[12px] font-medium ${tab === t.id && open ? 'bg-white/10 text-fg' : 'text-mute'}`}>{t.label}</button>)}
        <button type="button" onClick={() => setOpen((o) => !o)} aria-label={open ? 'Collapse' : 'Expand'} className="ml-auto h-8 w-8 rounded-md text-mute">{open ? '⌄' : '⌃'}</button>
      </div>
      {open && (
        <div className="min-h-0 overflow-y-auto border-t border-white/8 p-3">
          {tab === 'key' && <Legend inline />}
          {tab === 'todo' && <GuidelinesPanel compact />}
          {tab === 'detail' && <DetailPanel inline />}
        </div>
      )}
    </div>
  )
}
