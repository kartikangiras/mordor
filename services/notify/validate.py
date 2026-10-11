"""Hard constraints for the parent message (DESIGN.md §6.4). The agent's output must pass all
of them or the template is used instead - the card must never fail to produce a message."""
from __future__ import annotations

import re

MAX_CHARS = 400
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")
_TIME = re.compile(r"\b\d{1,2}(:\d{2})?\s?(am|pm|बजे)", re.IGNORECASE)
BANNED = {
    "emergency": ["emergency", "आपातकाल", "इमरजेंसी"],
    "medication": ["medicine", "medication", "tablet", "inhaler", "dose", "दवा", "दवाई", "इनहेलर", "गोली"],
    "closure": ["school is closed", "school closed", "school will be closed", "remain closed", "holiday declared",
                "स्कूल बंद", "छुट्टी घोषित", "बंद रहेगा"],
}


# A hospital writes to its own wards, so it may name the emergency ward and its stock of inhalers
# and oxygen; parents and residents never hear either word.
RELAXED_FOR = {"hospital": {"emergency", "medication"}}


def check(msg: dict, actor: str = "school") -> tuple[bool, list[str]]:
    reasons: list[str] = []
    skip = RELAXED_FOR.get(actor, set())
    hi, en = str(msg.get("hi", "")).strip(), str(msg.get("en", "")).strip()
    if not hi or not en:
        reasons.append("both hi and en required")
    if hi and not _DEVANAGARI.search(hi):
        reasons.append("hindi part must be in devanagari")
    if _DEVANAGARI.search(en):
        reasons.append("english part contains devanagari")
    total = len(hi) + len(en)
    if total > MAX_CHARS:
        reasons.append(f"{total} chars > {MAX_CHARS}")
    emojis = _EMOJI.findall(hi + en)
    if len(emojis) > 1 or (emojis and not _EMOJI.match(hi)):
        reasons.append("at most one leading emoji")
    low = (hi + " " + en).lower()
    for kind, words in BANNED.items():
        if kind in skip:
            continue
        if any(w in low for w in words):
            reasons.append(f"banned: {kind}")
    if not _TIME.search(hi + " " + en) and not re.search(r"\d{1,2}\s(बजे|am|pm)", hi + en):
        reasons.append("no concrete time named")
    return (not reasons), reasons
