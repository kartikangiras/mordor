/** Window-level shortcuts (slider arrows, space, Shift+arrows for chapters, Escape) must leave a key
 *  alone when the focused element already means something by it: arrows step a focused range input
 *  and move a caret, space clicks a focused button or link, typing goes into fields. A focused link
 *  must not swallow Escape or the arrows, or shortcuts die after every header click. */
export function typingTarget(e: KeyboardEvent): boolean {
  const t = e.target as HTMLElement | null
  if (!t || !t.tagName) return false
  const tag = t.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || t.isContentEditable) return true
  return e.key === ' ' && (tag === 'BUTTON' || tag === 'A')
}
