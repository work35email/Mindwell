"""Wellness companion. Crisis, abuse, medical, and boundary turns never call the chat model."""

from __future__ import annotations

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from extensions import db
from models import ChatMessage
from services.companion import MODES, _card_view, _cards_for, _language, run_companion, starter_keys, suggestion_keys
from services.i18n import t

from .helpers import ai_client, consent_required, limited

bp = Blueprint("companion", __name__)


@bp.route("/companion", methods=["GET", "POST"])
@login_required
@consent_required("mental_health", "ai_processing")
def page():
    if request.method == "POST":
        if not limited(current_user.id):
            flash(t("rate_limited"))
            return redirect(url_for("companion.page"))
        text = request.form.get("message") or ""
        mode = _mode(request.form.get("mode"))
        if not text.strip() or len(text) > 2000:
            flash(t("error_range"))
        else:
            result = run_companion(current_user, text, ai_client(), mode=mode)
            _log(result)
        return redirect(url_for("companion.page"))
    rows = (
        ChatMessage.query.filter_by(user_id=current_user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(40)
        .all()
    )
    rows.reverse()
    messages = [
        {
            "role": row.role,
            "content": row.text(),
            "level": row.level,
            "provider": row.provider,
            "created_at": row.created_at,
        }
        for row in rows
    ]
    mode = _mode(session.get("companion_mode"))
    last_user = ""
    for message in reversed(messages):
        if message["role"] == "user":
            last_user = message["content"]
            break
    language = _language(current_user)
    keys = suggestion_keys(last_user, mode) if last_user else starter_keys()
    suggestions = [{"label": t(key, lang=language), "text": t(key, lang=language)} for key in keys]
    cards = [_card_view(card, language) for card in _cards_for(last_user, mode)] if last_user else []
    return render_template(
        "companion.html",
        messages=messages,
        missing=[],
        mode=mode,
        modes=MODES,
        suggestions=suggestions,
        cards=cards,
    )


@bp.post("/api/chat")
@login_required
@consent_required("mental_health", "ai_processing")
def chat():
    if not limited(current_user.id):
        return jsonify({"error": "rate_limited"}), 429
    payload = request.get_json(silent=True) or {}
    text = payload.get("message") or ""
    if not str(text).strip() or len(str(text)) > 2000:
        return jsonify({"error": "invalid"}), 400
    result = run_companion(current_user, str(text), ai_client(), mode=_mode(payload.get("mode")))
    _log(result)
    return jsonify(result)


@bp.post("/companion/clear")
@login_required
@consent_required("mental_health", "ai_processing")
def clear():
    ChatMessage.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    session.pop("companion_mode", None)
    return redirect(url_for("companion.page"))


def _mode(value) -> str:
    chosen = str(value or "listen")
    if chosen not in MODES:
        return "listen"
    session["companion_mode"] = chosen
    return chosen


def _log(result: dict) -> None:
    from flask import current_app

    current_app.logger.info("companion level=%s provider=%s source=%s", result.get("level"), result.get("provider"), result.get("source"))
