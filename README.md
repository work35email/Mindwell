# MindWell

A local Flask demo of a women's wellness companion. It tracks mood, sleep, stress, and an optional cycle day, keeps an encrypted journal, and answers with a guardrailed companion. It does not diagnose, prescribe, or infer a psychiatric condition.

Groq is the first text and speech provider. If Groq is missing, rate-limited, or returns an error, chat, summaries, topic tags, library rewrites, and the optional safety model fall back to **Ollama on this computer**. Voice transcription stays on Groq. Audio is not saved and is not sent to Ollama.

Use synthetic or practice data. Helplines in `resources/support_resources.json` are **UNVERIFIED**. Library cards and Sinhala/Tamil wording are drafts.

## Setup (Windows)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put the printed value in `.env` as `FIELD_ENCRYPTION_KEY`. Add `GROQ_API_KEY` from [console.groq.com/keys](https://console.groq.com/keys) if you want cloud replies and voice transcription. Without that key, text uses Ollama only.

```powershell
ollama pull llama3.2
flask --app app seed-demo
flask --app app run --debug
```

Demo account: `demo@mindwell.local` / `mindwell-demo` (Sinhala UI, 60 synthetic days).

If `.env` has no encryption key, the first launch stores one in `instance/field.key`.

## Models

As of November 2026, Groq has retired `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, and `meta-llama/llama-guard-4-12b` on the free tier. Defaults are `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, and `whisper-large-v3`. Override them in `.env` if your account offers different IDs.

Leave `GROQ_GUARD_MODEL` empty to screen with rules only. Set it (or `OLLAMA_GUARD_MODEL`, for example `llama-guard3:8b`) for a second opinion. Rules still run first, and a guard failure does not unblock a reply.

## Tests

```powershell
pytest
```

The safety file `eval/safety_prompts.json` has 150+ prompts in English, Sinhala, and Tamil. Crisis, abuse, medical, and boundary prompts must not call the chat model.

## Privacy

Check-in notes, journal text, summaries, and chat are Fernet-encrypted in SQLite. The companion sends the current message, up to eight recent ordinary turns, and short library notes. It does not send email or raw cycle rows. AI processing consent says Groq receives the text or voice clip, and that a Groq failure sends the same text to local Ollama.
