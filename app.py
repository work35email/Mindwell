"""MindWell application factory."""

from __future__ import annotations

import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from sqlalchemy.pool import StaticPool

from extensions import csrf, db, login_manager

load_dotenv()


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    database = Path(app.instance_path) / "mindwell.db"
    app.config.from_mapping(
        SECRET_KEY="dev",
        SQLALCHEMY_DATABASE_URI="sqlite:///" + database.as_posix(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE") == "1",
        WTF_CSRF_SSL_STRICT=False,
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        JSON_AS_ASCII=False,
    )
    if test_config:
        app.config.update(test_config)
    else:
        app.config["SECRET_KEY"] = _secret(app.instance_path)

    if ":memory:" in app.config["SQLALCHEMY_DATABASE_URI"]:
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        }

    from services.crypto import init_crypto

    init_crypto(os.getenv("FIELD_ENCRYPTION_KEY"), None if test_config else app.instance_path)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from models import User
    from services.ai_client import AIClient
    from services.i18n import current_language, t

    app.extensions["ai"] = AIClient()

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify({"error": "auth_required"}), 401
        return redirect(url_for("auth.login", next=request.path))

    from routes.auth import bp as auth_bp
    from routes.companion import bp as companion_bp
    from routes.explore import bp as explore_bp
    from routes.journal import bp as journal_bp
    from routes.wellness import bp as wellness_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(wellness_bp)
    app.register_blueprint(companion_bp)
    app.register_blueprint(journal_bp)
    app.register_blueprint(explore_bp)

    @app.context_processor
    def inject():
        from models import EMOTION_EMOJI, MOOD_SCALE
        from services.icons import icon

        return {"t": t, "lang": current_language(), "mood_scale": MOOD_SCALE, "icon": icon, "emotion_emoji": EMOTION_EMOJI}

    @app.template_filter("short_dt")
    def short_dt(value):
        if not value:
            return ""
        return value.strftime("%d %b %H:%M")

    @app.after_request
    def hardening(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if not request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    @app.errorhandler(404)
    def missing(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not_found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "forbidden"}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def crashed(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "server"}), 500
        return render_template("errors/500.html"), 500

    @app.cli.command("seed-demo")
    def seed_demo_command():
        from services.seed import seed_demo

        seed_demo()

    with app.app_context():
        db.create_all()
        _ensure_cycle_note()
        _ensure_checkin_fields()
    return app


def _ensure_cycle_note() -> None:
    """Add the optional cycle note column on databases created before it existed."""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "cycle_log" not in inspector.get_table_names():
        return
    names = {column["name"] for column in inspector.get_columns("cycle_log")}
    if "note" in names:
        return
    db.session.execute(text("ALTER TABLE cycle_log ADD COLUMN note TEXT"))
    db.session.commit()


def _ensure_checkin_fields() -> None:
    """Store the mood emoji and optional influences on databases created earlier."""
    from sqlalchemy import inspect, or_, text

    from models import MOOD_EMOJI, CheckIn

    inspector = inspect(db.engine)
    if "checkin" not in inspector.get_table_names():
        return
    names = {column["name"] for column in inspector.get_columns("checkin")}
    if "mood_emoji" not in names:
        db.session.execute(text("ALTER TABLE checkin ADD COLUMN mood_emoji VARCHAR(16)"))
    if "influences" not in names:
        db.session.execute(text("ALTER TABLE checkin ADD COLUMN influences TEXT"))
    db.session.commit()
    pending = CheckIn.query.filter(or_(CheckIn.mood_emoji.is_(None), CheckIn.mood_emoji == "")).all()
    for row in pending:
        row.mood_emoji = MOOD_EMOJI.get(row.mood, "")
    if pending:
        db.session.commit()


def _secret(instance_path: str) -> str:
    configured = (os.getenv("SECRET_KEY") or "").strip()
    if configured:
        return configured
    path = Path(instance_path) / "secret.key"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    path.write_text(secrets.token_hex(32), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()
