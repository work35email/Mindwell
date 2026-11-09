"""SQLite models. Sensitive free text is stored only as Fernet ciphertext."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import List, Optional

from flask_login import UserMixin
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from services.crypto import decrypt
from services.i18n import current_language, show_text

CONSENT_TYPES = (
    "mental_health",
    "reproductive",
    "voice",
    "ai_processing",
    "report_sharing",
)

EMOTIONS = (
    "calm",
    "anxious",
    "overwhelmed",
    "tired",
    "sad",
    "irritable",
    "hopeful",
    "numb",
    "grateful",
    "angry",
    "lonely",
)

MOOD_SCALE = (
    (1, "😢", "mood_1"),
    (2, "😔", "mood_2"),
    (3, "😐", "mood_3"),
    (4, "🙂", "mood_4"),
    (5, "😄", "mood_5"),
)
MOOD_EMOJI = {value: emoji for value, emoji, _key in MOOD_SCALE}

EMOTION_EMOJI = {
    "calm": "😌",
    "anxious": "😰",
    "overwhelmed": "🥺",
    "tired": "🥱",
    "sad": "😢",
    "irritable": "😒",
    "hopeful": "🌈",
    "numb": "😑",
    "grateful": "🥹",
    "angry": "😠",
    "lonely": "🫂",
}

INFLUENCES = (
    "work",
    "relationships",
    "sleep",
    "health",
    "family",
    "personal",
    "other",
)

STRESS_TAGS = (
    "work",
    "home",
    "money",
    "health",
    "relationships",
    "caregiving",
    "other",
)

LANGUAGES = ("en", "si", "ta")


def _loads(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(8), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    consents: Mapped[List["Consent"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Consent(db.Model):
    __tablename__ = "consent"
    __table_args__ = (UniqueConstraint("user_id", "type", name="uq_consent_user_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    granted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    user: Mapped[User] = relationship(back_populates="consents")


class CheckIn(db.Model):
    __tablename__ = "checkin"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_checkin_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    mood: Mapped[int] = mapped_column(Integer)
    mood_emoji: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    energy: Mapped[int] = mapped_column(Integer)
    emotions: Mapped[str] = mapped_column(Text, default="[]")
    influences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note_enc: Mapped[Optional[str]] = mapped_column("note", Text, nullable=True)

    def face(self) -> str:
        if self.mood_emoji:
            return self.mood_emoji
        return MOOD_EMOJI.get(self.mood, "")

    def emotion_list(self) -> list[str]:
        return [e for e in _loads(self.emotions) if isinstance(e, str)]

    def influence_list(self) -> list[str]:
        return [item for item in _loads(self.influences) if isinstance(item, str)]

    def note_text(self) -> str:
        return show_text(decrypt(self.note_enc))


class SleepLog(db.Model):
    __tablename__ = "sleep_log"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_sleep_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    hours: Mapped[float] = mapped_column(Float)
    quality: Mapped[int] = mapped_column(Integer)


class StressLog(db.Model):
    __tablename__ = "stress_log"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_stress_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    stress: Mapped[int] = mapped_column(Integer)
    tags: Mapped[str] = mapped_column(Text, default="[]")

    def tag_list(self) -> list[str]:
        return [t for t in _loads(self.tags) if isinstance(t, str)]


class CycleLog(db.Model):
    __tablename__ = "cycle_log"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_cycle_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    cycle_day: Mapped[int] = mapped_column(Integer)
    note_enc: Mapped[Optional[str]] = mapped_column("note", Text, nullable=True)

    def note_text(self) -> str:
        return show_text(decrypt(self.note_enc))


class Journal(db.Model):
    __tablename__ = "journal"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    source: Mapped[str] = mapped_column(String(16), default="text")
    language: Mapped[str] = mapped_column(String(8), default="en")
    body_enc: Mapped[Optional[str]] = mapped_column("text", Text, nullable=True)
    summary_enc: Mapped[Optional[str]] = mapped_column("summary", Text, nullable=True)
    summary_provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    def body_text(self) -> str:
        return show_text(decrypt(self.body_enc))

    def summary_text(self) -> str:
        return show_text(decrypt(self.summary_enc))

    def shown_language(self) -> str:
        if self.language == "all":
            return current_language()
        return self.language


class ChatMessage(db.Model):
    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content_enc: Mapped[Optional[str]] = mapped_column("content", Text, nullable=True)
    level: Mapped[str] = mapped_column(String(16), default="normal")
    provider: Mapped[str] = mapped_column(String(32), default="scripted")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)

    def text(self) -> str:
        return show_text(decrypt(self.content_enc))


class SafetyEvent(db.Model):
    """Level and source only. Message text is never copied here."""

    __tablename__ = "safety_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
