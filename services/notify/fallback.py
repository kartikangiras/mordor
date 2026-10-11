"""Jinja template for the parent message (DESIGN.md §6.4 fallback). Same fields as the agent,
same constraints, deterministic. Hindi first, then English, <= 400 characters in total, one
leading marker, one parent action, never 'emergency', never medication, never 'closed'."""
from __future__ import annotations

from datetime import datetime

from jinja2 import Environment

_HI_MONTHS = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
_EN_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

TEMPLATES = {
    "T0": {
        "hi": "🌤 {{ school }}: {{ date_hi }} को हवा सामान्य रहेगी। सभी गतिविधियाँ और {{ pickup_hi }} की छुट्टी हमेशा की तरह।",
        "en": "{{ school }}: air should be normal on {{ date_en }}. Activities and the {{ pickup_en }} pickup as usual.",
    },
    "T1": {
        "hi": "🌫 {{ school }}: {{ date_hi }} को हवा 'खराब' (AQI {{ aqi }}) रहेगी। PT सिर्फ़ 20 मिनट, दौड़ नहीं; छुट्टी {{ pickup_hi }}। कृपया पानी की बोतल भेजें।",
        "en": "{{ school }}: 'Poor' air (AQI {{ aqi }}) on {{ date_en }}. PT cut to 20 min, no running; pickup {{ pickup_en }}. Please send a water bottle.",
    },
    "T2": {
        "hi": "🌫 {{ school }}: {{ date_hi }} को {{ from_hi }} से हवा 'बहुत खराब' (AQI {{ aqi }}) रहेगी। बाहरी खेल रद्द, खिड़कियाँ बंद। कृपया {{ pickup_hi }} की छुट्टी के लिए मास्क भेजें।",
        "en": "{{ school }}: 'Very Poor' air (AQI {{ aqi }}) from {{ from_en }} on {{ date_en }}. Outdoor games off, windows shut. Please send a mask for the {{ pickup_en }} pickup.",
    },
    "T3": {
        "hi": "🌫 {{ school }}: {{ date_hi }} को हवा 'गंभीर' (AQI {{ aqi }}) रहेगी। सभी बाहरी गतिविधियाँ रद्द; गेट पर मास्क मिलेंगे। कृपया {{ pickup_hi }} की छुट्टी के बाद बच्चे को सीधे घर ले जाएँ।",
        "en": "{{ school }}: 'Severe' air (AQI {{ aqi }}) on {{ date_en }}. All outdoor activity off; masks at the gate. Please take your child straight home after the {{ pickup_en }} pickup.",
    },
    "T4": {
        "hi": "🌫 {{ school }}: {{ date_hi }} को हवा 'गंभीर+' (AQI {{ aqi }}) रहेगी। कृपया {{ pickup_hi }} तक शिक्षा निदेशालय के आदेश पर स्कूल के संदेश देखें और ऑनलाइन कक्षा के लिए तैयार रहें।",
        "en": "{{ school }}: 'Severe+' air (AQI {{ aqi }}) on {{ date_en }}. Please watch for the school's message on the Directorate of Education order by {{ pickup_en }} and be ready for online class.",
    },
}

TEMPLATES_RWA = {
    "T0": {"hi": "🌤 {{ school }}: {{ date_hi }} को हवा सामान्य रहेगी। सैर और पार्क हमेशा की तरह, {{ pickup_hi }} तक।",
           "en": "{{ school }}: air should be normal on {{ date_en }}. Walks and the park as usual until {{ pickup_en }}."},
    "T1": {"hi": "🌫 {{ school }}: {{ date_hi }} को हवा 'खराब' (AQI {{ aqi }}) रहेगी। शाम का खेल {{ from_hi }} तक छोटा। कृपया बुज़ुर्गों को शाम को घर में रखें।",
           "en": "{{ school }}: 'Poor' air (AQI {{ aqi }}) on {{ date_en }}. Evening play shortened to {{ from_en }}. Please keep elderly residents in during the evening."},
    "T2": {"hi": "🌫 {{ school }}: {{ date_hi }} को {{ from_hi }} से हवा 'बहुत खराब' (AQI {{ aqi }}) रहेगी। सुबह की सैर और शाम का खेल बंद, जनरेटर बंद। कृपया {{ pickup_hi }} के बाद बच्चों को अंदर रखें।",
           "en": "{{ school }}: 'Very Poor' air (AQI {{ aqi }}) from {{ from_en }} on {{ date_en }}. Walks and evening play paused, gensets off. Please keep children indoors after {{ pickup_en }}."},
    "T3": {"hi": "🌫 {{ school }}: {{ date_hi }} को हवा 'गंभीर' (AQI {{ aqi }}) रहेगी। पार्क के गेट बंद, जनरेटर बंद। कृपया {{ pickup_hi }} के बाद बाहर न निकलें।",
           "en": "{{ school }}: 'Severe' air (AQI {{ aqi }}) on {{ date_en }}. Park gates shut, gensets off. Please stay in after {{ pickup_en }}."},
    "T4": {"hi": "🌫 {{ school }}: {{ date_hi }} को हवा 'गंभीर+' (AQI {{ aqi }}) रहेगी। पार्क बंद। कृपया {{ pickup_hi }} तक CAQM के घर से काम के आदेश की सूचना देखें।",
           "en": "{{ school }}: 'Severe+' air (AQI {{ aqi }}) on {{ date_en }}. Park shut. Please watch for the CAQM work-from-home notice by {{ pickup_en }}."},
}

TEMPLATES_SOURCE = {
    "hi": "🔥 {{ school }}: 48 घंटे में {{ n_cells }} क्षेत्रों में पराली जलने का ख़तरा {{ worst }} ({{ top }})। {{ burning }} जगह अभी जल रही हैं। कृपया {{ from_hi }} तक बेलर की उपलब्धता CHC को बताएँ।",
    "en": "{{ school }}: {{ n_cells }} cells at {{ worst }} burning risk in 48 h ({{ top }}); {{ burning }} burning now. Please confirm baler availability to the CHC by {{ from_en }}.",
}

_env = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True)


TEMPLATES_HOSPITAL = {
    "T0": {"hi": "🌤 {{ school }}: {{ date_hi }} को हवा सामान्य रहेगी। श्वसन वार्ड में सामान्य व्यवस्था; {{ pickup_hi }} तक नियमित ओपीडी।",
           "en": "{{ school }}: air should be normal on {{ date_en }}. Routine load on the respiratory ward; regular OPD until {{ pickup_en }}."},
    "T1": {"hi": "🌫 {{ school }}: {{ date_hi }} को हवा 'खराब' (AQI {{ aqi }}) रहेगी। दमा के मरीज़ बढ़ सकते हैं; कृपया {{ pickup_hi }} तक इनहेलर और नेबुलाइज़र का स्टॉक जाँचें।",
           "en": "{{ school }}: 'Poor' air (AQI {{ aqi }}) on {{ date_en }}. Expect more asthma visits; please check inhaler and nebuliser stock by {{ pickup_en }}."},
    "T2": {"hi": "🌫 {{ school }}: {{ date_hi }} को {{ from_hi }} से हवा 'बहुत खराब' (AQI {{ aqi }}) रहेगी। श्वसन और आपातकालीन वार्ड सतर्क; ऑक्सीजन का स्टॉक भरें। कृपया {{ pickup_hi }} तक दो बेड तैयार रखें।",
           "en": "{{ school }}: 'Very Poor' air (AQI {{ aqi }}) from {{ from_en }} on {{ date_en }}. Respiratory and emergency wards on alert; top up oxygen. Please keep two beds ready by {{ pickup_en }}."},
    "T3": {"hi": "🌫 {{ school }}: {{ date_hi }} को हवा 'गंभीर' (AQI {{ aqi }}) रहेगी। शाम को अतिरिक्त स्टाफ़; ऑक्सीजन जाँचा हुआ। कृपया {{ pickup_hi }} तक बेड तैयार रखें।",
           "en": "{{ school }}: 'Severe' air (AQI {{ aqi }}) on {{ date_en }}. Extra staff in the evening; oxygen verified. Please keep beds ready by {{ pickup_en }}."},
    "T4": {"hi": "🌫 {{ school }}: {{ date_hi }} को हवा 'गंभीर+' (AQI {{ aqi }}) रहेगी। वार्ड चौबीसों घंटे सतर्क; हेल्पलाइन चालू। कृपया {{ pickup_hi }} तक सांस की तकलीफ़ के मामलों के लिए तैयार रहें।",
           "en": "{{ school }}: 'Severe+' air (AQI {{ aqi }}) on {{ date_en }}. Wards on alert round the clock; helpline staffed. Please be ready for breathlessness cases by {{ pickup_en }}."},
}


def _short(name: str, limit: int = 34) -> str:
    """Cut a long entity name at a word boundary (never mid-word) and drop a trailing '(demo)'."""
    name = name.replace("(demo)", "").strip()
    if len(name) <= limit:
        return name
    cut = name[:limit].rsplit(" ", 1)[0].rstrip(",")
    return cut or name[:limit]


def _dates(date_iso: str) -> tuple[str, str]:
    d = datetime.strptime(date_iso, "%Y-%m-%d")
    return f"{d.day} {_HI_MONTHS[d.month - 1]}", f"{_EN_MONTHS[d.month - 1]} {d.day}"


def _spoken(hhmm: str, hi: bool) -> str:
    h, m = (int(x) for x in hhmm.split(":"))
    if hi:
        return f"{h}:{m:02d} बजे" if m else f"{h} बजे"
    ampm = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {ampm}" if m else f"{h12} {ampm}"


def render_source(name: str, date_iso: str, card: dict) -> dict:
    """District agriculture officer: dispatch message to the custom hiring centres."""
    date_hi, date_en = _dates(date_iso)
    top = ", ".join(c["name"] for c in card.get("cells", [])[:3]) or "none"
    ctx = {"school": _short(name, 30), "date_hi": date_hi, "date_en": date_en, "n_cells": len(card.get("cells", [])),
           "worst": card.get("dayTier", "Low"), "top": top, "burning": card.get("burningNow", 0),
           "from_hi": "9 बजे", "from_en": "9 am"}
    hi = _env.from_string(TEMPLATES_SOURCE["hi"]).render(ctx).strip()
    en = _env.from_string(TEMPLATES_SOURCE["en"]).render(ctx).strip()
    return {"hi": hi, "en": en, "chars": len(hi) + len(en), "source": "template"}


def render(school: str, date_iso: str, tier: str, windows: list[dict], peak_aqi: int | None,
           dismissal: tuple[str, str] | list[str] = ("15:00", "16:00"), actor: str = "school") -> dict:
    table = TEMPLATES_RWA if actor == "rwa" else TEMPLATES_HOSPITAL if actor == "hospital" else TEMPLATES
    tier = tier if tier in table else "T0"
    date_hi, date_en = _dates(date_iso)
    first_bad = next((w["fromIst"] for w in windows if w["tier"] in ("T2", "T3", "T4")), None) or "08:00"
    ctx = {"school": _short(school), "date_hi": date_hi, "date_en": date_en, "aqi": peak_aqi or "",
           "from_hi": _spoken(first_bad, True), "from_en": _spoken(first_bad, False),
           "pickup_hi": _spoken(dismissal[0], True), "pickup_en": _spoken(dismissal[0], False)}
    hi = _env.from_string(table[tier]["hi"]).render(ctx).strip()
    en = _env.from_string(table[tier]["en"]).render(ctx).strip()
    return {"hi": hi, "en": en, "chars": len(hi) + len(en), "source": "template"}
