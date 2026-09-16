#!/usr/bin/env python3
"""Compare claude plugin eval results for two versions of the skills, case by case.

Usage: compare.py --baseline RESULT.json... --new RESULT.json... [--margin 0.15]

Each RESULT.json is an aggregate-result.json. When several files hold the same case, the later file wins,
so a rerun of some cases can be listed after the full pass. A case is a regression when its new score is
lower by more than the margin, or when a grader that passed every baseline run fails in a new run.
Exit 1 when any case regressed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(paths: list[Path]) -> dict[str, dict]:
    cases: dict[str, dict] = {}
    for path in paths:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("partial"):
            print(f"compare: warning: {path} is partial ({document.get('partialReason')})", file=sys.stderr)
        for case in document.get("cases", []):
            runs = case.get("arms", {}).get("with", [])
            graders: dict[str, list[bool]] = {}
            for run in runs:
                for grader in run.get("graders", []):
                    graders.setdefault(grader["name"], []).append(bool(grader.get("passed")))
            errors = [run["error"] for run in runs if run.get("error")]
            cases[case["name"]] = {"score": case.get("aggregates", {}).get("score"), "runs": len(runs), "graders": graders, "errors": errors}
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--baseline", nargs="+", type=Path, required=True)
    parser.add_argument("--new", nargs="+", type=Path, required=True)
    parser.add_argument("--margin", type=float, default=0.15)
    args = parser.parse_args()
    old, new = load(args.baseline), load(args.new)
    regressed = False
    print(f"{'case':28} {'base':>5} {'new':>5} {'delta':>6}  verdict")
    for name in sorted(set(old) | set(new)):
        before, after = old.get(name), new.get(name)
        if before is None or after is None or before["score"] is None or after["score"] is None:
            print(f"{name:28} {'-' if not before else before['score']:>5} {'-' if not after else after['score']:>5}         missing in one version")
            continue
        delta = after["score"] - before["score"]
        dropped = [g for g, passes in after["graders"].items()
                   if before["graders"].get(g) and all(before["graders"][g]) and not all(passes)]
        verdict = "regressed" if delta < -args.margin or dropped else "improved" if delta > args.margin else "flat"
        regressed |= verdict == "regressed"
        detail = f"  graders now failing: {', '.join(dropped)}" if dropped else ""
        if after["errors"]:
            detail += f"  run errors: {len(after['errors'])}"
        print(f"{name:28} {before['score']:5.2f} {after['score']:5.2f} {delta:+6.2f}  {verdict}{detail}")
    return 1 if regressed else 0


if __name__ == "__main__":
    sys.exit(main())
