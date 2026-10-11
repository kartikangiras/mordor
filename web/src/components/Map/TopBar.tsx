// The layer bar: one icon button per overlay, top-centre on the free map. Brand and navigation
// live in the shell header, so this is the only thing the bar does.
import { useStore } from '@/lib/store'
import { LAYER_WORDS, type LayerId } from '@/config/layers'
import { LayerIcon } from './icons'

const ORDER: LayerId[] = ['plume', 'fires', 'wind', 'stations', 'schools', 'actors', 'zones', 'burnrisk', 'ndvi']
const TOGGLES = ORDER.map((id) => ({ id, label: LAYER_WORDS[id] }))

export default function TopBar() {
  const layers = useStore((s) => s.layers)
  const toggle = useStore((s) => s.toggleLayer)
  return (
    <div className="glass glass-tight absolute left-1/2 top-4 z-20 flex -translate-x-1/2 gap-0.5 p-1 max-sm:left-2 max-sm:right-2 max-sm:top-2 max-sm:translate-x-0 max-sm:overflow-x-auto" role="toolbar" aria-label="Layers">
      {TOGGLES.map((t) => {
        const on = layers[t.id]
        return (
          <button
            key={t.id}
            type="button"
            data-layer={t.id}
            onClick={() => toggle(t.id)}
            aria-pressed={on}
            title={`${on ? 'Hide' : 'Show'} ${t.label}`}
            className={`flex h-12 w-[58px] shrink-0 flex-col items-center justify-center gap-1 rounded-lg transition ${on ? 'bg-white/10 text-fg' : 'text-mute hover:bg-white/5 hover:text-fg'}`}
          >
            <LayerIcon id={t.id} className={`h-4 w-4 ${on ? 'text-fire' : ''}`} />
            <span className="text-[9.5px] font-medium tracking-wide">{t.label}</span>
          </button>
        )
      })}
    </div>
  )
}
