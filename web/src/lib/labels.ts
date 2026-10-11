// Viewer words for the ids the API speaks (PIVOT_PLAN.md P3): never print an id on a screen.
export const ACTION_LABELS: Record<string, string> = {
  pt_indoors: 'outdoor PT and games moved indoors', windows_shut: 'windows shut', masks: 'masks offered', assembly_indoor: 'assembly indoors or cancelled',
  outdoor_off: 'morning walks and evening play paused', gensets_off: 'diesel gensets off', elderly_notice: 'elderly and asthmatic residents told to stay in',
  dispatch_balers: 'balers and Happy Seeders dispatched', nodal_visits: 'nodal officers sent', awareness_drive: 'village announcements', fire_tender_standby: 'fire tender on standby',
  alert_wards: 'respiratory and emergency wards on alert', stock_meds: 'inhalers, nebulisers and oxygen checked', beds_ready: 'beds kept ready for asthma and COPD', helpline: 'helpline staffed',
}
export const OUTCOME_LABELS: Record<string, string> = { confirmed: 'confirmed', not_confirmed: 'not confirmed', missed: 'missed', moot: 'moot', pending: 'pending', no_station: 'no station within 25 km', no_data: 'no station data yet' }
