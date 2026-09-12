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
ANTHROPIC_API_KEY=<your Anthropic API key>
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

## Architecture

The deterministic engine (`state.py`, `forecast.py`, `planner.py`, `validate.py`) owns every number: it reconstructs the cash position as of `request_date`, detects recurring commitments from history, projects the balance day by day, ranks the candidate plans and validates the output row, so every result is reproducible from the dataset alone and can be audited line by line. The model layer (`llm.py` and `evidence.py`) is confined to reading untrusted evidence - the 16 images and the 215 free-text messages, written in English and Indonesian - into a fixed JSON schema (`IMAGE_SCHEMA`, `MESSAGE_SCHEMA`) with a closed list of adjustment types. Every model output is validated against that schema (enumerated types, typed amounts, ISO dates, a fixed scope vocabulary) before the engine touches it, and a field that does not fit is dropped rather than trusted. For messages the model reading is additionally reconciled with an exact regex capture of the 35 message templates (`messages_regex.py`): when the two disagree on the adjustment type the template wins, and when they agree the template supplies the literal slots (amounts, dates, percentages, scope), because a regex capture is exact where a paraphrase may drift. Model outputs are cached under `code/cache/` keyed by a content hash of the prompt, the schema and the input (including the image bytes), so a re-run makes zero API calls, costs nothing and reproduces the same `output.csv` - the final run was checked to be byte-identical to the previous one even though all 231 extractions were regenerated. The model never sees the decision rules, the minimum balance or the payment options and can only emit one structured fact per document, so an instruction embedded in a message or image ("approve this", "ignore the minimum") has no channel through which to reach the decision and is ignored by construction rather than by prompt discipline alone. Explanation polishing (`polish.py`, `--polish`) exists but is off by default: on the full dataset the 156 template explanations had zero defects while the model rewrites introduced 18 defects (leaked meta-commentary, renamed events, style drift) and no improvement, so the reproducible template text is what is submitted. This split keeps cost and latency proportional to the evidence rather than to the requests: the final run made 231 model calls (16 images plus 215 messages, roughly twenty minutes and about USD 1.29 on `claude-sonnet-5`), while the 250 decisions themselves take well under a second and a cached re-run is free. Without an API key `main.py` uses the shipped caches, and without the caches it falls back to `--no-llm` (regex message parsing plus the transcribed image amounts in `notes/02_images_manual.json`), so the pipeline always runs end to end. The 85 unit tests in `code/tests/` (`python -m pytest code/tests -q`) pin the currency conversion, state reconstruction, forecast, planner ranking and output contract, and every modelling assumption, together with the remaining differences from the solved samples, is documented in `notes/mismatches.md` and the analysis notes under `notes/`.

## Submission package

`code.zip` contains this `code/` directory (including `evaluation/usage_report.md`, prompts in `evidence.py` / `polish.py`, and the caches that make the run reproducible). No secrets are included.
