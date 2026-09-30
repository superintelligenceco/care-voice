# 0003: Build the dashboard and storage on the standard library

- Status: Accepted
- Date: 2026-09-30

## Context

The people who run care-voice are often a family member with a spare computer or a small care organization, not an operations team. Every runtime dependency adds install weight, upgrade churn, and supply-chain risk, and the tool handles sensitive health information.

## Decision

- Runtime dependencies are limited to PyYAML and the Python standard library.
- The caregiver dashboard, the JSON API, and the Twilio webhooks use `http.server.ThreadingHTTPServer`.
- History, transcripts, and alerts live in a single SQLite file through the `sqlite3` module.
- The LLM extractor and the webhook notifier call HTTP APIs with `urllib.request`; the email notifier uses `smtplib`.

## Consequences

- `pip install care-voice` pulls in one dependency, and the standalone executables stay small.
- Data stays on the machine by default, and deleting one file deletes all history.
- The dashboard is intentionally small: no sessions, no user accounts, and HTTP basic authentication only when `CARE_VOICE_DASHBOARD_PASSWORD` is set. Anyone exposing it beyond `127.0.0.1` needs a reverse proxy with TLS.
- Multi-person installations and a richer UI need a new decision before they add a web framework or a database server.
