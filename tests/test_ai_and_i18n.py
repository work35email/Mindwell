import requests

from services.ai_client import AIClient, AIUnavailable, TranscriptionUnavailable, parse_llama_guard
from services.i18n import STRINGS, _ROWS


class _Response:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_i18n_catalogs_match():
    assert len(_ROWS) == len(STRINGS["en"])
    assert set(STRINGS["si"]) == set(STRINGS["en"])
    assert set(STRINGS["ta"]) == set(STRINGS["en"])
    import re

    for key, text in STRINGS["en"].items():
        fields = set(re.findall(r"{(\w+)}", text))
        assert fields == set(re.findall(r"{(\w+)}", STRINGS["si"][key]))
        assert fields == set(re.findall(r"{(\w+)}", STRINGS["ta"][key]))


def test_ollama_is_used_when_groq_fails(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_CHAT_MODEL", "llama3.1:8b")
    client = AIClient()
    seen = []

    def fake_post(url, **kwargs):
        seen.append(url)
        if "api.groq.com" in url:
            return _Response(503, text="unavailable")
        return _Response(200, {"choices": [{"message": {"content": "local grounding step"}}]})

    monkeypatch.setattr(requests, "post", fake_post)
    result = client.chat([{"role": "user", "content": "hello"}])
    assert result.provider == "ollama"
    assert result.text == "local grounding step"
    assert any("api.groq.com" in url for url in seen)
    assert any("11434" in url for url in seen)


def test_no_groq_key_skips_cloud(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    client = AIClient()
    seen = []

    def fake_post(url, **kwargs):
        seen.append(url)
        return _Response(200, {"choices": [{"message": {"content": '{"topics": ["sleep"]}'}}]})

    monkeypatch.setattr(requests, "post", fake_post)
    result = client.chat([{"role": "user", "content": "sleep"}])
    assert result.provider == "ollama"
    assert all("groq.com" not in url for url in seen)


def test_both_providers_down(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    client = AIClient()

    def fake_post(url, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "post", fake_post)
    try:
        client.chat([{"role": "user", "content": "hello"}])
        raised = False
    except AIUnavailable:
        raised = True
    assert raised


def test_transcription_does_not_fall_back_to_ollama(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    client = AIClient()
    called = {"n": 0}

    def fake_post(url, **kwargs):
        called["n"] += 1
        return _Response(200, {"text": "nope"})

    monkeypatch.setattr(requests, "post", fake_post)
    try:
        client.transcribe(b"abc", "clip.webm", "si")
        raised = False
    except TranscriptionUnavailable:
        raised = True
    assert raised
    assert called["n"] == 0


def test_llama_guard_parser_again():
    assert parse_llama_guard("unsafe\nS11") == "crisis"
