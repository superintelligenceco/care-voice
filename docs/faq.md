# FAQ

## Is care-voice a medical device or an emergency service?

No. care-voice does not diagnose, treat, or monitor any condition, and it never contacts emergency services. When it hears emergency words, it tells the person to call their local emergency number and sends a critical alert to your notifiers, which can fail or arrive late. Use it alongside human contact and a personal alarm, not instead of them.

## Do I need an API key or an internet connection?

No. The default rule-based extractor, the rules, the SQLite store, the simulator, and the dashboard all run offline. You only need network access for the optional LLM extractor, the webhook and email notifiers, and the Twilio adapter.

## Does it place real phone calls?

Only with the experimental Twilio adapter and real Twilio credentials. Test it with your own number first. care-voice does not schedule calls itself: run `care-voice call` from cron or a systemd timer.

## Which LLM providers work?

Any provider or local server that exposes an OpenAI-compatible chat completions endpoint. Set `extractor.kind: llm`, `extractor.base_url`, `extractor.model`, and `extractor.api_key_env`. care-voice sends only the current question, the reply, and today's weekday; it never sends the person's name, history, or caregiver details.

## Can a model hide an emergency?

No. The rule-based extractor always runs underneath the LLM extractor. Its safety flags are merged into every answer, and its answer is used whenever the model call fails or returns something invalid.

## Why did a reply come back as "unclear"?

The rule-based extractor does not guess. If a reply does not match any phrasing it knows, the answer is `unclear` and the agent re-asks once (see `checkin.max_reprompts`). Two or more unclear answers in one check-in raise `POSSIBLE_CONFUSION`, so tune `rules.unclear_answers_threshold` if the person often answers in their own words, or try the LLM extractor.

## Can I change the questions?

Yes. Copy the bundled `default_script.yaml`, edit it, and set `script:` in your config to its path. Keep the standard question ids if you want the matching alert rules to apply. Check the file with `care-voice validate --script my-script.yaml`.

## Does it support languages other than English?

Not yet. The script wording is yours to change, but the rule-based extractor only understands English replies. With the LLM extractor, replies in other languages often work, but they are not tested.

## Where is the data stored, and how do I delete it?

In the SQLite file named by `database` (default `care-voice.db`, next to the config file). Delete the file to delete all history. The Docker image stores it in the `/data` volume.

## How do I protect the dashboard?

It binds to `127.0.0.1` by default. Set `CARE_VOICE_DASHBOARD_PASSWORD` to require HTTP basic authentication, and put a reverse proxy with TLS in front before you expose it to anyone else.

## How do I verify a downloaded release?

Each release has `SHA256SUMS` and build provenance attestations. `install.sh` checks the checksum for you. To check the provenance, run `gh attestation verify care-voice-linux-x64 -R superintelligenceco/care-voice`. To check the container image signature, run:

```bash
cosign verify ghcr.io/superintelligenceco/care-voice:v0.2.0 \
  --certificate-identity-regexp '^https://github.com/superintelligenceco/care-voice/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```
