# Contributing to care-voice

Thank you for helping. care-voice runs near vulnerable people, so changes favor clarity, predictability, and safety over cleverness.

## Before you start

- Read the [Code of Conduct](CODE_OF_CONDUCT.md).
- For anything larger than a small fix, open a feature request issue first so the design can be discussed before you write code.
- Report security issues privately. See [SECURITY.md](SECURITY.md).

## Set up your environment

You need Python 3.11 or later.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Run the checks

Run the same checks that CI runs before you open a pull request:

```bash
ruff check .
ruff format --check .
mypy
pytest --cov
```

Try your change end to end in the simulator:

```bash
care-voice simulate --replies examples/replies/concerning-day.txt --date 2026-09-30
```

## Guidelines

- **Tests work offline.** Tests never call a real LLM, SMTP server, webhook, or telephony provider. Use the local fakes in `tests/`.
- **Add a test for every rule or extractor change.** Include the exact reply text that motivated the change.
- **Keep the extractor conservative.** When a reply is ambiguous, report it as unclear instead of guessing.
- **Every alert explains itself.** New rules must add human-readable reasons that quote what the person said.
- **No clinical claims.** Do not describe care-voice, a rule, or an alert as diagnosing, detecting, or preventing a condition.
- **No new runtime dependencies** without discussion. The core depends only on PyYAML.
- **Type everything.** `mypy --strict` runs on `src/`.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `chore:`, `refactor:`. Release notes and version numbers are generated from them.

## Pull requests

- Keep each pull request focused on one change.
- Fill in the pull request template, including how you tested the change.
- Update `README.md` when you change behavior, configuration, or alert rules.
- Add an entry under `Unreleased` in `CHANGELOG.md` for user-facing changes.

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE).
