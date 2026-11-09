"""Registration, login, and consents."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import CONSENT_TYPES, LANGUAGES, User
from services.account import audit, granted_types, set_consent
from services.i18n import t

from .helpers import safe_next, valid_email

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("wellness.home"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        language = request.form.get("language") if request.form.get("language") in LANGUAGES else "en"
        if not valid_email(email):
            flash(t("invalid_email"))
        elif len(password) < 8:
            flash(t("password_short"))
        elif password != confirm:
            flash(t("password_mismatch"))
        elif User.query.filter_by(email=email).one_or_none():
            flash(t("register_exists"))
        else:
            user = User(email=email, language=language)
            user.set_password(password)
            db.session.add(user)
            try:
                db.session.flush()
                audit(user.id, "register", language)
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash(t("register_exists"))
            else:
                login_user(user)
                return redirect(url_for("auth.consent"))
    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(safe_next(request.args.get("next")))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).one_or_none()
        if user is None or not user.check_password(password):
            flash(t("login_failed"))
        else:
            login_user(user)
            audit(user.id, "login", "")
            db.session.commit()
            return redirect(safe_next(request.args.get("next") or request.form.get("next")))
    return render_template("auth/login.html", next_url=request.args.get("next") or "")


@bp.post("/logout")
@login_required
def logout():
    audit(current_user.id, "logout", "")
    db.session.commit()
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/consent", methods=["GET", "POST"])
@login_required
def consent():
    if request.method == "POST":
        for name in CONSENT_TYPES:
            set_consent(current_user, name, request.form.get(name) == "on")
        db.session.commit()
        flash(t("consent_saved"))
        return redirect(url_for("wellness.home"))
    return render_template("auth/consent.html", granted=granted_types(current_user), types=CONSENT_TYPES)
