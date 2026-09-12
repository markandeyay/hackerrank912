"""Generate evaluation/usage_report.md from code/cache/usage.jsonl.

Run after the final full-dataset run:  python code/evaluation/usage_report.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE_DIR))

from data import DATASET_DIR  # noqa: E402
from llm import MODEL, PRICING, USAGE_PATH, usage_summary  # noqa: E402

OUT = CODE_DIR / "evaluation" / "usage_report.md"


def main() -> None:
    n_requests = sum(1 for _ in open(DATASET_DIR / "requests.csv", encoding="utf-8")) - 1
    s = usage_summary(n_requests)
    lines = [
        "# Token usage and cost report",
        "",
        f"Generated {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())} from `code/cache/usage.jsonl`, which records every model call made while building the cached evidence that produced the final `output.csv` ({n_requests} requests).",
        "",
        "## Architecture recap",
        "",
        "The decision engine is deterministic Python. The model is used for three narrow, cached jobs only:",
        "",
        "1. `image_extraction` - one call per image in `dataset/images.csv` (16 images) to read the amount, currency, date and document type that fill the blank event amounts.",
        "2. `message_adjustment` - one call per message in `dataset/messages.csv` (215 messages) to convert untrusted text into one structured adjustment (salary change, confirmed one-off income, pending credit, expense increase, ignore...).",
        "3. `explanation_polish` - one call per request to rewrite the template `decision_explanation`; the rewrite is discarded unless every number and date survives.",
        "",
        "All calls go through `code/llm.py`, which caches results under `code/cache/` (so re-runs make zero calls) and appends usage to `usage.jsonl`.",
        "",
        "## Providers and models",
        "",
        "| Provider | Model | Calls | Input tokens | Output tokens | Total tokens | Price (in/out per 1M) | Estimated cost (USD) |",
        "|---|---|---:|---:|---:|---:|---|---:|",
    ]
    for name, m in sorted(s["per_model"].items()):
        lines.append(
            f"| {m['provider']} | `{name}` | {m['calls']} | {m['input_tokens']:,} | {m['output_tokens']:,} | {m['input_tokens'] + m['output_tokens']:,} | ${m['price']['input']:.2f} / ${m['price']['output']:.2f} | ${m['cost_usd']:.4f} |"
        )
    if not s["per_model"]:
        lines.append(f"| Anthropic | `{MODEL}` | 0 | 0 | 0 | 0 | ${PRICING[MODEL]['input']:.2f} / ${PRICING[MODEL]['output']:.2f} | $0.0000 |")
    lines += [
        "",
        "## Overall totals",
        "",
        f"- Model calls: **{s['calls']}**",
        f"- Input tokens: **{s['input_tokens']:,}**",
        f"- Output tokens: **{s['output_tokens']:,}**",
        f"- Total tokens: **{s['total_tokens']:,}**",
        f"- Average tokens per request ({n_requests} requests): **{s['avg_tokens_per_request']:,.1f}**",
        f"- Estimated total cost: **${s['cost_usd']:.4f}**",
        f"- Estimated cost per request: **${s['avg_cost_per_request']:.5f}**",
        "",
        "## Calls by job",
        "",
        "| Model | Job | Calls | Input tokens | Output tokens |",
        "|---|---|---:|---:|---:|",
    ]
    for name, m in sorted(s["per_model"].items()):
        for kind, k in sorted(m["by_kind"].items()):
            lines.append(f"| `{name}` | {kind} | {k['calls']} | {k['input_tokens']:,} | {k['output_tokens']:,} |")
    lines += [
        "",
        "Cost is estimated from Anthropic list prices (input / output tokens; prompt-cache reads and writes are billed at the same rate here, i.e. conservatively). No API keys or credentials are stored in this package; the key is read from the `ANTHROPIC_API_KEY` environment variable or a git-ignored `.env` file.",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({s['calls']} calls, {s['total_tokens']:,} tokens, ${s['cost_usd']:.4f}) from {USAGE_PATH}")


if __name__ == "__main__":
    main()
