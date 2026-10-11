// The public "what to do today" text lives in services/protocol/actors.py and arrives through
// GET /api/guidelines (PIVOT_PLAN.md D6 b). The web keeps only the shape.
export type Guideline = { title: string; outdoor: string; windows: string; masks: string; vulnerable: string; grapAnchor: string; advisory?: string }
export type Guidelines = Record<'T0' | 'T1' | 'T2' | 'T3' | 'T4', Guideline>
