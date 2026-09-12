# Token usage and cost report

Generated 2026-09-12 20:24:02 UTC from `code/cache/usage.jsonl`, which records every model call made while building the cached evidence that produced the final `output.csv` (250 requests).

## Architecture recap

The decision engine is deterministic Python. The model is used for three narrow, cached jobs only:

1. `image_extraction` - one call per image in `dataset/images.csv` (16 images) to read the amount, currency, date and document type that fill the blank event amounts.
2. `message_adjustment` - one call per message in `dataset/messages.csv` (215 messages) to convert untrusted text into one structured adjustment (salary change, confirmed one-off income, pending credit, expense increase, ignore...).
3. `explanation_polish` - one call per request to rewrite the template `decision_explanation`; the rewrite is discarded unless every number and date survives.

All calls go through `code/llm.py`, which caches results under `code/cache/` (so re-runs make zero calls) and appends usage to `usage.jsonl`.

## Providers and models

| Provider | Model | Calls | Input tokens | Output tokens | Total tokens | Price (in/out per 1M) | Estimated cost (USD) |
|---|---|---:|---:|---:|---:|---|---:|
| Anthropic | `claude-sonnet-5` | 487 | 590,908 | 49,837 | 640,745 | $2.00 / $10.00 | $1.6802 |

## Overall totals

- Model calls: **487**
- Input tokens: **590,908**
- Output tokens: **49,837**
- Total tokens: **640,745**
- Average tokens per request (250 requests): **2,563.0**
- Estimated total cost: **$1.6802**
- Estimated cost per request: **$0.00672**

## Calls by job

| Model | Job | Calls | Input tokens | Output tokens |
|---|---|---:|---:|---:|
| `claude-sonnet-5` | explanation_polish | 256 | 126,628 | 14,428 |
| `claude-sonnet-5` | image_extraction | 16 | 43,208 | 5,438 |
| `claude-sonnet-5` | message_adjustment | 215 | 421,072 | 29,971 |

Cost is estimated from Anthropic list prices (input / output tokens; prompt-cache reads and writes are billed at the same rate here, i.e. conservatively). No API keys or credentials are stored in this package; the key is read from the `ANTHROPIC_API_KEY` environment variable or a git-ignored `.env` file.
