# 0001: Use a rule-based extractor by default and keep it under the LLM

- Status: Accepted
- Date: 2026-09-30

## Context

care-voice has to turn free-form replies ("not really, I kept waking up", "about an eight") into structured answers, and it has to notice emergencies in any reply. A language model understands free-form speech better than patterns do, but it needs a network connection and an account, sends health information to a third party, can fail or time out, and can return a confident answer that is wrong. A missed fall or a missed "help me" is the worst possible failure for this tool.

## Decision

- The default extractor, `RuleBasedExtractor`, is deterministic, offline, and conservative: an ambiguous reply is `unclear`, never a guess, and the engine re-asks.
- The rule-based extractor scans every reply for emergency, fall, pain, and disorientation phrases, whatever the question.
- The optional `LLMExtractor` always runs the rule-based extractor as well. It merges the rule-based safety flags into the model's answer and falls back to the rule-based answer whenever the model call fails or returns something invalid.
- The LLM only receives the current question, the reply, and today's weekday.

## Consequences

- care-voice works with no API key and no network, and tests run offline.
- A misbehaving model can add signal, but it cannot remove an emergency flag or turn a check-in into a crash.
- The rule-based extractor produces more `unclear` answers for unusual phrasing, which the `POSSIBLE_CONFUSION` rule counts; its threshold is configurable.
- Every new phrasing the extractor learns needs a test, and the property-based tests guard its invariants.
