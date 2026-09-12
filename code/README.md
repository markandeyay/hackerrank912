# Buy or Wait? - solution

An AI-assisted financial decision agent for the HackerRank Orchestrate challenge. For every row in `dataset/requests.csv` it reconstructs the user's cash position, forecasts the balance day by day, and recommends `full_payment`, `partial_payment`, `installments`, `wait` or `not_recommended`, writing `output.csv` in the repository root.

## Setup

```bash
python -m venv .venv
.venv/Scripts/pip install -r code/requirements.txt      # Windows
# source .venv/bin/activate && pip install -r code/requirements.txt   # macOS / Linux
```

Create a `.env` file in the repository root (git-ignored) or export the variable:

```text
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-5
```

Python 3.10+ is required (developed on 3.14). Dependencies: `pandas`, `anthropic`, `python-dotenv`, `pillow`; `pytest` (in `requirements-dev.txt`) for the tests.

## Run

```bash
python code/main.py                 # full run: model-extracted evidence (cached under code/cache/), template explanations
python code/main.py --polish        # opt-in: rewrite explanations with the model (kept only when every fact survives)
python -m pytest code/tests -q      # unit tests (pytest from requirements-dev.txt)
python code/main.py --no-llm        # fully deterministic: regex message parsing + transcribed image amounts, no API calls
python code/validate.py             # re-check output.csv against the output contract
python code/evaluation/main.py -v   # score the engine against the 25 solved samples
python code/evaluation/usage_report.py   # regenerate evaluation/usage_report.md from code/cache/usage.jsonl
python code/debug_request.py request_42  # print the reconstructed state and daily projection for one request
```

Every model result is cached as JSON under `code/cache/` (keyed by a content hash of the input), so a second run makes no API calls and is fully reproducible. If the key is missing but the cache is present, `main.py` uses the cache; if neither exists it falls back to `--no-llm` automatically.

## How it works

| Module | Role |
|---|---|
| `data.py` | Loads and joins the dataset; exchange-rate lookup by settlement date and stated direction (inverse pair as fallback). |
| `llm.py` | The single Claude API wrapper (model from `ANTHROPIC_MODEL`, default `claude-sonnet-5`): JSON-schema output, on-disk cache, `usage.jsonl` token log. |
| `evidence.py` | Two narrow model jobs: amount/date extraction from the 16 images, and one structured adjustment per message (fixed schema: salary amount/date change, one-time confirmed income, income ended, unconfirmed income, pending credit, expense increase, transfer/dispute/scam/duplicate ignore, no effect). All content is treated as untrusted data; embedded instructions are never followed. |
| `messages_regex.py` + `message_templates.json` | Deterministic regex fallback for the 35 message templates; also fills fields the model leaves empty. |
| `state.py` | Financial state as of `request_date`: reserves pending/scheduled debits at settlement date; ignores pending credits, refunds, failed/cancelled rows, duplicates and unrealized values; resolves `linked_event_id` chains; fills blank amounts from the image cache; detects recurring debit series per category (monthly on the same day of month, or shorter cycles at the observed gap) at the historical mean; projects salary from the scheduled row or the settled payroll history and applies message adjustments. |
| `forecast.py` | Daily balance for the forecast window; `amount_safe_to_pay` (largest amount payable today that keeps every projected day above `minimum_balance_to_keep`), `earliest_date_for_full_payment` (first day a single full payment stays safe for the rest of the window). |
| `planner.py` | Candidate plans (full, partial with exactly two payments, installments exactly matching a supplied option within `max_installment_months`, wait, full/installments with at most three greedy spending changes on flexible, non-protected, permitted events) ranked by: completes by deadline, no spending changes, lowest total paid, earliest start, fewest payments, lowest option id. |
| `explain.py` / `polish.py` | Explanations in the style of `sample_requests.csv`; optional model rewrite that must preserve every number and date. |
| `validate.py` | Every output constraint from `problem_statement.md`. |
| `evaluation/main.py` | Per-column scoring against the 25 samples. |

Assumptions and the remaining differences from the solved samples are documented in `notes/mismatches.md`; the analysis notes that drove the design are in `notes/`.

## Submission package

`code.zip` contains this `code/` directory (including `evaluation/usage_report.md`, prompts in `evidence.py` / `polish.py`, and the caches that make the run reproducible). No secrets are included.
