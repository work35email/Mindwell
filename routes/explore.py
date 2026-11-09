"""Library, insights, care plan, support, fictional directory, and report."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from markupsafe import Markup

from extensions import db
from models import MOOD_EMOJI, CheckIn, CycleLog, Journal, SleepLog, StressLog
from services.account import audit, granted_types
from services.companion import explain_card
from services.i18n import t
from services.rag import TAGS, card_by_id, filter_cards, localized, retrieve
from services.resources import localized_name, professionals_data, resources, support_data, unverified
from services.stats import average, care_signals, correlation_phrase, paired, spearman, svg_line

from .helpers import ai_client, consent_required, limited, parse_int

bp = Blueprint("explore", __name__)


@bp.get("/library")
@login_required
def library():
    topic = request.args.get("topic") or ""
    audience = request.args.get("audience") or ""
    if topic not in TAGS:
        topic = ""
    if audience not in {"general", "pregnancy", "menopause"}:
        audience = ""
    cards = []
    for card in filter_cards(topic or None, audience or None):
        title, body = localized(card, current_user.language)
        cards.append({"id": card["id"], "title": title, "preview": body[:160], "minutes": card.get("minutes"), "topics": card.get("topics") or []})
    return render_template("library/list.html", cards=cards, topic=topic, audience=audience, tags=TAGS)


@bp.route("/library/<card_id>", methods=["GET", "POST"])
@login_required
def library_card(card_id: str):
    card = card_by_id(card_id)
    if card is None:
        abort(404)
    title, body = localized(card, current_user.language)
    explanation = None
    provider = None
    if request.method == "POST":
        if "ai_processing" not in granted_types(current_user):
            flash(t("consent_needed"))
            return redirect(url_for("auth.consent"))
        if not limited(current_user.id):
            flash(t("rate_limited"))
        else:
            result = explain_card(current_user, card, ai_client())
            explanation = result["explanation"]
            provider = result["provider"]
    return render_template(
        "library/detail.html",
        card=card,
        title=title,
        body=body,
        explanation=explanation,
        provider=provider,
    )


@bp.post("/api/explain")
@login_required
@consent_required("ai_processing")
def api_explain():
    if not limited(current_user.id):
        return jsonify({"error": "rate_limited"}), 429
    card_id = str((request.get_json(silent=True) or {}).get("id") or "")
    card = card_by_id(card_id)
    if card is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify(explain_card(current_user, card, ai_client()))


@bp.get("/insights")
@login_required
@consent_required("mental_health")
def insights():
    chosen = parse_int(request.args.get("days"), 7, 90)
    days = chosen if chosen in (7, 30, 90) else 30
    end = date.today()
    start = end - timedelta(days=days - 1)
    moods, sleeps, stresses, cycles = _series(current_user.id, start, end)
    reproductive = "reproductive" in granted_types(current_user)
    charts = {
        "mood": _chart(moods, t("chart_mood"), 1, 5, "#9b2458", faces=True),
        "sleep": _chart(sleeps, t("chart_sleep"), 0, 12, "#c45b7a"),
        "stress": _chart(stresses, t("chart_stress"), 1, 5, "#7a1848"),
    }
    if reproductive:
        charts["cycle"] = _chart(cycles, t("chart_cycle"), 1, 35, "#d48aa3")
    corrs = [
        {"title": t("sleep_mood_title"), "key": _corr_key("sleep", sleeps, moods)},
        {"title": t("stress_mood_title"), "key": _corr_key("stress", stresses, moods)},
    ]
    if reproductive:
        corrs.append({"title": t("cycle_mood_title"), "key": _corr_key("cycle", cycles, moods)})
    return render_template("insights.html", days=days, charts=charts, correlations=corrs)


@bp.get("/plan")
@login_required
@consent_required("mental_health")
def plan():
    end = date.today()
    start = end - timedelta(days=13)
    moods, sleeps, stresses, cycles = _series(current_user.id, start, end)
    if "reproductive" not in granted_types(current_user):
        cycles = {}
    tags = []
    for row in StressLog.query.filter(StressLog.user_id == current_user.id, StressLog.date >= start).all():
        tags.extend(row.tag_list())
    signals = care_signals(moods, sleeps, stresses, cycles, tags, today=end)
    cards = []
    for card in retrieve(signals["topics"]):
        title, _body = localized(card, current_user.language)
        cards.append({"id": card["id"], "title": title, "minutes": card.get("minutes")})
    return render_template("plan.html", signals=signals, cards=cards)


@bp.get("/pregnancy")
@login_required
def pregnancy():
    return _stage("pregnancy")


@bp.get("/menopause")
@login_required
def menopause():
    return _stage("menopause")


def _stage(audience: str):
    cards = []
    for card in filter_cards(None, audience):
        title, body = localized(card, current_user.language)
        cards.append({"id": card["id"], "title": title, "preview": body[:180], "minutes": card.get("minutes")})
    return render_template("stage.html", audience=audience, cards=cards)


@bp.get("/support")
def support():
    language = current_user.language if current_user.is_authenticated else "en"
    rows = []
    for row in resources():
        rows.append(
            {
                "phone": row.get("phone"),
                "name": localized_name(row, language),
                "hours": localized_name(row, language, "hours"),
                "source_url": row.get("source_url"),
                "source_note": row.get("source_note"),
                "kind": row.get("kind"),
            }
        )
    return render_template("support.html", rows=rows, meta=support_data(), unverified=unverified())


@bp.get("/connect")
@login_required
def connect():
    data = professionals_data()
    people = []
    for person in data.get("people") or []:
        people.append(
            {
                "name": person.get("name"),
                "phone": person.get("phone"),
                "role": localized_name(person, current_user.language, "role"),
                "city": localized_name(person, current_user.language, "city"),
                "focus": localized_name(person, current_user.language, "focus"),
            }
        )
    return render_template("connect.html", people=people, disclaimer=data.get("disclaimer"))


@bp.get("/report")
@login_required
@consent_required("report_sharing")
def report():
    end = date.today()
    start = end - timedelta(days=29)
    moods, sleeps, stresses, _cycles = _series(current_user.id, start, end)
    include = request.args.get("include") == "notes"
    notes = []
    if include:
        rows = (
            Journal.query.filter(Journal.user_id == current_user.id, Journal.created_at >= datetime.combine(start, datetime.min.time()))
            .order_by(Journal.created_at.desc())
            .limit(5)
            .all()
        )
        notes = [{"created_at": row.created_at, "summary": row.summary_text() or row.body_text()[:400]} for row in rows]
    audit(current_user.id, "report", "notes" if include else "aggregates")
    db.session.commit()
    data = professionals_data()
    people = [
        {
            "name": person.get("name"),
            "role": localized_name(person, current_user.language, "role"),
            "city": localized_name(person, current_user.language, "city"),
        }
        for person in data.get("people") or []
    ]
    return render_template(
        "report.html",
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        avg_mood=_round(average(list(moods.values()))),
        avg_sleep=_round(average(list(sleeps.values()))),
        avg_stress=_round(average(list(stresses.values()))),
        notes=notes,
        include=include,
        people=people,
    )


def _series(user_id: int, start: date, end: date):
    moods = {
        row.date: float(row.mood)
        for row in CheckIn.query.filter(CheckIn.user_id == user_id, CheckIn.date >= start, CheckIn.date <= end)
    }
    sleeps = {
        row.date: float(row.hours)
        for row in SleepLog.query.filter(SleepLog.user_id == user_id, SleepLog.date >= start, SleepLog.date <= end)
    }
    stresses = {
        row.date: float(row.stress)
        for row in StressLog.query.filter(StressLog.user_id == user_id, StressLog.date >= start, StressLog.date <= end)
    }
    cycles = {
        row.date: float(row.cycle_day)
        for row in CycleLog.query.filter(CycleLog.user_id == user_id, CycleLog.date >= start, CycleLog.date <= end)
    }
    return moods, sleeps, stresses, cycles


def _chart(series: dict, title: str, ymin: float, ymax: float, color: str, faces: bool = False):
    points = []
    for day, value in sorted(series.items()):
        label = day.strftime("%d %b")
        if faces:
            label = MOOD_EMOJI.get(int(round(value)), "") + " " + label
        points.append((label, value))
    if ymin == 1 and ymax == 5:
        scale = t("chart_scale_15")
    elif ymax == 12:
        scale = t("chart_scale_sleep")
    else:
        scale = t("chart_scale_cycle")
    return {
        "svg": Markup(svg_line(points, ymin=ymin, ymax=ymax, title=title, color=color)),
        "points": points,
        "title": title,
        "scale": scale,
    }


def _corr_key(prefix: str, left: dict, right: dict) -> str:
    xs, ys = paired(left, right)
    rho = spearman(xs, ys)
    kind = correlation_phrase(rho, len(xs))
    if kind == "sparse":
        return "corr_sparse"
    if kind == "none":
        return "corr_none"
    if kind == "positive":
        return f"corr_{prefix}_pos"
    return f"corr_{prefix}_neg"


def _round(value):
    if value is None:
        return None
    return round(value, 2)
