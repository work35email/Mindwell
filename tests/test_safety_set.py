import json
from pathlib import Path

from models import User
from services.companion import run_companion
from services.safety import screen_input
from tests.conftest import FakeAI, register

CASES = json.loads(Path("eval/safety_prompts.json").read_text(encoding="utf-8"))


def test_prompt_set_is_large_and_rules_match():
    assert len(CASES) >= 150
    languages = {row["lang"] for row in CASES}
    assert languages == {"en", "si", "ta"}
    missed = []
    for row in CASES:
        got = screen_input(row["text"])
        if got != row["expected"]:
            missed.append((row["text"], row["expected"], got))
    assert missed == []


def test_unsafe_prompts_never_call_chat(client, app):
    register(client)
    fake = FakeAI()
    unsafe = [row for row in CASES if row["expected"] != "normal"]
    assert len(unsafe) >= 100
    with app.app_context():
        user = User.query.one()
        for row in unsafe:
            run_companion(user, row["text"], fake)
        assert fake.chat_calls == 0
        assert fake.json_calls == 0
