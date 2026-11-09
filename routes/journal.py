"""Journal entries. Audio is transcribed in memory and never written to disk."""

from __future__ import annotations

import json
from datetime import datetime

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import LANGUAGES, Journal
from services.account import audit, missing_consents
from services.ai_client import TranscriptionUnavailable
from services.companion import reflect_text
from services.crypto import decrypt, encrypt
from services.i18n import t

from .helpers import ai_client, consent_required, limited

bp = Blueprint("journal", __name__)


@bp.get("/journal")
@login_required
@consent_required("mental_health")
def index():
    rows = Journal.query.filter_by(user_id=current_user.id).order_by(Journal.created_at.desc()).all()
    entries = [
        {
            "id": row.id,
            "created_at": row.created_at,
            "source": row.source,
            "language": row.shown_language(),
            "preview": (row.body_text() or "")[:180],
            "has_summary": bool(row.summary_text()),
        }
        for row in rows
    ]
    return render_template("journal/list.html", entries=entries)


@bp.route("/journal/new", methods=["GET", "POST"])
@login_required
@consent_required("mental_health")
def create():
    if request.method == "POST":
        body = (request.form.get("body") or "").strip()
        language = request.form.get("language") if request.form.get("language") in LANGUAGES else current_user.language
        source = "voice" if request.form.get("source") == "voice" else "text"
        if not body or len(body) > 8000:
            flash(t("error_range"))
            return render_template("journal/form.html", languages=LANGUAGES, draft=body, language=language, source=source)
        summary = None
        provider = None
        if request.form.get("reflect"):
            if missing_consents(current_user, ("ai_processing",)):
                flash(t("consent_needed"))
            elif not limited(current_user.id):
                flash(t("rate_limited"))
            else:
                result = reflect_text(current_user, body, ai_client())
                summary = result["summary"]
                provider = result["provider"]
        row = Journal(
            user_id=current_user.id,
            created_at=datetime.now(),
            source=source,
            language=language,
            body_enc=encrypt(body),
            summary_enc=encrypt(summary) if summary else None,
            summary_provider=provider,
        )
        db.session.add(row)
        audit(current_user.id, "journal", source)
        db.session.commit()
        flash(t("flash_journal"))
        return redirect(url_for("journal.detail", journal_id=row.id))
    return render_template(
        "journal/form.html",
        languages=LANGUAGES,
        draft="",
        language=current_user.language,
        source="text",
    )


@bp.get("/journal/<int:journal_id>")
@login_required
@consent_required("mental_health")
def detail(journal_id: int):
    row = _own(journal_id)
    return render_template("journal/detail.html", entry=row)


@bp.post("/journal/<int:journal_id>/summarize")
@login_required
@consent_required("mental_health", "ai_processing")
def summarize(journal_id: int):
    row = _own(journal_id)
    if not limited(current_user.id):
        flash(t("rate_limited"))
        return redirect(url_for("journal.detail", journal_id=row.id))
    result = reflect_text(current_user, row.body_text(), ai_client())
    row.summary_enc = encrypt(result["summary"])
    row.summary_provider = result["provider"]
    audit(current_user.id, "summary", result["provider"])
    db.session.commit()
    flash(t("flash_summary"))
    return redirect(url_for("journal.detail", journal_id=row.id))


@bp.route("/journal/<int:journal_id>/edit", methods=["GET", "POST"])
@login_required
@consent_required("mental_health")
def edit(journal_id: int):
    row = _own(journal_id)
    language = row.language if row.language in LANGUAGES else current_user.language
    if request.method == "POST":
        body = (request.form.get("body") or "").strip()
        chosen = request.form.get("language") if request.form.get("language") in LANGUAGES else language
        if not body or len(body) > 8000:
            flash(t("error_range"))
            return render_template(
                "journal/form.html",
                languages=LANGUAGES,
                draft=body,
                language=chosen,
                source=row.source,
                editing=True,
            )
        row.body_enc = _merge_body(row.body_enc, body, chosen)
        row.language = row.language if row.language == "all" else chosen
        if request.form.get("reflect"):
            if missing_consents(current_user, ("ai_processing",)):
                flash(t("consent_needed"))
            elif not limited(current_user.id):
                flash(t("rate_limited"))
            else:
                result = reflect_text(current_user, body, ai_client())
                row.summary_enc = encrypt(result["summary"])
                row.summary_provider = result["provider"]
        audit(current_user.id, "journal_update", row.source)
        db.session.commit()
        flash(t("flash_journal"))
        return redirect(url_for("journal.detail", journal_id=row.id))
    return render_template(
        "journal/form.html",
        languages=LANGUAGES,
        draft=row.body_text(),
        language=language,
        source=row.source,
        editing=True,
    )


@bp.post("/journal/<int:journal_id>/delete")
@login_required
@consent_required("mental_health")
def remove(journal_id: int):
    row = _own(journal_id)
    audit(current_user.id, "journal_delete", row.source)
    db.session.delete(row)
    db.session.commit()
    flash(t("flash_deleted"))
    return redirect(url_for("journal.index"))


@bp.post("/api/transcribe")
@login_required
@consent_required("voice", "ai_processing")
def transcribe():
    if not limited(current_user.id):
        return jsonify({"error": "rate_limited"}), 429
    upload = request.files.get("audio")
    if upload is None:
        return jsonify({"error": "missing_audio"}), 400
    audio = upload.read()
    if not audio or len(audio) > 10 * 1024 * 1024:
        return jsonify({"error": "invalid_audio"}), 400
    language = request.form.get("language") or current_user.language
    try:
        result = ai_client().transcribe(audio, upload.filename or "journal.webm", language)
    except TranscriptionUnavailable:
        return jsonify({"error": "transcription_unavailable", "message": t("voice_needs_groq")}), 503
    return jsonify({"text": result.text, "provider": result.provider})


@bp.post("/api/summarize")
@login_required
@consent_required("mental_health", "ai_processing")
def api_summarize():
    if not limited(current_user.id):
        return jsonify({"error": "rate_limited"}), 429
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    if not text or len(text) > 8000:
        return jsonify({"error": "invalid"}), 400
    return jsonify(reflect_text(current_user, text, ai_client()))


def _merge_body(existing_enc: str | None, text: str, language: str) -> str:
    """Keep the other languages when a stored note is an English/Sinhala/Tamil pack."""
    raw = decrypt(existing_enc) if existing_enc else ""
    if raw.lstrip().startswith("{"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and any(key in data for key in LANGUAGES):
            data[language] = text
            return encrypt(json.dumps(data, ensure_ascii=False))
    return encrypt(text)


def _own(journal_id: int) -> Journal:
    row = db.session.get(Journal, journal_id)
    if row is None or row.user_id != current_user.id:
        abort(404)
    return row
