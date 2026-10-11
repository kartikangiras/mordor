// The one place UTC -> IST formatting lives in the web app (DESIGN.md §5.2).
const IST = 'Asia/Kolkata'

const parts = new Intl.DateTimeFormat('en-GB', {
  timeZone: IST, weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', hour12: true,
})

/** "Tue 9 Oct, 4 PM" — matches services/common/timeutil.ist_label. */
export function istLabel(iso: string): string {
  const p = Object.fromEntries(parts.formatToParts(new Date(iso)).map((x) => [x.type, x.value]))
  const minute = p.minute === '00' ? '' : `:${p.minute}`
  return `${p.weekday} ${p.day} ${p.month}, ${p.hour}${minute} ${p.dayPeriod.toUpperCase()}`
}

export function istClock(iso: string): string {
  const p = Object.fromEntries(parts.formatToParts(new Date(iso)).map((x) => [x.type, x.value]))
  return `${p.hour}${p.minute === '00' ? '' : ':' + p.minute} ${p.dayPeriod.toUpperCase()}`
}

export function hoursBetween(aIso: string, bIso: string): number {
  return Math.round((new Date(bIso).getTime() - new Date(aIso).getTime()) / 3.6e6)
}
