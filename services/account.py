"""Consent, audit, export, and deletion. Audit details never include journal or chat text."""

from __future__ import annotations

from datetime import datetime

from extensions import db
from models import (
    CONSENT_TYPES,
    AuditLog,
    ChatMessage,
    CheckIn,
    Consent,
    CycleLog,
    Journal,
    SafetyEvent,
    SleepLog,
    StressLog,
    User,
)


def granted_types(user: User) -> set[str]:
    return {row.type for row in user.consents if row.granted}


def missing_consents(user: User, types: tuple[str, ...] | list[str]) -> list[str]:
    have = granted_types(user)
    return [name for name in types if name not in have]


def set_consent(user: User, consent_type: str, granted: bool) -> None:
    if consent_type not in CONSENT_TYPES:
        return
    row = Consent.query.filter_by(user_id=user.id, type=consent_type).one_or_none()
    now = datetime.now()
    if row is None:
        row = Consent(user_id=user.id, type=consent_type, granted=granted, updated_at=now)
        db.session.add(row)
    else:
        row.granted = granted
        row.updated_at = now
    audit(user.id, "consent", f"{consent_type}:{'yes' if granted else 'no'}")


def audit(user_id: int | None, action: str, detail: str = "") -> None:
    db.session.add(
        AuditLog(user_id=user_id, action=action[:64], detail=(detail or "")[:255], created_at=datetime.now())
    )


def export_payload(user: User) -> dict:
    def day(value) -> str:
        return value.isoformat() if value else ""

    def stamp(value) -> str:
        return value.isoformat(timespec="minutes") if value else ""

    return {
        "exported_at": datetime.now().isoformat(timespec="minutes"),
        "notice": "Wellness export for the signed-in person. Not a medical record.",
        "email": user.email,
        "language": user.language,
        "consents": [
            {"type": row.type, "granted": row.granted, "updated_at": stamp(row.updated_at)} for row in user.consents
        ],
        "checkins": [
            {
                "date": day(row.date),
                "mood": row.mood,
                "mood_emoji": row.face(),
                "energy": row.energy,
                "emotions": row.emotion_list(),
                "influences": row.influence_list(),
                "note": row.note_text(),
            }
            for row in CheckIn.query.filter_by(user_id=user.id).order_by(CheckIn.date).all()
        ],
        "sleep": [
            {"date": day(row.date), "hours": row.hours, "quality": row.quality}
            for row in SleepLog.query.filter_by(user_id=user.id).order_by(SleepLog.date).all()
        ],
        "stress": [
            {"date": day(row.date), "stress": row.stress, "tags": row.tag_list()}
            for row in StressLog.query.filter_by(user_id=user.id).order_by(StressLog.date).all()
        ],
        "cycle": [
            {"date": day(row.date), "cycle_day": row.cycle_day}
            for row in CycleLog.query.filter_by(user_id=user.id).order_by(CycleLog.date).all()
        ],
        "journals": [
            {
                "created_at": stamp(row.created_at),
                "source": row.source,
                "language": row.language,
                "text": row.body_text(),
                "summary": row.summary_text(),
            }
            for row in Journal.query.filter_by(user_id=user.id).order_by(Journal.created_at).all()
        ],
        "messages": [
            {
                "created_at": stamp(row.created_at),
                "role": row.role,
                "level": row.level,
                "provider": row.provider,
                "content": row.text(),
            }
            for row in ChatMessage.query.filter_by(user_id=user.id).order_by(ChatMessage.created_at).all()
        ],
    }


def delete_account(user: User) -> None:
    user_id = user.id
    for model in (SafetyEvent, AuditLog, ChatMessage, Journal, CheckIn, SleepLog, StressLog, CycleLog, Consent):
        model.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    db.session.delete(user)
    db.session.commit()
