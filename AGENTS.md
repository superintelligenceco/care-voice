# Notes for coding agents

This file gives automated coding agents the context they need to work in this repository. Human contributors can read it too; [CONTRIBUTING.md](CONTRIBUTING.md) has the full guidelines.

## What this project is

care-voice runs a short daily check-in conversation with an older adult, extracts structured answers, applies alert rules, and notifies caregivers. It is not a medical device and not an emergency service. Never add wording that claims otherwise.

## Layout

- `src/care_voice/script.py`: YAML check-in script loading and validation.
- `src/care_voice/engine.py`: `CheckinSession` (turn-by-turn conversation) and `run_checkin` (retries over a channel).
- `src/care_voice/extractors/`: `Extractor` protocol, `RuleBasedExtractor` (offline, default), `LLMExtractor` (OpenAI-compatible, uses the rule-based extractor as a safety net).
- `src/care_voice/risk.py`: alert rules. Each rule is a pure function `(result, history, config) -> Alert | None`.
- `src/care_voice/store.py`: SQLite persistence.
- `src/care_voice/notifiers/`: console, webhook, and email notifiers.
- `src/care_voice/service.py`: glues store, rules, and notifiers.
- `src/care_voice/dashboard.py`: standard-library HTTP server for the caregiver page, JSON API, and Twilio webhooks.
- `src/care_voice/telephony/`: `VoiceAdapter` protocol and the experimental Twilio adapter.
- `src/care_voice/cli.py`: the `care-voice` command.
- `tests/`: pytest suite. `tests/helpers.py` has a local HTTP server used instead of real services.

## Commands

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy && pytest --cov
```

All four must pass before you finish a change.

## Rules

- Tests must run offline. Never call a real LLM, SMTP server, webhook, or telephony API from a test.
- Keep runtime dependencies to PyYAML and the standard library.
- Keep the rule-based extractor conservative: ambiguous replies are unclear, not guessed.
- Every alert carries reasons that quote what the person said.
- Safety flags from the rule-based extractor must never be dropped by the LLM path.
- Do not commit databases, `.env` files, real transcripts, phone numbers, or secrets.
- Use Conventional Commits for commit messages.
- Update `README.md` (especially the alert rules reference and configuration table) when behavior changes.
