"""Buy or Wait? - entry point.

    python code/main.py                # full run: model-extracted evidence (cached), template explanations
    python code/main.py --no-llm       # fully deterministic run (regex message parsing, transcribed image amounts)
    python code/main.py --polish       # additionally rewrite explanations with the model (opt-in; the template is kept unless every fact survives)

Reads dataset/, writes output.csv in the repository root and validates it.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))

from data import REPO_ROOT, Dataset  # noqa: E402
from llm import CACHE_DIR, api_key_available  # noqa: E402
from pipeline import run  # noqa: E402
from state import HORIZON_DAYS  # noqa: E402
from validate import COLUMNS, validate_rows  # noqa: E402


def _usage_lines() -> int:
    from llm import USAGE_PATH

    if not USAGE_PATH.exists():
        return 0
    with open(USAGE_PATH, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def _write_last_run(n_requests: int, use_llm: bool, polish: bool, new_calls: int) -> None:
    import json
    import time

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_DIR / "last_run.json", "w", encoding="utf-8") as f:
        json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n_requests": n_requests, "use_llm": use_llm, "polish": polish, "new_model_calls": new_calls}, f, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser(description="Buy or Wait? decision engine")
    ap.add_argument("--no-llm", action="store_true", help="do not call the Claude API; use the deterministic fallbacks")
    ap.add_argument("--polish", action="store_true", help="rewrite explanations with the model (opt-in)")
    ap.add_argument("--no-polish", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--requests", default="requests.csv", help="requests file inside dataset/ (default requests.csv)")
    ap.add_argument("--out", default=str(REPO_ROOT / "output.csv"))
    ap.add_argument("--horizon", type=int, default=HORIZON_DAYS)
    args = ap.parse_args()

    use_llm = not args.no_llm
    if use_llm and not api_key_available():
        have_cache = (CACHE_DIR / "images.json").exists() and (CACHE_DIR / "messages.json").exists()
        if have_cache:
            print("ANTHROPIC_API_KEY not set: using the cached model extractions only (no new calls).")
        else:
            print("ANTHROPIC_API_KEY not set and no cache present: falling back to deterministic extraction (--no-llm).")
            use_llm = False

    ds = Dataset()
    reqs = ds.load_requests(args.requests)
    polish = use_llm and args.polish and not args.no_polish
    calls_before = _usage_lines()
    results = run(reqs, ds, use_llm=use_llm, horizon_days=args.horizon, polish=polish)
    rows = [row for _, row in results]
    _write_last_run(len(reqs), use_llm, polish, _usage_lines() - calls_before)

    out = Path(args.out)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote {len(rows)} rows to {out}")

    problems = validate_rows(rows, ds, args.requests)
    if problems:
        print(f"VALIDATION: {len(problems)} problem(s)")
        for p in problems[:50]:
            print(" -", p)
        return 1
    print("VALIDATION: all rows valid")
    from collections import Counter

    print("methods:", dict(Counter(r["recommended_payment_method"] for r in rows)))
    print("statuses:", dict(Counter(r["affordability_status"] for r in rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
