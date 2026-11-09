"""Daily logs, dashboard, settings, export, and deletion."""

from __future__ import annotations

import json
from datetime import date, timedelta

from flask import Blueprint, abort, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user
from markupsafe import Markup

from extensions import db
from models import EMOTIONS, INFLUENCES, LANGUAGES, MOOD_EMOJI, STRESS_TAGS, CheckIn, CycleLog, SleepLog, StressLog, User
from services.account import audit, delete_account, export_payload, granted_types, missing_consents
from services.crypto import encrypt
from services.i18n import t
from services.stats import streak, svg_line

from .helpers import consent_required, parse_float, parse_int

bp = Blueprint("wellness", __name__)


@bp.get("/")
def home():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    today = date.today()
    checkins = CheckIn.query.filter_by(user_id=current_user.id).all()
    by_day = {row.date: row for row in checkins}
    start = today - timedelta(days=13)
    points = []
    for offset in range(14):
        day = start + timedelta(days=offset)
        row = by_day.get(day)
        if row:
            points.append((day.strftime("%d %b"), float(row.mood)))
    chart = Markup(svg_line(points, ymin=1, ymax=5, title=t("chart_mood")))
    return render_template(
        "dashboard.html",
        today=by_day.get(today),
        sleep=SleepLog.query.filter_by(user_id=current_user.id, date=today).one_or_none(),
        stress=StressLog.query.filter_by(user_id=current_user.id, date=today).one_or_none(),
        streak_count=streak(set(by_day), today),
        chart=chart,
        points=points,
        missing=missing_consents(current_user, ("mental_health", "ai_processing")),
        has_reproductive="reproductive" in granted_types(current_user),
        cycle=CycleLog.query.filter_by(user_id=current_user.id, date=today).one_or_none()
        if "reproductive" in granted_types(current_user)
        else None,
    )


@bp.route("/checkin", methods=["GET", "POST"])
@login_required
@consent_required("mental_health")
def checkin():
    day = _chosen_day()
    if day is None:
        flash(t("error_range"))
        day = date.today()
    row = CheckIn.query.filter_by(user_id=current_user.id, date=day).one_or_none()
    if request.method == "POST":
        mood = parse_int(request.form.get("mood"), 1, 5)
        energy = parse_int(request.form.get("energy"), 1, 5)
        emotions = [name for name in EMOTIONS if request.form.get(f"emotion_{name}")]
        influences = [name for name in INFLUENCES if request.form.get(f"influence_{name}")]
        note = (request.form.get("note") or "").strip()
        if mood is None or energy is None or len(note) > 2000:
            flash(t("error_range"))
        else:
            if row is None:
                row = CheckIn(user_id=current_user.id, date=day, mood=mood, energy=energy)
                db.session.add(row)
            row.mood = mood
            row.mood_emoji = MOOD_EMOJI[mood]
            row.energy = energy
            row.emotions = json.dumps(emotions)
            row.influences = json.dumps(influences)
            row.note_enc = encrypt(note)
            audit(current_user.id, "checkin", day.isoformat())
            db.session.commit()
            flash(t("flash_checkin"))
            return redirect(url_for("wellness.checkin", date=day.isoformat()))
    picked = parse_int(request.args.get("mood"), 1, 5)
    if picked is None and row is not None:
        picked = row.mood
    history = CheckIn.query.filter_by(user_id=current_user.id).order_by(CheckIn.date.desc()).all()
    return render_template(
        "checkin.html",
        row=row,
        emotions=EMOTIONS,
        influences=INFLUENCES,
        selected_mood=picked,
        entry_date=day,
        today=date.today(),
        history=history,
    )


@bp.post("/checkin/<int:entry_id>/delete")
@login_required
@consent_required("mental_health")
def delete_checkin(entry_id: int):
    row = _owned(CheckIn, entry_id)
    audit(current_user.id, "checkin_delete", row.date.isoformat())
    db.session.delete(row)
    db.session.commit()
    flash(t("flash_deleted"))
    return redirect(url_for("wellness.checkin"))


@bp.route("/sleep", methods=["GET", "POST"])
@login_required
@consent_required("mental_health")
def sleep():
    day = _chosen_day()
    if day is None:
        flash(t("error_range"))
        day = date.today()
    row = SleepLog.query.filter_by(user_id=current_user.id, date=day).one_or_none()
    if request.method == "POST":
        hours = parse_float(request.form.get("hours"), 0, 16)
        quality = parse_int(request.form.get("quality"), 1, 5)
        if hours is None or quality is None:
            flash(t("error_range"))
        else:
            if row is None:
                row = SleepLog(user_id=current_user.id, date=day, hours=hours, quality=quality)
                db.session.add(row)
            row.hours = hours
            row.quality = quality
            audit(current_user.id, "sleep", day.isoformat())
            db.session.commit()
            flash(t("flash_sleep"))
            return redirect(url_for("wellness.sleep", date=day.isoformat()))
    history = SleepLog.query.filter_by(user_id=current_user.id).order_by(SleepLog.date.desc()).all()
    return render_template("sleep.html", row=row, entry_date=day, today=date.today(), history=history)


@bp.post("/sleep/<int:entry_id>/delete")
@login_required
@consent_required("mental_health")
def delete_sleep(entry_id: int):
    row = _owned(SleepLog, entry_id)
    audit(current_user.id, "sleep_delete", row.date.isoformat())
    db.session.delete(row)
    db.session.commit()
    flash(t("flash_deleted"))
    return redirect(url_for("wellness.sleep"))


@bp.route("/stress", methods=["GET", "POST"])
@login_required
@consent_required("mental_health")
def stress():
    day = _chosen_day()
    if day is None:
        flash(t("error_range"))
        day = date.today()
    row = StressLog.query.filter_by(user_id=current_user.id, date=day).one_or_none()
    if request.method == "POST":
        level = parse_int(request.form.get("stress"), 1, 5)
        tags = [name for name in STRESS_TAGS if request.form.get(f"tag_{name}")]
        if level is None:
            flash(t("error_range"))
        else:
            if row is None:
                row = StressLog(user_id=current_user.id, date=day, stress=level, tags="[]")
                db.session.add(row)
            row.stress = level
            row.tags = json.dumps(tags)
            audit(current_user.id, "stress", day.isoformat())
            db.session.commit()
            flash(t("flash_stress"))
            return redirect(url_for("wellness.stress", date=day.isoformat()))
    history = StressLog.query.filter_by(user_id=current_user.id).order_by(StressLog.date.desc()).all()
    return render_template("stress.html", row=row, tags=STRESS_TAGS, entry_date=day, today=date.today(), history=history)


@bp.post("/stress/<int:entry_id>/delete")
@login_required
@consent_required("mental_health")
def delete_stress(entry_id: int):
    row = _owned(StressLog, entry_id)
    audit(current_user.id, "stress_delete", row.date.isoformat())
    db.session.delete(row)
    db.session.commit()
    flash(t("flash_deleted"))
    return redirect(url_for("wellness.stress"))


@bp.route("/cycle", methods=["GET", "POST"])
@login_required
@consent_required("reproductive")
def cycle():
    day = _chosen_day()
    if day is None:
        flash(t("error_range"))
        day = date.today()
    row = CycleLog.query.filter_by(user_id=current_user.id, date=day).one_or_none()
    if request.method == "POST":
        cycle_day = parse_int(request.form.get("cycle_day"), 1, 60)
        note = (request.form.get("note") or "").strip()
        if cycle_day is None or len(note) > 2000:
            flash(t("error_range"))
        else:
            if row is None:
                row = CycleLog(user_id=current_user.id, date=day, cycle_day=cycle_day)
                db.session.add(row)
            row.cycle_day = cycle_day
            row.note_enc = encrypt(note) if note else None
            audit(current_user.id, "cycle", day.isoformat())
            db.session.commit()
            flash(t("flash_cycle"))
            return redirect(url_for("wellness.cycle", date=day.isoformat()))
    history = CycleLog.query.filter_by(user_id=current_user.id).order_by(CycleLog.date.desc()).all()
    return render_template("cycle.html", row=row, entry_date=day, today=date.today(), history=history)


@bp.post("/cycle/<int:entry_id>/delete")
@login_required
@consent_required("reproductive")
def delete_cycle(entry_id: int):
    row = _owned(CycleLog, entry_id)
    audit(current_user.id, "cycle_delete", row.date.isoformat())
    db.session.delete(row)
    db.session.commit()
    flash(t("flash_deleted"))
    return redirect(url_for("wellness.cycle"))


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    client = current_app_ai()
    if request.method == "POST":
        language = request.form.get("language")
        if language in LANGUAGES:
            current_user.language = language
            audit(current_user.id, "language", language)
            db.session.commit()
            flash(t("language_saved"))
            return redirect(url_for("wellness.settings"))
    ollama = client.ollama_status()
    status = {
        "groq": bool(client.groq_key),
        "ollama": ollama,
        "chat_model": client.chat_model,
        "fast_model": client.fast_model,
        "ollama_model": client.ollama_chat_model,
        "stt_model": client.stt_model,
        "guard": bool(client.guard_configured),
        "last_error": client.last_error,
    }
    return render_template("settings.html", status=status, languages=LANGUAGES)


@bp.post("/export")
@login_required
def export():
    payload = export_payload(current_user)
    audit(current_user.id, "export", "json")
    db.session.commit()
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    response = make_response(raw)
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=mindwell-export.json"
    return response


@bp.post("/delete-account")
@login_required
def remove_account():
    if request.form.get("confirm") != "DELETE":
        flash(t("confirm_delete_mismatch"))
        return redirect(url_for("wellness.settings"))
    user_id = current_user.id
    logout_user()
    user = db.session.get(User, user_id)
    if user is not None:
        delete_account(user)
    return redirect(url_for("auth.login"))


def _chosen_day():
    raw = (request.form.get("date") if request.method == "POST" else request.args.get("date")) or ""
    raw = raw.strip()
    if not raw:
        return date.today()
    try:
        day = date.fromisoformat(raw)
    except ValueError:
        return None
    if day > date.today() or day < date.today() - timedelta(days=400):
        return None
    return day


def _owned(model, entry_id: int):
    row = db.session.get(model, entry_id)
    if row is None or row.user_id != current_user.id:
        abort(404)
    return row


def current_app_ai():
    from flask import current_app

    return current_app.extensions["ai"]
