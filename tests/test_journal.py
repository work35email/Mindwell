import io

from models import Journal
from tests.conftest import register


def test_transcribe_does_not_store_audio_or_a_journal(client, app):
    register(client)
    response = client.post(
        "/api/transcribe",
        data={"audio": (io.BytesIO(b"not-really-audio"), "clip.webm"), "language": "ta"},
    )
    assert response.status_code == 200
    assert response.get_json()["text"] == "synthetic transcript"
    with app.app_context():
        assert Journal.query.count() == 0


def test_journal_save_and_voice_consent(client, app):
    register(client, consents=False)
    client.post("/consent", data={"mental_health": "on"})
    blocked = client.post("/api/transcribe", data={"audio": (io.BytesIO(b"abc"), "clip.webm")})
    assert blocked.status_code == 403
    saved = client.post("/journal/new", data={"body": "typed line", "language": "en", "source": "text"})
    assert saved.status_code in {302, 303}
    with app.app_context():
        row = Journal.query.one()
        assert row.body_text() == "typed line"
        assert "typed line" not in (row.body_enc or "")
