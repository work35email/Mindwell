import os

import pytest
from cryptography.fernet import Fernet

os.environ["FIELD_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["SECRET_KEY"] = "test-secret-key-mindwell"
os.environ["GROQ_API_KEY"] = ""
os.environ["GROQ_GUARD_MODEL"] = ""
os.environ["OLLAMA_GUARD_MODEL"] = ""

from app import create_app
from extensions import db
from models import CONSENT_TYPES
from services.ai_client import AIResult, AIUnavailable


class FakeAI:
    def __init__(self, reply="Try a four-count breath and one short walk.", fail=False, topics=None):
        self.reply = reply
        self.fail = fail
        self.topics = topics if topics is not None else ["stress"]
        self.chat_calls = 0
        self.json_calls = 0
        self.guard_configured = False
        self.guard_level = None

    def chat(self, messages, **kwargs):
        self.chat_calls += 1
        if self.fail:
            raise AIUnavailable("down")
        return AIResult(self.reply, "groq")

    def fast_json(self, system, user, **kwargs):
        self.json_calls += 1
        return {"topics": list(self.topics)}

    def guard(self, text):
        return self.guard_level

    def transcribe(self, audio, filename, language):
        return AIResult("synthetic transcript", "groq")


@pytest.fixture
def app():
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key-mindwell",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        }
    )
    application.extensions["ai"] = FakeAI()
    yield application
    with application.app_context():
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, email="a@example.com", password="password123", language="en", consents=True):
    response = client.post(
        "/register",
        data={"email": email, "password": password, "confirm": password, "language": language},
        follow_redirects=False,
    )
    assert response.status_code in {302, 303}
    if consents:
        client.post("/consent", data={name: "on" for name in CONSENT_TYPES})
    return response
