# Language-quality gate

This file is the place the plan reserves for native-speaker ratings and speech-error scores. Those measurements have not been run.

## Decision still open

- Sinhala and Tamil chat quality on the hosted model is unmeasured. Until a native speaker rates about 50 wellness prompts per language, treat generated Sinhala and Tamil as draft.
- Sinhala and Tamil speech-to-text is unmeasured. The journal keeps "edit the transcript before you save" in front, and voice is labelled beta.
- Safety keywords and the fixed crisis, abuse, and medical replies are drafts. They need a native speaker and a clinician before any real-user demo.
- Helpline numbers were copied from public pages on 2026-11-09 and are still marked UNVERIFIED.

## What this build did instead

Text features try Groq first and fall back to a local Ollama model. Voice transcription stays on Groq Whisper, because Ollama does not accept the audio. The rule screen in `services/safety.py` is what the automated tests lock: crisis, abuse, medical, and boundary prompts do not call the chat model.
