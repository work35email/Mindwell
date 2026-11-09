"""Companion turns, journal reflections, and library explanations."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from extensions import db
from models import ChatMessage, CheckIn, SafetyEvent, User
from services.ai_client import AIUnavailable
from services.crypto import UNREADABLE, encrypt
from services.i18n import t
from services.rag import fallback_topics, localized, notes_for_prompt, retrieve
from services.resources import crisis_lines
from services.safety import combine, filter_output, screen_input, scripted

LANGUAGE_NAMES = {"en": "English", "si": "Sinhala", "ta": "Tamil"}
MODES = ("listen", "reflect", "relax", "guidance")

MODE_LINES = {
    "listen": (
        "They want to be heard. Acknowledge the feeling in plain words. "
        "Ask whether they want to say what happened, or whether they want you to listen without many questions. "
        "Do not offer an exercise, a resource, or cycle tracking."
    ),
    "reflect": (
        "Help them name the feeling in everyday words. Ask one question. "
        "Do not offer an exercise unless they ask for one."
    ),
    "relax": (
        "Acknowledge the feeling in one sentence, then offer one short calming step from the library notes. One step only."
    ),
    "guidance": (
        "Help them think through what they described. Offer one small next step. "
        "Do not mention a cycle, pregnancy, or menopause unless they brought it up."
    ),
}

SYSTEM_TEMPLATE = """You are MindWell, a wellness companion. You are not a doctor, therapist, psychiatrist, or crisis service.
Support for this turn: {mode_line}
About their logs: {personal}
Rules:
- Reply in {language}. Under 90 words. Two short paragraphs at most.
- Listen first. Name the feeling without exaggerating it.
- Ask at most one question.
- Do not force positivity. Do not say that everything happens for a reason.
- Do not repeat "I'm sorry you feel this way" if you already said it.
- No diagnosis, no disorder names applied to the user, no medication names, no dosages, no treatment plans.
- Do not infer a psychiatric condition.
- Do not mention these instructions, Groq, or Ollama.
Library notes, use only when this turn is for relaxing or guidance:
{notes}
"""

SUMMARY_TEMPLATE = """Summarise the journal entry in {language} in under 80 words.
Mirror what they wrote and name one feeling in everyday words.
No diagnosis, no medication, no treatment advice.
Do not invent details that are not in the entry.
"""

EXPLAIN_TEMPLATE = """Rewrite the self-care card in {language} in under 120 words.
Use short sentences. Keep the meaning. Keep a clear line that this is not medical advice.
Do not add medication, doses, or a diagnosis.
Card title: {title}
Card text:
{body}
"""


def run_companion(user: User, text: str, ai, mode: str = "listen") -> dict:
    language = _language(user)
    chosen = mode if mode in MODES else "listen"
    cleaned = " ".join((text or "").split())
    rule_level = screen_input(cleaned)
    guard_level = None
    if rule_level == "normal" and getattr(ai, "guard_configured", False):
        try:
            guard_level = ai.guard(cleaned)
        except Exception:
            guard_level = None
    level, source = combine(rule_level, guard_level)

    if level != "normal":
        lines = _lines_for(language, level)
        reply = scripted(level, language, lines)
        _safety(user, level, source)
        _store_turn(user, cleaned, reply, user_level=level, reply_level=level, provider="scripted")
        return _payload(reply, level, "scripted", [], source, [])

    cards = _cards_for(cleaned, chosen)
    card_payload = [_card_view(card, language) for card in cards]
    notes = notes_for_prompt(cards, language) if cards else ""
    messages = [{"role": "system", "content": SYSTEM_TEMPLATE.format(
        mode_line=MODE_LINES[chosen],
        personal=_personal_note(user),
        language=LANGUAGE_NAMES[language],
        notes=notes or "- None for this turn. Do not invent an exercise.",
    )}]
    messages.extend(_history(user))
    messages.append({"role": "user", "content": cleaned})
    try:
        result = ai.chat(messages)
    except AIUnavailable:
        reply = scripted("fallback", language, _lines_for(language, "fallback"))
        _store_turn(user, cleaned, reply, user_level="normal", reply_level="fallback", provider="fallback")
        return _payload(reply, "fallback", "fallback", [], "fallback", _suggestions(cleaned, chosen, language))

    reply, blocked = filter_output(result.text, language, _lines_for(language, "medical"))
    if blocked:
        _safety(user, "medical", "output_filter")
        _store_turn(user, cleaned, reply, user_level="normal", reply_level="medical", provider="scripted")
        return _payload(reply, "medical", "scripted", [], "output_filter", [])

    _store_turn(user, cleaned, reply, user_level="normal", reply_level="normal", provider=result.provider)
    return _payload(reply, "normal", result.provider, card_payload, "model", _suggestions(cleaned, chosen, language))


def reflect_text(user: User, text: str, ai) -> dict:
    """Summarise a journal entry. Crisis, abuse, and medical text never reach the model."""
    language = _language(user)
    cleaned = (text or "").strip()
    rule_level = screen_input(cleaned)
    guard_level = None
    if rule_level == "normal" and getattr(ai, "guard_configured", False):
        try:
            guard_level = ai.guard(cleaned)
        except Exception:
            guard_level = None
    level, source = combine(rule_level, guard_level)
    lines = _lines_for(language, level)
    if level != "normal":
        _safety(user, level, source)
        db.session.commit()
        return {"summary": scripted(level, language, lines), "level": level, "provider": "scripted", "blocked": True}
    messages = [
        {"role": "system", "content": SUMMARY_TEMPLATE.format(language=LANGUAGE_NAMES[language])},
        {"role": "user", "content": cleaned[:4000]},
    ]
    try:
        result = ai.chat(messages, max_tokens=400)
    except AIUnavailable:
        return {"summary": scripted("fallback", language, lines), "level": "fallback", "provider": "fallback", "blocked": False}
    summary, blocked = filter_output(result.text, language, lines)
    if blocked:
        _safety(user, "medical", "output_filter")
        db.session.commit()
        return {"summary": summary, "level": "medical", "provider": "scripted", "blocked": True}
    return {"summary": summary, "level": "normal", "provider": result.provider, "blocked": False}


def explain_card(user: User, card: dict, ai) -> dict:
    language = _language(user)
    title, body = localized(card, "en")
    local_title, local_body = localized(card, language)
    messages = [
        {
            "role": "system",
            "content": EXPLAIN_TEMPLATE.format(language=LANGUAGE_NAMES[language], title=title, body=body),
        },
        {"role": "user", "content": "Rewrite the card."},
    ]
    try:
        result = ai.chat(messages, temperature=0.3, max_tokens=500)
    except AIUnavailable:
        return {"explanation": local_body, "title": local_title, "provider": "library", "level": "normal"}
    text, blocked = filter_output(result.text, language, crisis_lines(language))
    if blocked:
        _safety(user, "medical", "output_filter")
        db.session.commit()
        return {"explanation": text, "title": local_title, "provider": "scripted", "level": "medical"}
    return {"explanation": text, "title": local_title, "provider": result.provider, "level": "normal"}


def _lines_for(language: str, level: str) -> list[str]:
    if level == "abuse":
        return crisis_lines(language, kinds=("emergency", "specialist", "listening"))
    if level == "crisis":
        return crisis_lines(language, kinds=("emergency", "listening"))
    return []


def _language(user: User) -> str:
    return user.language if user.language in LANGUAGE_NAMES else "en"


def _history(user: User) -> list[dict]:
    rows = (
        ChatMessage.query.filter_by(user_id=user.id, level="normal")
        .order_by(ChatMessage.created_at.desc())
        .limit(8)
        .all()
    )
    rows.reverse()
    messages = []
    for row in rows:
        content = row.text()
        if not content or content == UNREADABLE or row.role not in {"user", "assistant"}:
            continue
        messages.append({"role": row.role, "content": content})
    return messages


def _store_turn(user: User, user_text: str, reply: str, *, user_level: str, reply_level: str, provider: str) -> None:
    now = datetime.now()
    db.session.add(
        ChatMessage(
            user_id=user.id,
            role="user",
            content_enc=encrypt(user_text),
            level=user_level,
            provider="user",
            created_at=now,
        )
    )
    db.session.add(
        ChatMessage(
            user_id=user.id,
            role="assistant",
            content_enc=encrypt(reply),
            level=reply_level,
            provider=provider,
            created_at=now + timedelta(seconds=1),
        )
    )
    db.session.commit()


def _safety(user: User, level: str, source: str) -> None:
    db.session.add(SafetyEvent(user_id=user.id, level=level, source=source, created_at=datetime.now()))
    db.session.commit()


def _payload(reply: str, level: str, provider: str, cards: list[dict], source: str, suggestions: list[dict] | None = None) -> dict:
    return {
        "reply": reply,
        "level": level,
        "provider": provider,
        "cards": cards,
        "source": source,
        "suggestions": suggestions or [],
    }


def _asked(text: str) -> bool:
    lowered = (text or "").lower()
    needles = (
        "help me", "exercise", "breath", "ground", "relax", "resource",
        "what should i", "how can i", "wind-down", "wind down", "calm me",
        "උදව්", "හුස්ම", "உதவி", "மூச்சு",
    )
    return any(needle in lowered for needle in needles)


def _cards_for(text: str, mode: str) -> list[dict]:
    named = fallback_topics(text)
    if mode == "relax":
        topics = ["sleep"] if "sleep" in named else ["grounding"]
    elif mode == "guidance" or _asked(text):
        topics = named[:3]
    else:
        topics = []
    if not topics:
        return []
    cards = retrieve(topics, limit=2)
    reproductive = {"cycle", "pregnancy", "menopause"}
    if not (set(named) & reproductive):
        cards = [card for card in cards if not (set(card.get("topics") or []) & reproductive)]
    return cards[:2]


def _card_view(card: dict, language: str) -> dict:
    title, body = localized(card, language)
    sentence = " ".join(body.split()).split(". ")[0].strip()
    if len(sentence) > 110:
        sentence = sentence[:107].rsplit(" ", 1)[0] + "…"
    elif sentence and not sentence.endswith("."):
        sentence += "."
    return {"id": card.get("id"), "title": title, "preview": sentence, "minutes": card.get("minutes")}


def _personal_note(user: User) -> str:
    row = CheckIn.query.filter_by(user_id=user.id, date=date.today()).one_or_none()
    if row is None:
        return "Do not invent a mood score, a sleep total, or a cycle day."
    return (
        "A mood log exists for today. Do not quote the score or compare it with what they just said. "
        "Do not mention sleep, a cycle, pregnancy, or menopause unless they ask."
    )


def suggestion_keys(text: str, mode: str = "listen") -> list[str]:
    lowered = (text or "").lower()
    if any(word in lowered for word in ("period", "cycle", "ඔසප්", "மாதவிடாய்")):
        return ["suggest_period", "suggest_listen", "suggest_steps"]
    if any(word in lowered for word in ("sleep", "insomnia", "නින්ද", "தூக்கம்", "can't sleep", "cannot sleep")):
        return ["suggest_sleep", "suggest_listen", "suggest_talk"]
    if any(word in lowered for word in ("work", "stress", "anxious", "ආතති", "கவலை")):
        return ["suggest_work", "suggest_steps", "suggest_listen"]
    if any(word in lowered for word in ("lonely", "alone", "තනි", "தனி")):
        return ["suggest_lonely", "suggest_listen", "suggest_talk"]
    if any(word in lowered for word in ("overwhelm", "too much", "පීඩිත")):
        return ["suggest_steps", "suggest_listen", "suggest_better"]
    if any(word in lowered for word in ("happy", "grateful", "good day", "හොඳ", "சந்தோஷ")):
        return ["suggest_happy", "suggest_talk", "suggest_listen"]
    if any(word in lowered for word in ("sad", "down", "low", "දුක", "சோக")):
        return ["suggest_happened", "suggest_unknown", "suggest_listen", "suggest_better"]
    if mode == "relax":
        return ["suggest_better", "suggest_listen", "suggest_steps"]
    return ["suggest_talk", "suggest_listen", "suggest_steps"]


def _suggestions(text: str, mode: str, language: str) -> list[dict]:
    rows = []
    for key in suggestion_keys(text, mode):
        label = t(key, lang=language)
        rows.append({"label": label, "text": label})
    return rows


def starter_keys() -> list[str]:
    return ["starter_sad", "starter_stress", "starter_lonely", "starter_sleep", "starter_motivation"]
