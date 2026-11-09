# MindWell

MindWell is a local women's wellness companion. It records mood, sleep, stress, and an optional cycle day, keeps an encrypted journal, and replies through a guardrailed chat. The interface is available in English, Sinhala, and Tamil.

It does not diagnose, prescribe, or infer a psychiatric condition. It is a laptop demo for synthetic or practice data, not a clinical service and not a crisis line.

> **Not medical advice.** MindWell is not a doctor, therapist, or emergency service. If someone may be in danger, contact local emergency services. Helpline numbers in `resources/support_resources.json` are marked **UNVERIFIED** and must be checked by a person before anyone relies on them. Library cards and Sinhala/Tamil wording are drafts.

## Features

- **Daily logs.** Mood (with emoji), energy, emotions, influences, sleep hours and quality, stress level and tags, and an optional cycle day with a note.
- **Dashboard.** Today's entries, a check-in streak, and a 14-day mood chart.
- **Journal.** Typed entries, optional voice transcription, and a short reflection. Audio is held in memory for transcription and is not written to disk.
- **Companion.** Four modes — listen, reflect, relax, and guidance — with suggested prompts and related library cards. Crisis, abuse, medical, and boundary messages get a fixed reply and never reach the chat model.
- **Insights and care plan.** 7, 30, or 90 day charts, simple correlations, and a 14-day plan that points at library cards.
- **Library.** Fourteen self-care cards in three languages, filterable by topic and by life stage (general, pregnancy, menopause), with an optional plain-language rewrite.
- **Support and connect.** A public support page and a fictional professional directory. The directory is sample data, not a real referral list.
- **Shareable report.** A 30-day aggregate summary. Journal text is included only when the user asks for it and has granted report-sharing consent.
- **Account controls.** Separate consents, JSON export, account deletion, language switch, and a quick-exit link that leaves the page immediately.
- **Languages.** English, Sinhala, and Tamil. Notes stored in all three languages follow the account language on screen.

## Stack

| Piece | Choice |
| --- | --- |
| App | Flask 3, server-rendered Jinja templates |
| Data | SQLite through Flask-SQLAlchemy |
| Auth | Flask-Login, scrypt password hashes, CSRF via Flask-WTF |
| Secrets at rest | Fernet encryption for notes, journal text, summaries, and chat |
| Text models | Groq first, then local [Ollama](https://ollama.com) |
| Speech | Groq Whisper only. Audio is not sent to Ollama |

## Requirements

- Python 3.8 or newer
- A virtual environment tool (`venv` is enough)
- Optional: a [Groq API key](https://console.groq.com/keys) for cloud replies and voice transcription
- Optional: [Ollama](https://ollama.com) with a chat model such as `llama3.2` when Groq is missing or fails

Text features work with either provider. Voice transcription needs Groq.

## Getting started

Clone the repository, then from the project root:

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**macOS and Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put the printed value in `.env` as `FIELD_ENCRYPTION_KEY`. Add `GROQ_API_KEY` if you want cloud replies and voice transcription. Without that key, text uses Ollama only.

Pull a local model if you want the fallback (or the only text provider):

```bash
ollama pull llama3.2
```

Seed the demo account and start the server:

```bash
flask --app app seed-demo
flask --app app run --debug
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). A health check is available at `/health`.

If `.env` has no encryption key, the first launch stores one in `instance/field.key`. A missing `SECRET_KEY` is generated the same way into `instance/secret.key`. Keep both files, and `.env`, off git. They are listed in `.gitignore`.

### Demo account

| | |
| --- | --- |
| Email | `demo@mindwell.local` |
| Password | `mindwell-demo` |
| Language | English (switch to Sinhala or Tamil in Settings) |
| Data | 20 synthetic days of check-ins, sleep, stress, cycle notes, and journal entries |

The same diary lines are stored in English, Sinhala, and Tamil, so changing the account language shows the matching text. Running `seed-demo` again replaces that account's logs.

## Configuration

Copy `.env.example` to `.env`. Do not commit `.env`.

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Flask session secret. Generated into `instance/secret.key` when empty. |
| `FIELD_ENCRYPTION_KEY` | Fernet key for notes, journal text, summaries, and chat. |
| `GROQ_API_KEY` | Cloud text and Whisper. Empty means local Ollama for text, and no voice transcription. |
| `GROQ_CHAT_MODEL` | Main chat model. Default `openai/gpt-oss-120b`. |
| `GROQ_FAST_MODEL` | Short JSON tasks such as topic tags. Default `openai/gpt-oss-20b`. |
| `GROQ_STT_MODEL` | Speech-to-text. Default `whisper-large-v3`. |
| `GROQ_GUARD_MODEL` | Optional second safety opinion. Empty means rules only. |
| `OLLAMA_BASE_URL` | Local Ollama. Default `http://127.0.0.1:11434`. |
| `OLLAMA_CHAT_MODEL` | Fallback chat model. Default `llama3.2:latest`. |
| `OLLAMA_FAST_MODEL` | Fallback for short JSON tasks. |
| `OLLAMA_GUARD_MODEL` | Optional local guard, for example `llama-guard3:8b`. |
| `SESSION_COOKIE_SECURE` | Set to `1` only when the app is served over HTTPS. |

As of November 2026, Groq has retired `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, and `meta-llama/llama-guard-4-12b` on the free tier. Override the model IDs in `.env` if your account offers different ones.

Leave `GROQ_GUARD_MODEL` empty to screen with rules only. A model id containing `llama-guard` is parsed for safety codes. Any other id is asked for a JSON safety decision. Rules still run first, and a guard failure does not unblock a reply.

## How a companion turn works

1. Deterministic rules in `services/safety.py` label the message `normal`, `boundary`, `medical`, `abuse`, or `crisis`.
2. If the rules say `normal` and a guard model is configured, that model may only escalate the label. It cannot loosen a rule hit.
3. Anything other than `normal` gets a fixed, scripted reply. The chat model is not called.
4. A normal turn sends the current message, up to eight recent ordinary turns, and short library notes. It does not send the user's email or raw cycle rows.
5. The model reply is filtered again before it is shown. The companion is instructed to stay under 90 words, avoid diagnosis and medication, and reply in the account language.

AI routes are limited to 30 calls per user per 10 minutes, in memory. That limit suits a laptop demo.

Consents gate the sensitive areas:

| Consent | Unlocks |
| --- | --- |
| `mental_health` | Check-in, sleep, stress, journal, insights, care plan, companion |
| `reproductive` | Cycle log and cycle charts |
| `voice` | Microphone transcription |
| `ai_processing` | Companion, summaries, and library rewrites. The consent text says Groq receives the text or voice clip, and that a Groq failure sends the same text to local Ollama |
| `report_sharing` | The 30-day report |

## Privacy

Check-in notes, cycle notes, journal text, summaries, and chat are Fernet-encrypted in SQLite. Safety events store only a level and a source, never the message. Passwords are scrypt hashes and are omitted from the JSON export.

Responses set `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy`, and non-static pages are `Cache-Control: no-store`. Session cookies are HTTP-only and `SameSite=Lax`.

Deleting an account removes the user and related rows. Export downloads a JSON file of the account's own data.

## Project layout

```
app.py                  application factory, health check, seed command
models.py               users, consents, logs, journal, chat, safety events
routes/                 auth, wellness, companion, journal, library and insights
services/               AI client, safety, encryption, i18n, stats, seeding
templates/              Jinja pages
static/                 CSS and JavaScript
content/library.json    self-care cards (en / si / ta)
resources/              helplines and the fictional directory
eval/                   safety prompt set and the language-quality notes
tests/                  pytest suite
```

## Tests

```bash
pytest
```

The suite covers registration and consent gates, encrypted notes, journal save and transcription (audio is not stored), charts and the care plan, Groq-to-Ollama fallback, and the safety screen. `eval/safety_prompts.json` holds 150+ prompts in English, Sinhala, and Tamil. Crisis, abuse, medical, and boundary prompts must not call the chat model. Tests use an in-memory database and a fake AI client, so they do not need Groq or Ollama.

## Limitations

Recorded in `eval/RESULTS.md`:

- Sinhala and Tamil chat quality on the hosted model has not been rated by a native speaker. Treat generated text in those languages as a draft.
- Sinhala and Tamil speech-to-text is unmeasured. The journal asks the user to edit a transcript before saving, and voice is labelled beta.
- Safety keywords and the fixed crisis, abuse, and medical replies are drafts. They need a native speaker and a clinician before a demo with real users.
- Helpline numbers were copied from public pages on 2026-11-09 and are still **UNVERIFIED**.

This build is for local use. It is not set up for a public deployment: the rate limit is in-process, the database is a single SQLite file, and there is no production web server configuration in the repository.

## License

This project is released under the MIT License. The license is on the GitHub repository.
