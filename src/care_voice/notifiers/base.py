"""The notifier interface and shared helpers."""

from __future__ import annotations

from typing import Any, Protocol

from care_voice.models import Alert, CheckinResult, Severity


class Notifier(Protocol):
    """Delivers alerts at or above ``min_severity``."""

    name: str
    min_severity: Severity

    def send(self, alerts: list[Alert], result: CheckinResult) -> None:
        """Deliver ``alerts`` (already filtered by severity). May raise on failure."""
        ...


def filter_alerts(alerts: list[Alert], min_severity: Severity) -> list[Alert]:
    return [a for a in alerts if a.severity >= min_severity]


def alert_payload(alerts: list[Alert], result: CheckinResult) -> dict[str, Any]:
    """The JSON document sent by the webhook notifier and shown in the docs."""
    return {
        "person": result.person,
        "checkin_id": result.id,
        "checkin_status": result.status.value,
        "started_at": result.started_at.isoformat(),
        "alerts": [
            {
                "code": a.code,
                "severity": a.severity.label,
                "message": a.message,
                "reasons": list(a.reasons),
            }
            for a in alerts
        ],
    }


def format_text(alerts: list[Alert], result: CheckinResult) -> str:
    """A plain-text summary used by the console and email notifiers."""
    lines = [
        f"care-voice check-in for {result.person} at {result.started_at:%Y-%m-%d %H:%M}"
        f" ({result.status.value})",
        "",
    ]
    for a in alerts:
        lines.append(f"[{a.severity.label.upper()}] {a.code}: {a.message}")
        lines.extend(f"    - {reason}" for reason in a.reasons)
    lines += [
        "",
        "care-voice is not a medical device and does not contact emergency services.",
    ]
    return "\n".join(lines)
