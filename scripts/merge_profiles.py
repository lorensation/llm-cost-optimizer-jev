from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def merge_profiles(paths: list[Path]) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    experiment: dict[str, Any] | None = None
    for path in paths:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("validated_for_active"):
            raise SystemExit(f"{path} is marked validated_for_active; merge inputs must be provisional pilot outputs")
        if experiment is None:
            experiment = manifest["experiment"]
        elif experiment != manifest["experiment"]:
            raise SystemExit(f"{path} was measured under different generation settings than earlier inputs")
        sources.append({
            "label": path.stem, "dataset_sha256": manifest["dataset_sha256"],
            "results_sha256": manifest["results_sha256"], "results_file_sha256": manifest.get("results_file_sha256"),
            "config_sha256": manifest["config_sha256"], "evaluator_sha256": manifest["evaluator_sha256"],
        })
        for profile in manifest["profiles"]:
            key = (profile["contract_id"], profile["model_alias"])
            if key in seen:
                raise SystemExit(f"duplicate profile {key} across merge inputs; pilots must cover disjoint contracts")
            seen.add(key)
            profiles.append(profile)
    return {
        "version": f"claude-final-merged-{datetime.now(UTC).date().isoformat()}", "validated_for_active": False,
        "sources": sources, "experiment": experiment, "profiles": profiles,
        "notice": "Merged from separate pilot measurements listed in 'sources'. Not an untouched final test and not validated for active routing.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge disjoint per-contract pilot profile manifests into one routing profile file.")
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    merged = merge_profiles(args.inputs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(json.dumps({"path": str(args.output), "profiles": len(merged["profiles"]), "sources": len(merged["sources"])}))


if __name__ == "__main__":
    main()
