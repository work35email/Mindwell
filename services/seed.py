"""Twenty days for the demo account. Index 0 is today.

Most days sit in the middle. Weekends rest a little higher. One short night
and one very low day are the outliers. The same record is stored for English,
Sinhala, and Tamil.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from extensions import db
from models import (
    CONSENT_TYPES,
    MOOD_EMOJI,
    ChatMessage,
    CheckIn,
    Consent,
    CycleLog,
    Journal,
    SleepLog,
    StressLog,
    User,
)
from services.account import audit
from services.crypto import encrypt
from services.samples import CYCLE_NOTES, SAMPLES, pack, summary_pack

DEMO_EMAIL = "demo@mindwell.local"
DEMO_PASSWORD = "mindwell-demo"
DAY_COUNT = 20

PROFILES = (
    (4, 3, 2, 7.3, 4, ("calm", "grateful"), ("work", "personal"), ("work",)),
    (5, 4, 1, 8.4, 5, ("grateful", "hopeful"), ("family", "personal"), ("home",)),
    (4, 4, 2, 8.0, 4, ("calm", "hopeful"), ("relationships", "family"), ("home",)),
    (3, 3, 3, 6.9, 3, ("tired", "calm"), ("work",), ("work",)),
    (2, 2, 4, 5.2, 2, ("anxious", "irritable"), ("work", "sleep"), ("work",)),
    (3, 3, 3, 7.0, 3, ("calm",), ("work",), ("work",)),
    (4, 3, 2, 7.2, 4, ("hopeful",), ("work", "personal"), ("work",)),
    (3, 3, 3, 6.8, 3, ("tired",), ("work",), ("work",)),
    (4, 4, 2, 8.2, 5, ("grateful",), ("family",), ("home",)),
    (4, 4, 1, 8.6, 5, ("hopeful", "grateful"), ("personal", "family"), ("home",)),
    (1, 1, 5, 4.6, 1, ("sad", "overwhelmed", "lonely"), ("sleep", "health"), ("health", "work")),
    (2, 2, 5, 5.0, 1, ("anxious", "tired", "angry"), ("work", "sleep"), ("work",)),
    (3, 2, 4, 6.1, 2, ("overwhelmed",), ("work", "family"), ("work", "caregiving")),
    (3, 3, 3, 6.9, 3, ("irritable",), ("work", "other"), ("money",)),
    (4, 3, 2, 7.1, 4, ("calm",), ("work",), ("work",)),
    (5, 5, 1, 8.8, 5, ("grateful", "hopeful"), ("family", "personal"), ("home",)),
    (4, 4, 2, 7.9, 4, ("calm",), ("relationships",), ("relationships",)),
    (3, 3, 3, 7.0, 3, ("numb", "calm"), ("work", "other"), ("money", "other")),
    (4, 3, 2, 7.4, 4, ("hopeful",), ("work", "health"), ("health",)),
    (3, 3, 3, 6.7, 3, ("tired", "calm"), ("sleep", "health"), ("health",)),
)


def _cycle_day(index: int) -> int:
    """Count forward from day 18, then start again at day 1. Index 0 is today."""
    day_num = 18 + (DAY_COUNT - 1 - index)
    if day_num > 28:
        day_num -= 28
    return day_num


def seed_demo() -> None:
    user = User.query.filter_by(email=DEMO_EMAIL).one_or_none()
    if user is None:
        user = _create_demo_user()
    _replace_logs(user)
    db.session.commit()
    print(f"Demo ready: {DEMO_EMAIL} / {DEMO_PASSWORD}. {DAY_COUNT} varied days.")


def _create_demo_user() -> User:
    user = User(email=DEMO_EMAIL, language="en", created_at=datetime.now() - timedelta(days=DAY_COUNT))
    user.set_password(DEMO_PASSWORD)
    db.session.add(user)
    db.session.flush()
    now = datetime.now()
    for consent_type in CONSENT_TYPES:
        db.session.add(Consent(user_id=user.id, type=consent_type, granted=True, updated_at=now))
    return user


def _replace_logs(user: User) -> None:
    for model in (CheckIn, SleepLog, StressLog, CycleLog, Journal, ChatMessage):
        model.query.filter_by(user_id=user.id).delete()
    today = date.today()
    now = datetime.now().replace(microsecond=0)
    for index, profile in enumerate(PROFILES):
        mood, energy, stress, hours, quality, emotions, influences, tags = profile
        day = today - timedelta(days=index)
        db.session.add(
            CheckIn(
                user_id=user.id,
                date=day,
                mood=mood,
                mood_emoji=MOOD_EMOJI[mood],
                energy=energy,
                emotions=json.dumps(list(emotions)),
                influences=json.dumps(list(influences)),
                note_enc=encrypt(pack(SAMPLES[index])),
            )
        )
        db.session.add(SleepLog(user_id=user.id, date=day, hours=hours, quality=quality))
        db.session.add(StressLog(user_id=user.id, date=day, stress=stress, tags=json.dumps(list(tags))))
        db.session.add(
            CycleLog(
                user_id=user.id,
                date=day,
                cycle_day=_cycle_day(index),
                note_enc=encrypt(pack(CYCLE_NOTES[index])),
            )
        )
        db.session.add(
            Journal(
                user_id=user.id,
                created_at=now - timedelta(days=index, hours=index % 5),
                source="voice" if index % 4 == 0 else "text",
                language="all",
                body_enc=encrypt(pack(SAMPLES[index])),
                summary_enc=encrypt(summary_pack(SAMPLES[index])),
                summary_provider="library",
            )
        )
    audit(user.id, "seed", "demo logs")
