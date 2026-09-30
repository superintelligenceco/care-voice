# care-voice

care-voice runs a short daily check-in conversation with an older adult who lives alone, turns the replies into structured answers, and tells a caregiver in plain language when something looks off.

!!! warning "Not a medical device, not for emergencies"
    care-voice does not diagnose, treat, or monitor any condition, and it does not contact emergency services. If someone needs urgent help, call your local emergency number.

![A check-in in the terminal simulator, followed by the stored alerts](assets/demo.gif)

## What it does

- Asks the same short questions every day: sleep, morning medication, food, pain, falls, the day of the week, and mood.
- Extracts answers offline with a conservative rule-based extractor, or with any OpenAI-compatible LLM that you configure.
- Compares today with the person's own history in SQLite and raises alerts that quote the exact reply behind them.
- Sends alerts to the console, a webhook, or email, and shows them on a small caregiver dashboard.

## Where to start

- [Quickstart](quickstart.md): install care-voice and run your first check-in in under a minute.
- [Concepts](concepts.md): scripts, sessions, extractors, rules, and notifiers.
- [CLI reference](cli.md) and [Python API](reference.md).
- [Configuration](configuration.md) and [Alert rules](alert-rules.md).
- [Architecture](architecture.md) and the [decision records](adr/index.md).
- [FAQ](faq.md).
