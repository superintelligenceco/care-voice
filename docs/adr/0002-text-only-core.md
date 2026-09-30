# 0002: Keep the core text-only and put voice behind an adapter

- Status: Accepted
- Date: 2026-09-30

## Context

A real check-in is a phone call, but speech recognition, text-to-speech, and call control differ between providers (Twilio, LiveKit, browser WebRTC) and change often. Testing a conversation engine through audio is slow and flaky, and a simulator is essential for trying scripts and rules without calling anyone.

## Decision

- The conversation engine (`CheckinSession`), the extractors, and the rules only ever see text.
- Speech recognition and text-to-speech stay with the voice provider.
- Voice providers plug in through the `VoiceAdapter` protocol, which feeds provider events (`answered`, `speech`, `silence`, `ended`, `unanswered`) into a session. The Twilio adapter is the first implementation and is marked experimental.
- Synchronous channels, such as the terminal simulator, implement the small `Channel` protocol used by `run_checkin`.

## Consequences

- The simulator, the tests, and a real call exercise exactly the same engine, extractor, and rules.
- Adding a provider means writing one adapter, not changing the core.
- Transcription quality is the provider's responsibility; care-voice cannot correct a mis-heard word, which is one more reason the extractor re-asks unclear answers.
