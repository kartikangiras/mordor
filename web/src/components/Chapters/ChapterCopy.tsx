import { chapters } from '@/config/chapters'

export default function ChapterCopy({ index, n, total, kicker = 'chapter' }: { index: number; n: number; total: number; kicker?: string }) {
  const ch = chapters[index]
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-fire">{kicker} {n} / {total}</div>
      <h2 className="mt-1 text-[19px] font-semibold leading-tight tracking-tight text-fg">{ch.title}</h2>
      <p className="mt-1 text-[13px] leading-relaxed text-mute">{ch.body}</p>
    </div>
  )
}
