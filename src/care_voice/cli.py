"""Command-line interface: ``care-voice <command>``."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Iterator, Sequence
from datetime import datetime, time
from pathlib import Path
from typing import TextIO

from care_voice import __version__
from care_voice.config import ConfigError, load_config
from care_voice.engine import RetryPolicy, run_checkin
from care_voice.models import Alert, CheckinResult
from care_voice.notifiers import ConsoleNotifier
from care_voice.script import ScriptError, load_script
from care_voice.service import CareVoice

DISCLAIMER = (
    "care-voice is not a medical device and is not for emergencies. "
    "In an emergency, call your local emergency number."
)
SILENCE_MARKERS = ("", "(silence)", "...")


class TextChannel:
    """A terminal channel. Replies come from a file or from interactive input."""

    def __init__(
        self,
        out: TextIO,
        replies: Iterator[str] | None = None,
        answer: bool = True,
        interactive: bool = False,
    ) -> None:
        self.out = out
        self.replies = replies
        self.answer = answer
        self.interactive = interactive
        self.attempts = 0

    def connect(self) -> bool:
        self.attempts += 1
        if not self.answer:
            self.out.write(f"(call attempt {self.attempts}: no answer)\n")
        return self.answer

    def say(self, text: str) -> None:
        self.out.write(f"agent: {text}\n")

    def listen(self) -> str | None:
        if self.replies is not None:
            try:
                reply = next(self.replies)
            except StopIteration:
                self.out.write("  you: (hung up)\n")
                return None
            self.out.write(f"  you: {reply}\n")
        else:
            try:
                reply = input("  you: ")
            except EOFError:
                return None
        return "" if reply.strip().lower() in SILENCE_MARKERS else reply

    def close(self) -> None:
        pass


def _replies_from(path: str) -> Iterator[str]:
    for line in Path(path).read_text("utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        yield line.rstrip()


def _show(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _print_summary(out: TextIO, result: CheckinResult, alerts: list[Alert]) -> None:
    out.write(f"\n--- check-in {result.status.value} ({result.attempts} attempt(s)) ---\n")
    if result.answers:
        out.write("answers:\n")
        width = max(len(q) for q in result.answers)
        for qid, answer in result.answers.items():
            shown = _show(answer.value) if answer.understood else "(unclear)"
            flags = f"  flags: {', '.join(sorted(answer.flags))}" if answer.flags else ""
            out.write(f"  {qid:<{width}}  {shown}{flags}\n")
    if alerts:
        out.write("alerts:\n")
        for a in alerts:
            out.write(f"  [{a.severity.label.upper()}] {a.code}: {a.message}\n")
            for reason in a.reasons:
                out.write(f"      - {reason}\n")
    else:
        out.write("alerts: none\n")


def _app(args: argparse.Namespace) -> CareVoice:
    config = load_config(args.config)
    if getattr(args, "name", None):
        config.person_name = args.name
    if getattr(args, "db", None):
        config.database = args.db
    return CareVoice.from_config(config)


def cmd_simulate(args: argparse.Namespace, out: TextIO) -> int:
    app = _app(args)
    app.notifiers = [n for n in app.notifiers if not isinstance(n, ConsoleNotifier)]
    if args.no_notify:
        app.notifiers = []
    now = app.now()
    if args.date:
        day = datetime.strptime(args.date, "%Y-%m-%d").date()
        now = datetime.combine(day, time(9, 0), tzinfo=app.config.tz)
    replies = _replies_from(args.replies) if args.replies else None
    interactive = replies is None and not args.no_answer
    if interactive:
        out.write(
            "Type your replies. Press Enter on an empty line for silence, Ctrl-D to hang up.\n"
        )
    out.write(f"({DISCLAIMER})\n\n")
    channel = TextChannel(out, replies, answer=not args.no_answer, interactive=interactive)
    result = run_checkin(
        lambda: app.new_session(now),
        channel,
        RetryPolicy(attempts=app.config.checkin.call_attempts),
    )
    alerts = app.process(result)
    _print_summary(out, result, alerts)
    return 0


def cmd_history(args: argparse.Namespace, out: TextIO) -> int:
    app = _app(args)
    for c in app.store.recent_checkins(args.limit):
        mood = c.value(app.config.rules.ids.mood)
        out.write(
            f"#{c.id}  {c.started_at:%Y-%m-%d %H:%M}  {c.person:<12} {c.status.value:<10}"
            f" mood={mood if mood is not None else '-'}\n"
        )
    return 0


def cmd_alerts(args: argparse.Namespace, out: TextIO) -> int:
    app = _app(args)
    for a in app.store.recent_alerts(args.limit):
        when = f"{a.created_at:%Y-%m-%d %H:%M}" if a.created_at else ""
        out.write(f"{when}  {a.person:<12} {a.severity.label:<8} {a.code}: {a.message}\n")
    return 0


def cmd_validate(args: argparse.Namespace, out: TextIO) -> int:
    config = load_config(args.config)
    script = load_script(config.resolve(args.script or config.script))
    count = sum(1 for _ in script.iter_all())
    out.write(f"ok: config valid, script {script.name!r} has {count} question(s)\n")
    return 0


def _twilio(app: CareVoice) -> object:
    from care_voice.telephony.twilio import TwilioAdapter

    t = app.config.telephony
    return TwilioAdapter(
        app,
        account_sid=os.environ.get(t.account_sid_env, ""),
        auth_token=os.environ.get(t.auth_token_env, ""),
        from_number=t.from_number,
        public_url=t.public_url,
    )


def cmd_serve(args: argparse.Namespace, out: TextIO) -> int:
    from care_voice.dashboard import serve
    from care_voice.telephony.twilio import TwilioAdapter

    app = _app(args)
    twilio = None
    if args.twilio:
        adapter = _twilio(app)
        assert isinstance(adapter, TwilioAdapter)
        twilio = adapter
    host = args.host or app.config.dashboard_host
    port = args.port or app.config.dashboard_port
    server = serve(app.store, host, port, twilio)
    out.write(f"care-voice dashboard on http://{host}:{port}/  ({DISCLAIMER})\n")
    if twilio:
        out.write("EXPERIMENTAL Twilio webhooks mounted at /twilio/voice and /twilio/status\n")
    out.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def cmd_call(args: argparse.Namespace, out: TextIO) -> int:
    from care_voice.telephony.twilio import TwilioAdapter

    app = _app(args)
    number = args.to or app.config.person_phone
    if not number:
        raise ConfigError("no phone number: pass --to or set person.phone in the config")
    adapter = _twilio(app)
    assert isinstance(adapter, TwilioAdapter)
    sid = adapter.start_checkin(number)
    out.write(
        f"EXPERIMENTAL: placed call {sid}. Keep `care-voice serve --twilio` running so the"
        " call can reach the webhooks.\n"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="care-voice",
        description="Daily voice check-ins for older adults living alone. " + DISCLAIMER,
    )
    parser.add_argument("--version", action="version", version=f"care-voice {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="log debug output")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--config", help="path to a care-voice YAML config file")
    common.add_argument("--db", help="SQLite database path (overrides the config)")
    sub = parser.add_subparsers(dest="command", required=True)

    sim = sub.add_parser("simulate", parents=[common], help="run a check-in in the terminal")
    sim.add_argument("--replies", help="file with one reply per line instead of typing")
    sim.add_argument("--name", help="the person's name (overrides the config)")
    sim.add_argument("--date", help="pretend today is YYYY-MM-DD (affects the day question)")
    sim.add_argument("--no-answer", action="store_true", help="simulate an unanswered call")
    sim.add_argument("--no-notify", action="store_true", help="do not run configured notifiers")
    sim.set_defaults(func=cmd_simulate)

    hist = sub.add_parser("history", parents=[common], help="list recent check-ins")
    hist.add_argument("--limit", type=int, default=20)
    hist.set_defaults(func=cmd_history)

    al = sub.add_parser("alerts", parents=[common], help="list recent alerts")
    al.add_argument("--limit", type=int, default=20)
    al.set_defaults(func=cmd_alerts)

    val = sub.add_parser("validate", parents=[common], help="check a config and script")
    val.add_argument("--script", help="script file to validate (defaults to the configured one)")
    val.set_defaults(func=cmd_validate)

    srv = sub.add_parser("serve", parents=[common], help="run the caregiver dashboard")
    srv.add_argument("--host")
    srv.add_argument("--port", type=int)
    srv.add_argument("--twilio", action="store_true", help="mount Twilio webhooks (experimental)")
    srv.set_defaults(func=cmd_serve)

    call = sub.add_parser("call", parents=[common], help="place a Twilio call (experimental)")
    call.add_argument("--to", help="E.164 phone number, for example +15555550100")
    call.set_defaults(func=cmd_call)
    return parser


def main(argv: Sequence[str] | None = None, out: TextIO | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        code: int = args.func(args, out or sys.stdout)
    except (ConfigError, ScriptError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
