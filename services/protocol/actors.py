"""Actor types (DESIGN.md §6.6). A protocol is an actor type, a policy anchor, a rule table that
turns hourly tiers into actions, a message template, and a log. Schools were first; RWAs and
district agriculture officers follow the same shape. Two card kinds:

  exposure  - the actor is downwind: windows of concern, tier, actions (school, rwa)
  source    - the actor is at the source: cells likely to burn, dispatch actions (agri_officer)
"""
from __future__ import annotations

from typing import TypedDict


class ActorType(TypedDict):
    id: str
    kind: str                 # exposure | source
    label: str
    labelHi: str
    personTitle: str          # the human who holds the card
    anchor: str               # the official policy the card helps comply with
    windows: list[list[str]]  # IST windows of concern [[from, to], ...]
    actions: list[dict]       # {id, label, hi, weight}: weight = share of the hours at risk the action addresses (protocol/assess.py)
    defaultActions: dict      # tier -> [action ids]
    protocol: dict            # tier -> {field: text}
    peopleField: str          # the onboarding field that counts people (impact unit)
    impactUnit: str
    audience: str             # who the parent/resident message goes to


SCHOOL: ActorType = {
    "id": "school", "kind": "exposure", "label": "School", "labelHi": "स्कूल", "personTitle": "Principal",
    "anchor": "CAQM GRAP stages", "windows": [["08:00", "14:00"], ["15:00", "16:00"]],
    "actions": [
        {"id": "pt_indoors", "label": "Outdoor PT and games moved indoors", "hi": "खेल-कूद अंदर", "weight": 0.5},
        {"id": "windows_shut", "label": "Windows shut", "hi": "खिड़कियाँ बंद", "weight": 0.2},
        {"id": "masks", "label": "Masks offered / distributed", "hi": "मास्क", "weight": 0.2},
        {"id": "assembly_indoor", "label": "Assembly indoors or cancelled", "hi": "सभा अंदर", "weight": 0.1},
    ],
    "defaultActions": {"T0": [], "T1": ["windows_shut", "assembly_indoor"],
                       "T2": ["pt_indoors", "windows_shut", "masks", "assembly_indoor"],
                       "T3": ["pt_indoors", "windows_shut", "masks", "assembly_indoor"],
                       "T4": ["pt_indoors", "windows_shut", "masks", "assembly_indoor"]},
    "protocol": {
        "T0": {"outdoor": "Normal outdoor activity", "windows": "Normal", "masks": "Not needed", "assembly": "Outdoor OK", "grapAnchor": ""},
        "T1": {"outdoor": "Shorten PT to 20 minutes, no running drills", "windows": "Shut 11:00-16:00", "masks": "Offer to asthmatic students", "assembly": "Indoor", "grapAnchor": "Stage I (Poor)"},
        "T2": {"outdoor": "All outdoor activity cancelled", "windows": "Shut all day; purifier on if present", "masks": "Recommended for the bus queue", "assembly": "Indoor, shortened", "grapAnchor": "Stage II (Very Poor)"},
        "T3": {"outdoor": "Cancelled", "windows": "Shut all day", "masks": "Distribute at the gate", "assembly": "Cancelled", "grapAnchor": "Stage III (Severe)"},
        "T4": {"outdoor": "Cancelled", "windows": "Shut all day", "masks": "Distribute at the gate", "assembly": "Cancelled", "grapAnchor": "Stage IV (Severe+)",
               "advisory": "Stage IV conditions are forecast. Check for a Directorate of Education order and prepare for online classes."},
    },
    "peopleField": "students", "impactUnit": "protected student-hours", "audience": "parents",
}

RWA: ActorType = {
    "id": "rwa", "kind": "exposure", "label": "Residents' welfare association", "labelHi": "आरडब्ल्यूए", "personTitle": "RWA secretary",
    "anchor": "CAQM GRAP citizen charter", "windows": [["06:00", "09:00"], ["17:00", "21:00"]],
    "actions": [
        {"id": "outdoor_off", "label": "Morning walks and evening play paused; park gates shut", "hi": "सुबह की सैर और शाम का खेल बंद", "weight": 0.4},
        {"id": "gensets_off", "label": "Diesel gensets off (GRAP II/III)", "hi": "डीज़ल जनरेटर बंद", "weight": 0.2},
        {"id": "elderly_notice", "label": "Elderly and asthmatic residents told to stay in", "hi": "बुज़ुर्गों को सूचना", "weight": 0.3},
        {"id": "masks", "label": "Masks for guards, drivers and domestic workers", "hi": "कर्मचारियों को मास्क", "weight": 0.2},
    ],
    "defaultActions": {"T0": [], "T1": ["elderly_notice"], "T2": ["outdoor_off", "gensets_off", "elderly_notice", "masks"],
                       "T3": ["outdoor_off", "gensets_off", "elderly_notice", "masks"], "T4": ["outdoor_off", "gensets_off", "elderly_notice", "masks"]},
    "protocol": {
        "T0": {"outdoor": "Parks and walks as usual", "gensets": "Normal", "notice": "None", "staff": "Normal", "grapAnchor": ""},
        "T1": {"outdoor": "Shorten the evening play hour", "gensets": "Avoid running gensets in the evening", "notice": "Elderly and asthmatic residents advised to stay in during the evening", "staff": "Masks available at the gate", "grapAnchor": "Stage I (Poor)"},
        "T2": {"outdoor": "Morning walks and evening play paused", "gensets": "Diesel gensets off except emergencies", "notice": "Elderly and asthmatic residents told to stay in", "staff": "Masks for guards, drivers, domestic workers", "grapAnchor": "Stage II (Very Poor)"},
        "T3": {"outdoor": "Park gates shut", "gensets": "Off", "notice": "Door-to-door notice for elderly residents", "staff": "Masks issued; outdoor duties shortened", "grapAnchor": "Stage III (Severe)"},
        "T4": {"outdoor": "Park gates shut", "gensets": "Off", "notice": "Door-to-door notice", "staff": "Outdoor duties minimised", "grapAnchor": "Stage IV (Severe+)",
               "advisory": "Stage IV conditions are forecast. Watch for CAQM orders on work from home and vehicle restrictions."},
    },
    "peopleField": "residents", "impactUnit": "protected resident-hours", "audience": "residents",
}

AGRI_OFFICER: ActorType = {
    "id": "agri_officer", "kind": "source", "label": "District agriculture office", "labelHi": "ज़िला कृषि कार्यालय",
    "personTitle": "District agriculture officer", "anchor": "Crop residue management scheme; red-entry and nodal-officer patrols",
    "windows": [["06:00", "18:00"]],
    "actions": [
        {"id": "dispatch_balers", "label": "Balers / Happy Seeders dispatched to the top cells", "hi": "बेलर और हैप्पी सीडर भेजे", "weight": 0.5},
        {"id": "nodal_visits", "label": "Nodal officers sent to the top cells", "hi": "नोडल अधिकारी भेजे", "weight": 0.3},
        {"id": "awareness_drive", "label": "Village announcements and CHC helpline reminder", "hi": "गाँव में घोषणा", "weight": 0.1},
        {"id": "fire_tender_standby", "label": "Fire tender on standby near the highest-risk cell", "hi": "दमकल तैयार", "weight": 0.1},
    ],
    "defaultActions": {"Low": [], "Moderate": ["awareness_drive"], "High": ["dispatch_balers", "nodal_visits", "awareness_drive"],
                       "Extreme": ["dispatch_balers", "nodal_visits", "awareness_drive", "fire_tender_standby"]},
    "protocol": {},
    "peopleField": "machines", "impactUnit": "cells actioned", "audience": "custom hiring centres",
}

# The public "what to do today" text per tier (PIVOT_PLAN.md §5, D6 b): general CPCB / GRAP
# guidance for anyone, keyed by the same tier ids the cards use. Served by GET /api/guidelines;
# never used by the card builders (it is not in ACTOR_TYPES), so it changes no card and no record.
PUBLIC_GUIDELINES: dict[str, dict] = {
    "T0": {"title": "Normal day", "outdoor": "Outdoor activity as usual", "windows": "Open as you like", "masks": "Not needed", "vulnerable": "No special care", "grapAnchor": ""},
    "T1": {"title": "Take it easy outdoors", "outdoor": "Shorten runs and sport; skip the smoky hours", "windows": "Shut during the smoky hours", "masks": "Carry one if you have asthma",
           "vulnerable": "Lighter outdoor time for children, the elderly and asthmatics", "grapAnchor": "GRAP Stage I (Poor)"},
    "T2": {"title": "Stay in when you can", "outdoor": "No outdoor exercise; keep errands short", "windows": "Shut all day; purifier on if you have one", "masks": "N95 outdoors, especially in traffic",
           "vulnerable": "Children and the elderly indoors", "grapAnchor": "GRAP Stage II (Very Poor)"},
    "T3": {"title": "Indoors, except what you must do", "outdoor": "Cancel outdoor plans", "windows": "Shut all day", "masks": "N95 whenever outside",
           "vulnerable": "Indoors; look in on neighbours who live alone", "grapAnchor": "GRAP Stage III (Severe)",
           "advisory": "Check CAQM orders: construction and some vehicle restrictions apply at Stage III."},
    "T4": {"title": "Stay indoors", "outdoor": "Cancelled", "windows": "Shut all day", "masks": "N95 whenever outside", "vulnerable": "Indoors all day", "grapAnchor": "GRAP Stage IV (Severe+)",
           "advisory": "Stage IV: watch for orders on schools, work from home and vehicle restrictions."},
}

HOSPITAL: ActorType = {
    "id": "hospital", "kind": "exposure", "label": "Hospital", "labelHi": "अस्पताल", "personTitle": "Medical superintendent",
    "anchor": "State health advisory on air pollution; NPCCHH pollution-related illness guidance", "windows": [["06:00", "14:00"], ["14:00", "22:00"]],
    "actions": [
        {"id": "alert_wards", "label": "Respiratory and emergency wards put on alert", "hi": "श्वसन और आपातकालीन वार्ड सतर्क", "weight": 0.3},
        {"id": "stock_meds", "label": "Inhalers, nebulisers and oxygen stock checked", "hi": "इनहेलर, नेबुलाइज़र और ऑक्सीजन का स्टॉक जाँचा", "weight": 0.3},
        {"id": "beds_ready", "label": "Beds kept ready for asthma and COPD cases", "hi": "दमा और सीओपीडी के लिए बेड तैयार", "weight": 0.3},
        {"id": "helpline", "label": "Helpline staffed for breathless callers", "hi": "सांस की तकलीफ़ के लिए हेल्पलाइन", "weight": 0.1},
    ],
    "defaultActions": {"T0": [], "T1": ["alert_wards"], "T2": ["alert_wards", "stock_meds"],
                       "T3": ["alert_wards", "stock_meds", "beds_ready"], "T4": ["alert_wards", "stock_meds", "beds_ready", "helpline"]},
    "protocol": {
        "T0": {"wards": "Routine", "stock": "Routine", "beds": "Routine", "grapAnchor": ""},
        "T1": {"wards": "Respiratory OPD told to expect more asthma visits", "stock": "Check inhaler and nebuliser stock", "beds": "Routine", "grapAnchor": "Stage I (Poor)"},
        "T2": {"wards": "Respiratory and emergency wards on alert", "stock": "Inhalers, nebulisers and oxygen topped up", "beds": "Two beds held for asthma and COPD", "grapAnchor": "Stage II (Very Poor)"},
        "T3": {"wards": "Wards on alert; extra staff in the evening", "stock": "Oxygen and nebuliser stock verified", "beds": "Beds held; discharge planning reviewed", "grapAnchor": "Stage III (Severe)"},
        "T4": {"wards": "Wards on alert round the clock", "stock": "Oxygen, nebulisers and inhalers verified twice daily", "beds": "Beds held; helpline staffed", "grapAnchor": "Stage IV (Severe+)",
               "advisory": "Stage IV conditions are forecast. Expect a rise in breathlessness and chest cases; keep the helpline staffed."},
    },
    "peopleField": "beds", "impactUnit": "ready bed-hours", "audience": "the emergency and respiratory wards",
}

ACTOR_TYPES: dict[str, ActorType] = {"school": SCHOOL, "rwa": RWA, "agri_officer": AGRI_OFFICER, "hospital": HOSPITAL}

ROLES = {
    "operator": "Holds a card and acts: principal, RWA secretary, district agriculture officer",
    "verifier": "Confirms outcomes against observations and approves registrations: air-quality officer",
    "analyst": "Runs the model, publishes calibration and the nightly outcome checks: the forecast team",
    "auditor": "Reads the decision records and the impact: Directorate of Education, CAQM",
}

# Fictional demo personas (as Hestia's Raj / Maria / Jennifer / Carlos). Not real people.
PERSONAS = [
    {"name": "Priya", "role": "analyst", "title": "Forecast analyst", "org": "Mordor", "entityId": None, "email": "priya.demo@example.com"},
    {"name": "Anita", "role": "operator", "title": "Principal", "org": "Kendriya Vidyalaya, Rohini", "entityId": "osm-way-388242027", "email": "anita.demo@example.com"},
    {"name": "Rekha", "role": "operator", "title": "RWA secretary", "org": "Rohini Sector 3 RWA (demo)", "entityId": "rwa-demo-rohini", "email": "rekha.demo@example.com"},
    {"name": "Gurpreet", "role": "operator", "title": "District agriculture officer", "org": "Sangrur (demo)", "entityId": "dao-demo-sangrur", "email": "gurpreet.demo@example.com"},
    {"name": "Dr. Mehta", "role": "verifier", "title": "Air-quality officer", "org": "DPCC (demo)", "entityId": None, "email": "mehta.demo@example.com"},
    {"name": "Ms. Rao", "role": "auditor", "title": "Deputy director", "org": "Directorate of Education (demo)", "entityId": None, "email": "rao.demo@example.com"},
    {"name": "Dr. Kapoor", "role": "operator", "title": "Medical superintendent", "org": "District Hospital, Rohini (demo)", "entityId": "hosp-demo-rohini", "email": "kapoor.demo@example.com"},
]


def persona_for_email(email: str | None) -> str | None:
    """The demo persona behind a Cognito login, by its fixed demo address; None for anyone real
    (AWS_INTEGRATION.md row 13). Records then carry the person who acted, never the entity's
    persona on a real login (PIVOT_PLAN.md AUTH-9)."""
    if not email:
        return None
    return next((p["name"] for p in PERSONAS if p.get("email") == email.lower()), None)


def actor_type(type_id: str | None) -> ActorType:
    return ACTOR_TYPES.get(type_id or "school", SCHOOL)
