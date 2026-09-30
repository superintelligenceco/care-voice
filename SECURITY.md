# Security policy

care-voice stores personal and health-related information about the people it calls. Please treat security issues seriously and report them privately.

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

## Report a vulnerability

Do not open a public issue for a security problem.

Use GitHub's private vulnerability reporting: open the repository's **Security** tab and select **Report a vulnerability**. Include:

- A description of the issue and its impact.
- Steps to reproduce, or a proof of concept.
- The version or commit you tested.

You can expect an acknowledgement within 7 days. After the issue is confirmed, a fix is prepared and released, and you are credited in the release notes unless you prefer otherwise.

## Scope

Examples of issues that are in scope:

- Bypassing dashboard authentication or Twilio webhook signature checks.
- Reading check-in history or alerts without authorization.
- Injection through replies, scripts, or configuration that leads to code execution or leaks data.
- Secrets written to logs, the database, or notifier output.

## Deployment guidance

- Keep the dashboard on `127.0.0.1`, or set `CARE_VOICE_DASHBOARD_PASSWORD` and serve it over TLS.
- Keep secrets in environment variables. The config file only names them.
- Restrict file permissions on the SQLite database.
