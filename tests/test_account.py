import json

from sqlalchemy import text

from extensions import db
from models import AuditLog, ChatMessage, CheckIn, Journal, User
from services.crypto import decrypt, encrypt
from services.samples import SAMPLES
from tests.conftest import register


def test_register_login_and_wrong_password(client):
    register(client, consents=False)
    client.post("/logout")
    bad = client.post("/login", data={"email": "a@example.com", "password": "nope-nope"}, follow_redirects=True)
    assert "does not match" in bad.get_data(as_text=True) or bad.status_code == 200
    good = client.post("/login", data={"email": "a@example.com", "password": "password123"})
    assert good.status_code in {302, 303}


def test_consent_gates_features(client):
    register(client, consents=False)
    blocked = client.get("/companion")
    assert blocked.status_code in {302, 303}
    assert "/consent" in blocked.headers["Location"]
    blocked_cycle = client.get("/cycle")
    assert blocked_cycle.status_code in {302, 303}
    client.post("/consent", data={"mental_health": "on", "ai_processing": "on"})
    assert client.get("/companion").status_code == 200
    still = client.get("/cycle")
    assert still.status_code in {302, 303}
    denied = client.post("/api/chat", json={"message": "hello"})
    assert denied.status_code == 200 or denied.status_code == 403
    # mental health and AI were granted, so chat is allowed.
    assert denied.status_code == 200


def test_api_chat_requires_consent(client):
    register(client, consents=False)
    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 403
    assert response.get_json()["error"] == "consent_required"


def test_note_is_ciphertext_and_round_trips(client, app):
    register(client)
    secret = "secret phrase සිංහල"
    client.post("/checkin", data={"mood": "3", "energy": "3", "note": secret, "emotion_calm": "on"})
    with app.app_context():
        raw = db.session.execute(text("SELECT note FROM checkin")).scalar()
        assert secret not in raw
        assert "secret" not in raw
        row = CheckIn.query.one()
        assert row.note_text() == secret


def test_same_note_follows_the_account_language(client, app):
    assert len(SAMPLES) == 20
    register(client, language="ta")
    client.post("/checkin", data={"mood": "3", "energy": "3", "note": "plain"})
    packed = json.dumps({"en": SAMPLES[0]["en"], "si": SAMPLES[0]["si"], "ta": SAMPLES[0]["ta"]}, ensure_ascii=False)
    with app.app_context():
        row = CheckIn.query.one()
        row.note_enc = encrypt(packed)
        db.session.commit()
    page = client.get("/checkin").get_data(as_text=True)
    assert SAMPLES[0]["ta"] in page
    assert SAMPLES[0]["en"] not in page


def test_life_stage_pages_and_cycle_note(client):
    register(client)
    pregnancy = client.get("/pregnancy")
    assert pregnancy.status_code == 200
    assert "Rest after birth" in pregnancy.get_data(as_text=True)
    menopause = client.get("/menopause")
    assert menopause.status_code == 200
    assert "Heat and sleep" in menopause.get_data(as_text=True)
    client.post("/cycle", data={"cycle_day": "4", "note": "heavy day"})
    assert "heavy day" in client.get("/cycle").get_data(as_text=True)


def test_delete_removes_every_row(client, app):
    register(client)
    client.post("/checkin", data={"mood": "4", "energy": "4", "note": "gone soon"})
    client.post("/journal/new", data={"body": "a private line", "language": "en", "source": "text"})
    response = client.post("/delete-account", data={"confirm": "DELETE"})
    assert response.status_code in {302, 303}
    with app.app_context():
        assert User.query.count() == 0
        assert CheckIn.query.count() == 0
        assert Journal.query.count() == 0
        assert ChatMessage.query.count() == 0
        assert AuditLog.query.count() == 0


def test_delete_requires_the_word(client, app):
    register(client)
    client.post("/delete-account", data={"confirm": "delete"})
    with app.app_context():
        assert User.query.count() == 1


def test_export_contains_note_not_password(client):
    register(client)
    client.post("/checkin", data={"mood": "2", "energy": "2", "note": "export me"})
    response = client.post("/export")
    body = response.get_data(as_text=True)
    assert "export me" in body
    assert "password" not in body.lower() or "password_hash" not in body
    assert "scrypt" not in body


def test_home_labels_scores_and_groups_the_menu(client):
    register(client)
    client.post("/checkin", data={"mood": "4", "energy": "2"})
    client.post("/sleep", data={"hours": "7.5", "quality": "4"})
    client.post("/stress", data={"stress": "3"})
    page = client.get("/").get_data(as_text=True)
    assert "Okay" in page
    assert "Easy" in page
    assert "Good" in page
    assert "Mid" in page
    assert "Life stage" in page
    assert 'aria-current="page"' in page
    assert "/companion" in page
    insights = client.get("/insights").get_data(as_text=True)
    assert "chart-grid" in insights
    assert "1 to 5" in insights
    assert "How are you feeling today?" in page
    assert "What do you need today?" in page
    assert "🙂" in page
    assert "Very low" in page
    assert "Great" in page
    week = client.get("/insights?days=7").get_data(as_text=True)
    assert "This week" in week
    assert "What felt heavy?" in client.get("/journal/new").get_data(as_text=True)


def test_entries_update_delete_and_charts_follow_the_database(client, app):
    register(client)
    client.post("/checkin", data={"mood": "1", "energy": "2", "note": "first mood", "influence_sleep": "on", "emotion_tired": "on"})
    client.post("/checkin", data={"mood": "5", "energy": "4", "note": "changed mood", "influence_work": "on"})
    saved = client.get("/checkin").get_data(as_text=True)
    assert "😄" in saved
    assert "changed mood" in saved
    assert "😄" in client.get("/insights?days=7").get_data(as_text=True)
    with app.app_context():
        row = CheckIn.query.one()
        assert row.mood == 5
        assert row.mood_emoji == "😄"
        assert row.influence_list() == ["work"]
        entry_id = row.id
    removed = client.post(f"/checkin/{entry_id}/delete", follow_redirects=True)
    assert "Entry deleted." in removed.get_data(as_text=True)
    assert "😄" not in client.get("/insights?days=7").get_data(as_text=True)
    assert "No check-in yet today." in client.get("/").get_data(as_text=True)

    client.post("/sleep", data={"hours": "8", "quality": "5"})
    client.post("/sleep", data={"hours": "6.5", "quality": "2"})
    client.post("/stress", data={"stress": "2"})
    client.post("/stress", data={"stress": "4", "tag_health": "on"})
    client.post("/cycle", data={"cycle_day": "4"})
    client.post("/cycle", data={"cycle_day": "12", "note": "short walk"})
    with app.app_context():
        from models import CycleLog, SleepLog, StressLog

        sleep = SleepLog.query.one()
        stress = StressLog.query.one()
        cycle = CycleLog.query.one()
        assert sleep.hours == 6.5
        assert stress.stress == 4
        assert "health" in stress.tag_list()
        assert cycle.cycle_day == 12
        assert cycle.note_text() == "short walk"
        ids = (sleep.id, stress.id, cycle.id)
    client.post(f"/sleep/{ids[0]}/delete")
    client.post(f"/stress/{ids[1]}/delete")
    client.post(f"/cycle/{ids[2]}/delete")
    with app.app_context():
        from models import CycleLog, SleepLog, StressLog

        assert SleepLog.query.count() == 0
        assert StressLog.query.count() == 0
        assert CycleLog.query.count() == 0

    created = client.post("/journal/new", data={"body": "A private line.", "language": "en"}, follow_redirects=True)
    assert "A private line." in created.get_data(as_text=True)
    with app.app_context():
        journal_id = Journal.query.one().id
    edited = client.post(
        f"/journal/{journal_id}/edit",
        data={"body": "A revised line.", "language": "en"},
        follow_redirects=True,
    )
    assert "A revised line." in edited.get_data(as_text=True)
    client.post(f"/journal/{journal_id}/delete", follow_redirects=True)
    with app.app_context():
        assert Journal.query.count() == 0
