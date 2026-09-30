"""Generate docs/cli.md from the argparse definitions of the ``care-voice`` command.

Run ``python scripts/gen_cli_docs.py`` after you change a command or option.
``tests/test_docs.py`` fails when docs/cli.md is out of date.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from care_voice.cli import build_parser

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "docs" / "cli.md"

HEADER = """# CLI reference

This page is generated from the `care-voice` argument parser by
`scripts/gen_cli_docs.py`. Every subcommand accepts `-c/--config` with the path
to a YAML config file. See [Configuration](configuration.md).
"""


def _subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


def render() -> str:
    os.environ["COLUMNS"] = "80"
    parser = build_parser()
    parser.prog = "care-voice"
    parts = [HEADER, "## care-voice\n", "```text", parser.format_help().rstrip(), "```\n"]
    for name, sub in _subparsers(parser).items():
        parts += [f"## care-voice {name}\n", "```text", sub.format_help().rstrip(), "```\n"]
    return "\n".join(parts)


def main() -> int:
    TARGET.write_text(render(), encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
