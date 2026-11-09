"""Topic tags and library retrieval. No embeddings: Groq has no embeddings API."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY_PATH = ROOT / "content" / "library.json"

TAGS = (
    "sleep",
    "stress",
    "mood",
    "cycle",
    "burnout",
    "menopause",
    "pregnancy",
    "breathing",
    "grounding",
    "boundaries",
    "journaling",
    "movement",
    "connection",
)

TAG_PROMPT = (
    "Tag the wellness message. Return JSON only: {\"topics\": [..]}. "
    "Use at most 3 tags from this list and no others: " + ", ".join(TAGS) + ". "
    "If nothing fits, return {\"topics\": []}."
)

KEYWORD_TAGS: tuple[tuple[str, str], ...] = (
    ("sleep", "sleep"),
    ("insomnia", "sleep"),
    ("නින්ද", "sleep"),
    ("නිදාගන්න", "sleep"),
    ("தூக்கம்", "sleep"),
    ("stress", "stress"),
    ("anxious", "stress"),
    ("overwhelm", "stress"),
    ("ආතති", "stress"),
    ("கவலை", "stress"),
    ("மன அழுத்த", "stress"),
    ("mood", "mood"),
    ("lonely", "mood"),
    ("තනිකම", "mood"),
    ("தனிமை", "mood"),
    ("cycle", "cycle"),
    ("period", "cycle"),
    ("ඔසප්", "cycle"),
    ("மாதவிடாய்", "cycle"),
    ("burnout", "burnout"),
    ("exhausted", "burnout"),
    ("වෙහෙස", "burnout"),
    ("சோர்வு", "burnout"),
    ("menopause", "menopause"),
    ("hot flash", "menopause"),
    ("ආර්තව", "menopause"),
    ("மாதவிடாய் நிறுத்தம்", "menopause"),
    ("pregnan", "pregnancy"),
    ("postpartum", "pregnancy"),
    ("ගැබිනි", "pregnancy"),
    ("கர்ப்ப", "pregnancy"),
    ("breath", "breathing"),
    ("හුස්ම", "breathing"),
    ("மூச்சு", "breathing"),
    ("ground", "grounding"),
    ("panic", "grounding"),
    ("boundary", "boundaries"),
    ("සීමාව", "boundaries"),
    ("எல்லை", "boundaries"),
    ("journal", "journaling"),
    ("සටහන", "journaling"),
    ("குறிப்பு", "journaling"),
    ("walk", "movement"),
    ("ඇවිදි", "movement"),
    ("நடை", "movement"),
    ("friend", "connection"),
    ("මිතුර", "connection"),
    ("நண்ப", "connection"),
)


@lru_cache(maxsize=1)
def load_cards() -> tuple[dict, ...]:
    data = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    cards = data.get("cards", [])
    return tuple(card for card in cards if isinstance(card, dict))


def card_by_id(card_id: str) -> dict | None:
    for card in load_cards():
        if card.get("id") == card_id:
            return card
    return None


def localized(card: dict, language: str) -> tuple[str, str]:
    lang = language if language in {"en", "si", "ta"} else "en"
    titles = card.get("titles") or {}
    bodies = card.get("bodies") or {}
    title = titles.get(lang) or titles.get("en") or card.get("id", "")
    body = bodies.get(lang) or bodies.get("en") or ""
    return title, body


def fallback_topics(text: str) -> list[str]:
    lowered = (text or "").lower()
    found: list[str] = []
    for needle, tag in KEYWORD_TAGS:
        if needle in lowered and tag not in found:
            found.append(tag)
        if len(found) == 3:
            break
    return found


def topics_from_model(payload: dict | None) -> list[str]:
    if not payload:
        return []
    raw = payload.get("topics") or []
    if not isinstance(raw, list):
        return []
    cleaned: list[str] = []
    for item in raw:
        tag = str(item).strip().lower()
        if tag in TAGS and tag not in cleaned:
            cleaned.append(tag)
        if len(cleaned) == 3:
            break
    return cleaned


def retrieve(topics: list[str], *, limit: int = 3, audience: str | None = None) -> list[dict]:
    scored: list[tuple[int, dict]] = []
    wanted = set(topics)
    for card in load_cards():
        audiences = card.get("audiences") or ["general"]
        if audience and audience not in audiences and "general" not in audiences:
            continue
        overlap = len(wanted & set(card.get("topics") or []))
        if overlap:
            scored.append((overlap, card))
    scored.sort(key=lambda pair: (-pair[0], pair[1].get("id", "")))
    picked = [card for _score, card in scored[:limit]]
    if picked:
        return picked
    # A steady default so an untagged message still has something concrete to offer.
    for card in load_cards():
        if card.get("id") == "box-breathing":
            return [card]
    return list(load_cards()[:1])


def filter_cards(topic: str | None = None, audience: str | None = None) -> list[dict]:
    cards = []
    for card in load_cards():
        if topic and topic not in (card.get("topics") or []):
            continue
        if audience and audience not in (card.get("audiences") or []):
            continue
        cards.append(card)
    return cards


def notes_for_prompt(cards: list[dict], language: str) -> str:
    chunks = []
    for card in cards:
        title, body = localized(card, "en")
        # English notes keep the prompt stable. The reply language is set separately.
        snippet = " ".join(body.split())
        if len(snippet) > 420:
            snippet = snippet[:420].rsplit(" ", 1)[0] + "…"
        chunks.append(f"- {title}: {snippet}")
    return "\n".join(chunks)
