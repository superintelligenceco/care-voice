# CLI reference

This page is generated from the `care-voice` argument parser by
`scripts/gen_cli_docs.py`. Every subcommand accepts `-c/--config` with the path
to a YAML config file. See [Configuration](configuration.md).

## care-voice

```text
usage: care-voice [-h] [--version] [-v]
                  {simulate,history,alerts,validate,serve,call} ...

Daily voice check-ins for older adults living alone. care-voice is not a
medical device and is not for emergencies. In an emergency, call your local
emergency number.

positional arguments:
  {simulate,history,alerts,validate,serve,call}
    simulate            run a check-in in the terminal
    history             list recent check-ins
    alerts              list recent alerts
    validate            check a config and script
    serve               run the caregiver dashboard
    call                place a Twilio call (experimental)

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -v, --verbose         log debug output
```

## care-voice simulate

```text
usage: care-voice simulate [-h] [-c CONFIG] [--db DB] [--replies REPLIES]
                           [--name NAME] [--date DATE] [--no-answer]
                           [--no-notify]

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        path to a care-voice YAML config file
  --db DB               SQLite database path (overrides the config)
  --replies REPLIES     file with one reply per line instead of typing
  --name NAME           the person's name (overrides the config)
  --date DATE           pretend today is YYYY-MM-DD (affects the day question)
  --no-answer           simulate an unanswered call
  --no-notify           do not run configured notifiers
```

## care-voice history

```text
usage: care-voice history [-h] [-c CONFIG] [--db DB] [--limit LIMIT]

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        path to a care-voice YAML config file
  --db DB               SQLite database path (overrides the config)
  --limit LIMIT
```

## care-voice alerts

```text
usage: care-voice alerts [-h] [-c CONFIG] [--db DB] [--limit LIMIT]

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        path to a care-voice YAML config file
  --db DB               SQLite database path (overrides the config)
  --limit LIMIT
```

## care-voice validate

```text
usage: care-voice validate [-h] [-c CONFIG] [--db DB] [--script SCRIPT]

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        path to a care-voice YAML config file
  --db DB               SQLite database path (overrides the config)
  --script SCRIPT       script file to validate (defaults to the configured
                        one)
```

## care-voice serve

```text
usage: care-voice serve [-h] [-c CONFIG] [--db DB] [--host HOST] [--port PORT]
                        [--twilio]

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        path to a care-voice YAML config file
  --db DB               SQLite database path (overrides the config)
  --host HOST
  --port PORT
  --twilio              mount Twilio webhooks (experimental)
```

## care-voice call

```text
usage: care-voice call [-h] [-c CONFIG] [--db DB] [--to TO]

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        path to a care-voice YAML config file
  --db DB               SQLite database path (overrides the config)
  --to TO               E.164 phone number, for example +15555550100
```
