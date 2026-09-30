# Changelog

All notable changes to this project are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-09-30

This release makes care-voice installable without a Python toolchain and hardens how it is built and shipped. The check-in engine, extractors, and alert rules behave exactly as in 0.1.0.

### Added

- Published on PyPI: `pip install care-voice`.
- Standalone executables for Linux x64 and arm64, macOS arm64 and x64, and Windows x64, attached to every GitHub Release.
- `install.sh`, a `curl | sh` installer that downloads the right executable for your system and checks it against `SHA256SUMS`.
- Multi-arch container image `ghcr.io/superintelligenceco/care-voice` (`linux/amd64`, `linux/arm64`), signed with cosign, and a release Compose file that runs it.
- SPDX SBOM, checksums, and build provenance attestations for every release file and the image.
- Documentation site at <https://superintelligenceco.github.io/care-voice/> with a quickstart, concepts, CLI and Python API reference, FAQ, architecture diagrams, and decision records.
- Demo GIF recorded from a real terminal session.
- Property-based tests for the parsers and alert rules, a test that runs the README commands and compares their output, a benchmark gate against a committed baseline, a nightly full-suite workflow, and weekly mutation testing.
- OpenSSF Scorecard, dependency review, Trivy image scanning, actionlint, and Markdown link checking in CI.
- Makefile, pre-commit hooks, dev container for GitHub Codespaces, editor settings, `CITATION.cff`, and `llms.txt`.

### Changed

- Releases start from a pushed `v*` tag; release-please is gone.

### Fixed

- On Windows, `pip install care-voice` now pulls in `tzdata`, so time zones such as `UTC` resolve without a system time zone database.

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

[Unreleased]: https://github.com/superintelligenceco/care-voice/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/superintelligenceco/care-voice/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/superintelligenceco/care-voice/releases/tag/v0.1.0
