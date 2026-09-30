# Configuration

Copy [`examples/care-voice.yaml`](https://github.com/superintelligenceco/care-voice/blob/main/examples/care-voice.yaml) and pass it with `--config`. Every key is optional. Secrets never go in the file: keys ending in `_env` name the environment variable that holds the secret.

| Key | Default | Meaning |
| --- | --- | --- |
| `person.name` | `friend` | The name the agent uses. |
| `person.timezone` | `UTC` | IANA time zone, used for the day-of-week question. |
| `person.phone` | empty | E.164 number for the experimental telephony adapter. |
| `script` | `default` | `default` or a path to your own YAML script. |
| `database` | `care-voice.db` | SQLite file. Relative paths resolve against the config file. |
| `checkin.max_reprompts` | `1` | How many times to re-ask an unclear answer. |
| `checkin.max_silences` | `3` | Silences in a row before the check-in ends as incomplete. |
| `checkin.call_attempts` | `3` | Tries before a check-in is recorded as unanswered. |
| `checkin.retry_delay_minutes` | `10` | Wait between telephony attempts. |
| `extractor.kind` | `rules` | `rules` or `llm`. |
| `extractor.base_url`, `model`, `api_key_env` | none | Settings for the LLM extractor. |
| `rules.*` | see [Alert rules](alert-rules.md) | Thresholds for the alert rules. |
| `notifiers` | console | A list of `console`, `webhook`, or `email` notifiers, each with `min_severity`. |
| `dashboard.host`, `dashboard.port` | `127.0.0.1`, `8080` | Where `care-voice serve` listens. |
| `telephony.*` | none | Twilio settings. See [Telephony](#telephony-experimental). |

### Custom scripts

A script is a list of questions. The alert rules find answers by question id, so keep the ids `slept_well`, `took_meds`, `has_eaten`, `in_pain`, `pain_level`, `had_fall`, `day_of_week`, and `mood` if you want the matching rules to apply. See [`examples/gentle-evening-script.yaml`](https://github.com/superintelligenceco/care-voice/blob/main/examples/gentle-evening-script.yaml) and the bundled [`default_script.yaml`](https://github.com/superintelligenceco/care-voice/blob/main/src/care_voice/data/default_script.yaml). Check a script with `care-voice validate --script my-script.yaml`.

### Notifiers

Each entry in `notifiers` has a `kind` and a `min_severity` (`low`, `medium`, `high`, or `critical`). The console notifier defaults to `low`; the webhook and email notifiers default to `medium`.

```yaml
notifiers:
  - kind: console
    min_severity: low
  - kind: webhook
    url: https://example.com/care-voice-hook
    secret_env: CARE_VOICE_WEBHOOK_SECRET   # optional HMAC-SHA256 signing
    min_severity: medium
  - kind: email
    host: smtp.example.com
    port: 587
    security: starttls
    sender: care-voice@example.com
    recipients: [caregiver@example.com]
    username: care-voice@example.com
    password_env: CARE_VOICE_SMTP_PASSWORD
    min_severity: high
```

### Webhook payload

```json
{
  "person": "Margaret",
  "checkin_id": 12,
  "checkin_status": "completed",
  "started_at": "2026-09-30T09:00:00+01:00",
  "alerts": [
    {
      "code": "FALL_REPORTED",
      "severity": "high",
      "message": "Margaret reported a fall.",
      "reasons": ["answered yes to the fall question: \"I slipped in the bathroom last night\""]
    }
  ]
}
```

When `secret_env` is set, each request carries `X-Care-Voice-Signature: sha256=<hex>`, an HMAC-SHA256 of the raw body.

## Telephony (experimental)

The `care_voice.telephony` package defines a small `VoiceAdapter` protocol: place a call, then feed provider events (`answered`, `speech`, `silence`, `ended`, `unanswered`) into a `CheckinSession`. The Twilio adapter implements it with `<Gather input="speech">` and checks every webhook against the `X-Twilio-Signature` header.

It places real phone calls when you give it real credentials. Test it with your own number first.

```bash
export TWILIO_ACCOUNT_SID=... TWILIO_AUTH_TOKEN=...
care-voice serve --config my.yaml --twilio          # must be reachable at telephony.public_url
care-voice call  --config my.yaml --to +15555550100
```

care-voice does not schedule calls itself. Use cron or a systemd timer to run `care-voice call` each morning.
