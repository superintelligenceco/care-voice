# Changelog

All notable changes to this project are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-09-30

The first public release. care-voice runs a daily check-in conversation, stores the results locally, and alerts caregivers when replies look concerning. It is not a medical device and not an emergency service.

### Added

- Conversation engine driven by a YAML check-in script, with `yes_no`, `scale`, `day_of_week`, and `text` questions, follow-ups, re-prompts for unclear answers, silence handling, and call retries.
- Bundled morning check-in script and an example evening script.
- Offline rule-based extractor that understands common ways of saying yes, no, numbers, feelings, and weekdays, and flags emergency words, falls, pain, and disorientation.
- Optional LLM extractor for any OpenAI-compatible chat completions endpoint. The rule-based extractor always runs underneath it as a safety net and as the fallback when the call fails.
- Risk-rules engine with twelve alert codes: `EMERGENCY_WORDS`, `NO_ANSWER`, `CHECKIN_INCOMPLETE`, `FALL_REPORTED`, `MISSED_MEDS`, `MEDS_UNCONFIRMED`, `PAIN_REPORTED`, `POSSIBLE_CONFUSION`, `MOOD_DROP`, `LOW_MOOD`, `NOT_EATEN`, and `POOR_SLEEP`. Every alert lists the replies that triggered it.
- SQLite history, used for mood baselines and for escalating consecutive missed calls.
- Console, webhook (with optional HMAC-SHA256 signatures), and SMTP email notifiers, each with its own minimum severity.
- `care-voice` command with `simulate`, `history`, `alerts`, `validate`, `serve`, and `call` subcommands.
- Caregiver dashboard and JSON API, with optional HTTP basic authentication.
- Experimental telephony: a `VoiceAdapter` interface and a Twilio Programmable Voice adapter with webhook signature checks and retries.
- Dockerfile and Docker Compose file for the dashboard.
- CI for lint, format, typecheck, and tests on Linux and macOS with Python 3.11 to 3.13, plus CodeQL, a Docker build check, and release automation.

[Unreleased]: https://github.com/superintelligenceco/care-voice/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/superintelligenceco/care-voice/releases/tag/v0.1.0
