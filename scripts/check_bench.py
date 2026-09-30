"""Fail when a benchmark is more than MAX_RATIO times slower than the baseline.

Usage: python scripts/check_bench.py CURRENT.json BASELINE.json

Both files are pytest-benchmark JSON output. Pass --update to copy the current
results over the baseline after an intentional change.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

MAX_RATIO = 2.0


def _medians(path: Path) -> dict[str, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {b["name"]: float(b["stats"]["median"]) for b in data["benchmarks"]}


def main(argv: list[str]) -> int:
    update = "--update" in argv
    args = [a for a in argv if a != "--update"]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    current_path, baseline_path = Path(args[0]), Path(args[1])
    if update:
        shutil.copyfile(current_path, baseline_path)
        print(f"updated {baseline_path}")
        return 0
    current, baseline = _medians(current_path), _medians(baseline_path)
    rows = ["| Benchmark | Baseline (us) | Current (us) | Ratio |", "| --- | --- | --- | --- |"]
    failed = []
    for name, base in sorted(baseline.items()):
        if name not in current:
            failed.append(f"{name}: missing from the current run")
            continue
        ratio = current[name] / base
        rows.append(f"| {name} | {base * 1e6:.1f} | {current[name] * 1e6:.1f} | {ratio:.2f}x |")
        if ratio > MAX_RATIO:
            failed.append(f"{name}: {ratio:.2f}x slower than the baseline (limit {MAX_RATIO}x)")
    table = "\n".join(rows)
    print(table)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## Benchmarks\n\n{table}\n")
    for line in failed:
        print(f"FAIL {line}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
