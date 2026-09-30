# Architecture

```mermaid
flowchart LR
    subgraph Channels
        SIM[Terminal simulator]
        TW[Twilio adapter<br/>experimental]
    end
    SCRIPT[(YAML check-in script)] --> ENGINE
    SIM <--> ENGINE[Conversation engine<br/>CheckinSession]
    TW <--> ENGINE
    ENGINE -- reply text --> EXT{Extractor}
    EXT --> RULESX[Rule-based<br/>offline, default]
    EXT --> LLM[LLM extractor<br/>optional]
    LLM -. safety net .-> RULESX
    ENGINE -- CheckinResult --> SERVICE[CareVoice service]
    SERVICE <--> DB[(SQLite history)]
    SERVICE --> RISK[Risk-rules engine]
    DB -- baseline --> RISK
    RISK -- alerts --> NOTIFY[Notifiers]
    NOTIFY --> CON[Console]
    NOTIFY --> HOOK[Webhook]
    NOTIFY --> MAIL[Email / SMTP]
    DB --> DASH[Caregiver dashboard]
```

| Module | Responsibility |
| --- | --- |
| `care_voice.script` | Loads and validates YAML check-in scripts. |
| `care_voice.engine` | Runs one check-in turn by turn, with re-prompts, follow-ups, silence handling, and call retries. |
| `care_voice.extractors` | The `Extractor` interface, the rule-based extractor, and the LLM extractor. |
| `care_voice.risk` | The rules that turn a check-in and its history into alerts. |
| `care_voice.store` | SQLite storage for check-ins, transcripts, and alerts. |
| `care_voice.notifiers` | Console, webhook, and email delivery. |
| `care_voice.service` | Wires storage, rules, and notifiers together. |
| `care_voice.dashboard` | The caregiver web page and JSON API, built on the standard library. |
| `care_voice.telephony` | The `VoiceAdapter` interface and the experimental Twilio adapter. |

The core only ever sees text. Speech recognition and text-to-speech stay with the voice provider, so the extractor and the rules behave the same in the simulator and on a real call.

## Data flow of one check-in

```mermaid
sequenceDiagram
    participant P as Person
    participant C as Channel
    participant S as CheckinSession
    participant X as Extractor
    participant V as CareVoice service
    participant DB as SQLite
    participant N as Notifiers
    C->>S: start()
    S-->>C: greeting and first question
    loop each question
        P->>C: reply
        C->>S: respond(reply)
        S->>X: extract(question, reply)
        X-->>S: Answer (value, status, flags)
        S-->>C: next question, re-prompt, or emergency notice
    end
    S-->>V: CheckinResult
    V->>DB: load history, save check-in
    V->>V: RiskEngine.evaluate(result, history)
    V->>DB: save alerts
    V->>N: deliver alerts at or above each min_severity
```

## Release artifacts

Every `v*` tag runs the release workflow, which builds:

- the wheel and sdist, published to [PyPI](https://pypi.org/project/care-voice/);
- standalone PyInstaller executables for Linux x64 and arm64, macOS arm64 and x64, and Windows x64;
- a multi-arch container image, `ghcr.io/superintelligenceco/care-voice`, signed with cosign;
- an SPDX SBOM, `SHA256SUMS`, and build provenance attestations for every file.

Verify a downloaded file with `gh attestation verify <file> -R superintelligenceco/care-voice`.

See the [decision records](adr/index.md) for why the pieces look the way they do.
