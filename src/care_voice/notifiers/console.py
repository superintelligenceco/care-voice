"""Print alerts to a stream (stdout by default)."""

from __future__ import annotations

import sys
from typing import TextIO

from care_voice.models import Alert, CheckinResult, Severity
from care_voice.notifiers.base import format_text


class ConsoleNotifier:
    name = "console"

    def __init__(self, min_severity: Severity = Severity.LOW, stream: TextIO | None = None):
        self.min_severity = min_severity
        self.stream = stream

    def send(self, alerts: list[Alert], result: CheckinResult) -> None:
        out = self.stream or sys.stdout
        out.write(format_text(alerts, result) + "\n")
        out.flush()
