// Mirrors services/common/aqi.py. Keep both in sync; the manifest carries the ramp too.
//
// Two palettes. `cpcb` is the statutory Indian AQI ramp and the default — it is what every
// Indian reader already recognises, and the plume PNGs are baked in it server-side. But green→
// yellow→orange→red is close to the worst case for deuteranopia and protanopia (~8% of men),
// where Satisfactory and Very Poor can read as the same mud. `cvd` keeps the same thresholds
// and labels and swaps in a blue→yellow ramp that stays monotonic in lightness, so the bands
// are distinguishable by hue *and* by brightness, and in greyscale.
//
// The arrays below are mutated in place by `setPalette` so that every module which already
// imported them picks the change up on its next render; `paletteRev` in the store is what
// triggers that render. Do not replace them with new objects.

export type PaletteId = 'cpcb' | 'cvd'

const RAMPS: Record<PaletteId, string[]> = {
  //        Satisfactory  Moderate   Poor       Very Poor  Severe
  cpcb: ['#9ED6A0', '#F7E07A', '#F0A35E', '#D75B4A', '#7C2B3F'],
  cvd: ['#CFE8F3', '#8FC7E8', '#F3D55B', '#E8853B', '#8C2D04'],
}

const TIER_COLOURS: Record<PaletteId, string[]> = {
  //       T0         T1         T2         T3         T4
  cpcb: ['#3FA34D', '#E0B13A', '#D9743B', '#B8383B', '#6B1F3A'],
  cvd: ['#2C7BB6', '#A6D3E8', '#F3D55B', '#E8853B', '#7F2704'],
}

const BURN_COLOURS: Record<PaletteId, string[]> = {
  cpcb: ['#7fb069', '#f7e07a', '#f0a35e', '#b8383b'],
  cvd: ['#8FC7E8', '#F3D55B', '#E8853B', '#8C2D04'],
}

export const PM25_RAMP: { from: number; colour: string; label: string }[] = [
  { from: 30, colour: RAMPS.cpcb[0], label: 'Satisfactory' },
  { from: 60, colour: RAMPS.cpcb[1], label: 'Moderate' },
  { from: 90, colour: RAMPS.cpcb[2], label: 'Poor' },
  { from: 120, colour: RAMPS.cpcb[3], label: 'Very Poor' },
  { from: 250, colour: RAMPS.cpcb[4], label: 'Severe' },
]

export const TIERS: Record<'T0' | 'T1' | 'T2' | 'T3' | 'T4', { label: string; colour: string }> = {
  T0: { label: 'Normal', colour: TIER_COLOURS.cpcb[0] },
  T1: { label: 'Caution', colour: TIER_COLOURS.cpcb[1] },
  T2: { label: 'Indoors', colour: TIER_COLOURS.cpcb[2] },
  T3: { label: 'Restrict', colour: TIER_COLOURS.cpcb[3] },
  T4: { label: 'Closure advisory', colour: TIER_COLOURS.cpcb[4] },
}
export type TierId = keyof typeof TIERS

let activePalette: PaletteId = 'cpcb'
export function palette(): PaletteId {
  return activePalette
}

/** Swap every colour in place. Thresholds and labels never change. */
export function setPalette(id: PaletteId): void {
  activePalette = id
  RAMPS[id].forEach((c, i) => { PM25_RAMP[i].colour = c })
  const tiers = ['T0', 'T1', 'T2', 'T3', 'T4'] as TierId[]
  tiers.forEach((tid, i) => { TIERS[tid].colour = TIER_COLOURS[id][i] })
  BURN_CATS.forEach((b, i) => { b.colour = BURN_COLOURS[id][i] })
}

/** k spans many orders of magnitude (raw units are MW per m^3); show it compactly, never rounded favourably. */
export function fmtK(k: number | null): string {
  return k === null ? 'not fitted' : k.toExponential(2)
}
export function fmtMetric(v: number | null | undefined, digits = 2): string {
  return v === null || v === undefined ? '—' : v.toFixed(digits)
}

export const BURN_CATS: { label: string; max: number; colour: string }[] = [
  { label: 'Low', max: 25, colour: BURN_COLOURS.cpcb[0] },
  { label: 'Moderate', max: 50, colour: BURN_COLOURS.cpcb[1] },
  { label: 'High', max: 75, colour: BURN_COLOURS.cpcb[2] },
  { label: 'Extreme', max: 100, colour: BURN_COLOURS.cpcb[3] },
]

const BP = [[0, 30, 0, 50], [30, 60, 51, 100], [60, 90, 101, 200], [90, 120, 201, 300], [120, 250, 301, 400], [250, 380, 401, 500]]
/** CPCB PM2.5 sub-index, mirrors services/common/aqi.py */
export function pm25Subindex(c: number): number {
  const v = Math.max(0, c)
  for (const [cl, ch, il, ih] of BP) if (v <= ch) return Math.round(((ih - il) / (ch - cl)) * (v - cl) + il)
  return 500
}
export function tierForAqi(a: number): TierId {
  return a <= 200 ? 'T0' : a <= 300 ? 'T1' : a <= 400 ? 'T2' : a <= 450 ? 'T3' : 'T4'
}
