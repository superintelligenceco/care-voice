# Quickstart

You don't need an API key, an account, or network access to try care-voice.

## Install

Pick one of these options.

=== "pip"

    ```bash
    python3 -m pip install care-voice
    ```

    You need Python 3.11 or later.

=== "Standalone executable"

    ```bash
    curl -fsSL https://raw.githubusercontent.com/superintelligenceco/care-voice/main/install.sh | sh
    ```

    The script downloads the executable for your operating system and architecture (Linux x64 and arm64, macOS arm64 and x64) from the latest GitHub Release, checks it against `SHA256SUMS`, and installs it to `~/.local/bin`. Set `CARE_VOICE_VERSION=v0.2.0` to pin a release, or `CARE_VOICE_INSTALL_DIR` to install somewhere else. For Windows, download `care-voice-windows-x64.exe` from the [releases page](https://github.com/superintelligenceco/care-voice/releases).

=== "Docker"

    ```bash
    docker run --rm -p 127.0.0.1:8080:8080 ghcr.io/superintelligenceco/care-voice:latest
    ```

    The image runs the caregiver dashboard on port 8080. It is built for `linux/amd64` and `linux/arm64` and signed with cosign.

## Run a check-in

Start an interactive check-in and answer the questions yourself:

```bash
care-voice simulate --name Margaret --db demo.db
```

Press Enter on an empty line to stay silent, or Ctrl-D to hang up. To replay a file of replies instead, download the example from the repository:

```bash
curl -fsSLO https://raw.githubusercontent.com/superintelligenceco/care-voice/main/examples/replies/concerning-day.txt
care-voice simulate --name Margaret --replies concerning-day.txt --date 2026-09-30 --db demo.db
```

The summary at the end lists each answer and each alert, with the replies that triggered it:

```text
alerts:
  [HIGH] FALL_REPORTED: Margaret reported a fall.
      - answered yes to the fall question: "I slipped in the bathroom last night"
  [HIGH] MISSED_MEDS: Margaret has not taken their morning medication.
      - said: "No, I forgot them"
```

## Look at the history

```bash
care-voice history --db demo.db
care-voice alerts --db demo.db
```

## Open the dashboard

```bash
care-voice serve --db demo.db
```

Then open <http://127.0.0.1:8080/>. To run the dashboard with Docker Compose from a clone of the repository, run `docker compose up --build`.

## Next steps

- Write a config file. See [Configuration](configuration.md).
- Tune the thresholds. See [Alert rules](alert-rules.md).
- Send alerts to a webhook or email address with [notifiers](configuration.md#notifiers).
