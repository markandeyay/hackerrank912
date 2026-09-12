# Token usage and cost report

Generated 2026-09-12 22:46:47 UTC from `code/cache/usage.jsonl`, which records every model call made while building the cached evidence that produced the final `output.csv` (250 requests).

## Architecture recap

The decision engine is deterministic Python. The model is used for three narrow, cached jobs only:

1. `image_extraction` - one call per image in `dataset/images.csv` (16 images) to read the amount, currency, date and document type that fill the blank event amounts.
2. `message_adjustment` - one call per message in `dataset/messages.csv` (215 messages) to convert untrusted text into one structured adjustment (salary change, confirmed one-off income, pending credit, expense increase, ignore...).
3. `explanation_polish` - one call per request to rewrite the template `decision_explanation`; the rewrite is discarded unless every number and date survives.

All calls go through `code/llm.py`, which caches results under `code/cache/` (so re-runs make zero calls) and appends usage to `usage.jsonl`.

## Final run

The final `python code/main.py` invocation (2026-09-12T22:46:45Z) processed 250 requests and made **0 new model calls**: every image and message extraction it needed was served from the cache built by the earlier extraction runs listed below. Explanation polishing (`--polish`) was **off** (the default) and made 0 `explanation_polish` calls in this run: it was evaluated on the full dataset and disabled because the template explanations scored better on the samples - the 156 rows kept on the template had zero defects, while the model rewrites introduced 18 defects (leaked meta-commentary, renamed events, style drift) and no improvement (see `code/notes/improve/5_explanations.md`); the template explanations are used.

Cached evidence that feeds the final output: image_extraction (16 calls, 48,576 tokens), message_adjustment (215 calls, 451,358 tokens).

## Providers and models

| Provider | Model | Calls | Input tokens | Output tokens | Total tokens | Price (in/out per 1M) | Estimated cost (USD) |
|---|---|---:|---:|---:|---:|---|---:|
| Anthropic | `claude-sonnet-5` | 231 | 464,280 | 35,654 | 499,934 | $2.00 / $10.00 | $1.2851 |

## Overall totals

- Model calls: **231**
- Input tokens: **464,280**
- Output tokens: **35,654**
- Total tokens: **499,934**
- Average tokens per request (250 requests): **1,999.7**
- Estimated total cost: **$1.2851**
- Estimated cost per request: **$0.00514**

## Calls by job

| Model | Job | Calls | Input tokens | Output tokens |
|---|---|---:|---:|---:|
| `claude-sonnet-5` | image_extraction | 16 | 43,208 | 5,368 |
| `claude-sonnet-5` | message_adjustment | 215 | 421,072 | 30,286 |

Cost is estimated from Anthropic list prices (input / output tokens; prompt-cache reads and writes are billed at the same rate here, i.e. conservatively). No API keys or credentials are stored in this package; the key is read from the `ANTHROPIC_API_KEY` environment variable or a git-ignored `.env` file.
