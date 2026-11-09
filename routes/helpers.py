"""Shared route helpers."""

from __future__ import annotations

import re
from functools import wraps

from flask import current_app, flash, jsonify, redirect, request, url_for
from flask_login import current_user

from services.account import missing_consents
from services.i18n import t
from services.ratelimit import allow

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def ai_client():
    return current_app.extensions["ai"]


def consent_required(*types: str):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            missing = missing_consents(current_user, types)
            if missing:
                if request.path.startswith("/api/") or request.is_json:
                    return jsonify({"error": "consent_required", "missing": missing}), 403
                flash(t("consent_needed"))
                return redirect(url_for("auth.consent"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def limited(user_id: int):
    return allow(f"ai:{user_id}")


def valid_email(value: str) -> bool:
    return bool(_EMAIL.match((value or "").strip().lower()))


def parse_int(raw, low: int, high: int) -> int | None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value < low or value > high:
        return None
    return value


def parse_float(raw, low: float, high: float) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < low or value > high:
        return None
    return round(value, 1)


def safe_next(target: str | None) -> str:
    if target and target.startswith("/") and not target.startswith("//") and not target.startswith("/\\"):
        return target
    return url_for("wellness.home")
