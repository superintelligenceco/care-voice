"""Keep the generated documentation in step with the code."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import gen_cli_docs  # noqa: E402


@pytest.mark.skipif(
    sys.version_info[:2] != (3, 12),
    reason="argparse help formatting differs between Python versions; docs are built on 3.12",
)
def test_cli_reference_is_up_to_date() -> None:
    current = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
    assert current == gen_cli_docs.render(), "run `python scripts/gen_cli_docs.py`"


def test_every_subcommand_is_documented() -> None:
    text = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
    for name in ("simulate", "history", "alerts", "validate", "serve", "call"):
        assert f"## care-voice {name}" in text
