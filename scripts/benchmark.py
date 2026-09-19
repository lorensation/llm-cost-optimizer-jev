from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Reduce a paired pilot result manifest without making provider calls.")
    parser.add_argument("--input", default="data/pilot.jsonl")
    parser.add_argument("--results", required=True)
    parser.add_argument("--output", default="artifacts/pilot/report.md")
    args = parser.parse_args()
    cases = {row["id"]: row for row in map(json.loads, Path(args.input).read_text(encoding="utf-8").splitlines())}
    results = list(map(json.loads, Path(args.results).read_text(encoding="utf-8").splitlines()))
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in results:
        if row["case_id"] not in cases:
            raise SystemExit(f"unknown case {row['case_id']}")
        grouped[str(row["model_alias"])].append(row)
    lines = ["# Pilot report", "", "> Computed from the supplied manifest. Fixture/replay results are not provider measurements.", "", "| model | n | success | cost (micro-USD) | cost/success |", "|---|---:|---:|---:|---:|"]
    for model, rows in sorted(grouped.items()):
        success = sum(bool(row["success"]) for row in rows)
        cost = sum(int(row.get("cost_microusd", 0)) for row in rows)
        ratio = f"{cost / success:.2f}" if success else "n/a"
        lines.append(f"| {model} | {len(rows)} | {success / len(rows):.3f} | {cost} | {ratio} |")
    lines += ["", "Decision: `insufficient_evidence` until representative labeled data and authorized real runs exist."]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

