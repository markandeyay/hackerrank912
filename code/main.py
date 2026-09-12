"""Buy or Wait? - entry point.

    python code/main.py                # full run: model-extracted evidence (cached), polished explanations
    python code/main.py --no-llm       # fully deterministic run (regex message parsing, transcribed image amounts)
    python code/main.py --no-polish    # model evidence but template explanations only

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


def main() -> int:
    ap = argparse.ArgumentParser(description="Buy or Wait? decision engine")
    ap.add_argument("--no-llm", action="store_true", help="do not call the Claude API; use the deterministic fallbacks")
    ap.add_argument("--no-polish", action="store_true", help="keep template explanations (no explanation model calls)")
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
    results = run(reqs, ds, use_llm=use_llm, horizon_days=args.horizon, polish=(use_llm and not args.no_polish))
    rows = [row for _, row in results]

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
