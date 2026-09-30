# Concepts

care-voice has five moving parts. Each one is small and replaceable.

## Check-in script

A YAML file lists the questions in order. Each question has an `id`, the text the agent says, an answer type (`yes_no`, `scale`, `day_of_week`, or `text`), an optional re-prompt, and optional follow-ups that only run for some answers, such as "how bad is the pain?" after a yes to "are you in any pain?". care-voice bundles a morning script; you can replace it with `script: path/to/your-script.yaml`. Run `care-voice validate --script your-script.yaml` to check it.

The alert rules find answers by question id. Keep the ids `slept_well`, `took_meds`, `has_eaten`, `in_pain`, `pain_level`, `had_fall`, `day_of_week`, and `mood` if you want the matching rules to apply.

## Session

A `CheckinSession` runs one conversation, turn by turn. You call `start()` for the opening line, then `respond(reply)` for each reply until `done` is true. The session re-asks unclear answers up to `checkin.max_reprompts` times, counts silences, ends the check-in after `checkin.max_silences` silences in a row, and records the full transcript.

`run_checkin` drives a session over a `Channel` (the terminal simulator, or a test double) and retries when nobody answers. The Twilio adapter feeds provider events into the same session instead.

## Extractor

An extractor turns one reply into an `Answer`: a value, a status (`answered` or `unclear`), and safety flags (`emergency`, `fall`, `pain`, `disoriented`).

- `RuleBasedExtractor` is the default. It runs offline and is deliberately conservative: when a reply is ambiguous, the answer is `unclear` instead of a guess. It also scans every reply for emergency words, falls, pain, and disoriented phrases, whatever the question.
- `LLMExtractor` sends the current question and reply to any OpenAI-compatible chat completions endpoint. The rule-based extractor always runs underneath it: its flags are merged in, and its answer is used whenever the model call fails or returns something invalid.

## Rules

A rule is a pure function `(result, history, config) -> Alert | None`. `RiskEngine` runs every rule, attaches the check-in id and person to each alert, and sorts the alerts from most to least severe. Rules that need a baseline, such as `MOOD_DROP` and the `NO_ANSWER` streak, read the person's own history from SQLite. See [Alert rules](alert-rules.md) for the full list.

## Notifiers

A notifier delivers alerts at or above its `min_severity`. care-voice ships three: console, webhook (JSON, optionally signed with HMAC-SHA256), and email over SMTP. A failing notifier is logged and does not stop the others.

## Service

`CareVoice` wires everything together from a `Config`: it stores each result, loads the history, runs the rules, stores the alerts, and calls the notifiers. The CLI, the dashboard, and the Twilio adapter all go through it.
