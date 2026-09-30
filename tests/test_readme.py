"""Keep the README honest: run its commands and compare the output it shows."""

from __future__ import annotations

import argparse
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from care_voice.cli import build_parser

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _blocks(lang: str) -> list[str]:
    return re.findall(rf"```{lang}\n(.*?)```", README, re.S)


def _run_cli(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "care_voice", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return proc.stdout


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "examples", tmp_path / "examples")
    return tmp_path


def test_see_it_work_output_matches_a_real_run(workdir: Path) -> None:
    demo = next(b for b in _blocks("text") if b.startswith("$ care-voice simulate"))
    command, expected = demo.split("\n", 1)
    args = shlex.split(command.removeprefix("$ "))[1:]
    assert _run_cli(args, workdir) == expected


def test_quickstart_command_runs(workdir: Path) -> None:
    quickstart = README.split("## Quickstart", 1)[1].split("\n## ", 1)[0]
    lines = [
        line
        for block in re.findall(r"```bash\n(.*?)```", quickstart, re.S)
        for line in block.splitlines()
        if line.startswith("care-voice ")
    ]
    assert lines, "the quickstart shows no care-voice command"
    for line in lines:
        output = _run_cli(shlex.split(line)[1:], workdir)
        assert "--- check-in completed" in output
        assert "[HIGH] FALL_REPORTED" in output


def test_usage_block_lists_real_subcommands_and_flags() -> None:
    usage = README.split("## Usage", 1)[1].split("```bash\n", 1)[1].split("```", 1)[0]
    parser = build_parser()
    subparsers = next(
        a.choices for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    for line in usage.strip().splitlines():
        words = line.split("#", 1)[0].split()
        assert words[0] == "care-voice"
        sub = subparsers[words[1]]
        known = {opt for action in sub._actions for opt in action.option_strings}
        for flag in re.findall(r"--[a-z][a-z-]*", " ".join(words[2:])):
            assert flag in known, f"README shows {flag} for {words[1]}, which the CLI lacks"
