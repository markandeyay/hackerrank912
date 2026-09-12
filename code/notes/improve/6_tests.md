# 6 - Unit tests and clean-clone verification

## Running the tests

```bash
.venv/Scripts/python -m pip install pytest      # dev-only dependency; not in code/requirements.txt
.venv/Scripts/python -m pytest code/tests -q    # 84 passed in ~1 s
```

`pytest` is a development dependency only. The owner should add a `requirements-dev.txt` (or a comment
line) with `pytest>=8`; `code/requirements.txt` was deliberately left untouched.

`code/tests/conftest.py` puts `code/` on `sys.path` and provides synthetic fixtures (`FakeDataset`,
`make_event`, `make_profile`, `make_request`, `make_option`, `make_state`) plus a session-scoped real
`Dataset()` fixture (`ds`) for the integration checks. No engine file was modified.

## Test list (all passing)

| File | Tests | What is covered |
|---|---|---|
| `test_currency.py` | 9 | same currency; direct `(date, from, to)` rate; inverse pair fallback; direct wins over inverse; nearest earlier date; earliest date when before the first rate; nearest-date via inverse; `KeyError` on unknown pair; three real-dataset pairs |
| `test_state.py` | 27 | `add_months` day clamping; monthly same-DOM series with the request-date occurrence counted; mean amount; 7/10/14-day periodic series at last+step with the request-date occurrence skipped (and not skipped when the option is off); `<3` rows and `>45`-day gaps are not series; `investment`/`refund` rows excluded; "at least once before first payday" (moved to payday-1, rest of cycle unchanged, off-switch, left alone when already before payday); pending debit reserved at settlement date / at request date when already past; pending credit ignored; failed/cancelled/unrealized ignored; `non_cash` ignored; pending "Possible duplicate card charge" linked row ignored; scheduled debit reserved and scheduled non-salary credit ignored; scheduled retry of a failed debit reserved once; `payment_delayed` message reserves a failed debit without a retry row exactly once (and not twice when the retry row exists); refund pairs excluded from recurrence history and from the mean; blank amount without image ignored (never zero); blank amount filled from the image extraction; foreign event converted with the settlement-date rate; scheduled salary projected monthly inside the window |
| `test_forecast.py` | 11 | daily balances net same-day flows over 85 days; flows outside the window ignored; `amount_safe_to_pay == trough - min` clipped to `[0, requested]`; consistency with `is_safe` (safe passes, safe+0.02 fails); closed form equals a bisection over `is_safe` on four synthetic states; `earliest_full_payment_date` first safe day / `None` when never / `== request_date` when safe >= requested; earliest date lies after a later dip and `is_safe` confirms it (day before fails) |
| `test_planner.py` | 17 | partial payment: exactly two payments summing to `requested` (`safe` today, rest on `earliest`); not when the request disallows it, the user rejects it, `earliest > desired`, or `safe == 0`; full payment `affordable_now` when safe today; `not_recommended` when nothing works; `wait` requires `full_payment` acceptance; `installment_eligible` (method match, user accepts, blank max => never, `n <= max`); plan follows the supplied option schedule exactly; option beyond `max_installment_months` rejected; option starting before `request_date` skipped; cheaper total beats earlier start, fewer payments beats more on a tie; `spending_change_candidates` rules (protected excluded, stop needs stoppable+willing, reduce needs reducible+willing+`min < amount`, reduce preferred over stop, never both, cheapest first, `as_string` format); greedy skips changes that do not raise the trough; `[]` when already safe, `None` when four changes would be needed, exactly three when three suffice; full payment with a stop is `affordable_with_plan` and `amount_safe_to_pay` is computed before the change; `Plan.rank_key` order (deadline, no changes, total paid, start, count, option id) |
| `test_output.py` | 18 | `fmt_amount` (620.4 -> "620.40", 25256 -> "25256", 23.5 -> "23.50", rounding); `fmt_safe` (17229139.2 -> "17229139.2", 25256.0 -> "25256"); `validate_rows` accepts the 25 sample rows unchanged and flags three deliberately broken rows; dataset shape (250 unique requests, 2-4 options each, every blank amount has an image); `--no-llm` pipeline on `sample_requests.csv` is valid, deterministic across two runs and at least at the current score (status 24/25, method 24/25, plan 23/25, earliest 23/25, changes 23/25, safe exact 4/25, within 2 % 16/25); `regex_adjustment` on `message_01` (T01 salary increase, 42 750 000 IDR from 2025-08-15) |

Two initial failures were arithmetic mistakes in the tests (trough with three series debits; 2024-06-25 is
past the 84-day window), fixed on the test side.

## Engine findings (no engine file changed)

1. **`code/__init__.py` shadows the standard-library `code` module.** `python -m pytest` puts the cwd on
   `sys.path`, so `import pdb` (pytest's debugging plugin) fails with
   `AttributeError: module 'code' has no attribute 'InteractiveConsole'`. Nothing imports `code` as a
   package (all modules do `sys.path.insert(0, CODE_DIR)`), so the empty file has no purpose.
   Proposed fix: `git rm code/__init__.py`. Until then `conftest.py` strips the repo root from `sys.path`
   and re-imports the stdlib module, so the suite runs with both `python -m pytest` and `pytest`.
2. **`validate.py` never checks the `wait` plan amount** (`validate.py:156`):
   `abs(plan[0][1] - req.requested_amount) > -1` is always true. Proposed one-line fix:
   `abs(plan[0][1] - req.requested_amount) <= EPS`. Current outputs still pass with the fix (the planner
   always writes `requested_amount`).
3. Robustness nit, `state.py:209`: `failed_with_retry` does `ds.events[e.linked_event_id]` and would
   `KeyError` on a dangling `linked_event_id` (none in this dataset). Proposed:
   `ds.events.get(e.linked_event_id) is not None and ds.events[e.linked_event_id].status == "failed"`.
4. Readability nit, `state.py:306`: the `expense_increase_percent` filter ends in `or True`, so every
   percentage increase message is applied to rent whatever its target. Intentional per the notes, but the
   dead condition should be removed or the comment made explicit.
5. Design limitation (not a bug): `greedy_changes` is cheapest-first, so a set of three larger changes
   that would work can be missed when three cheaper-but-insufficient ones are chosen first
   (`test_greedy_returns_empty_when_already_safe_and_none_when_over_three` documents the current
   behaviour with equal amounts only).

## Clean-clone verification

Clone: `git clone C:/Users/yalam/hackerrank912 C:/Users/yalam/AppData/Local/Temp/bow_clean` (0.4 s). The clone
has no `.env` and no `code/cache/` (both git-ignored); `code/notes/02_images_manual.json` is tracked, so the
deterministic image fallback is available. Fresh venv with `C:/Python314/python -m venv .venv` (8.5 s),
`pip install -r code/requirements.txt` (79 s, no missing dependency; pip 25.3 notice only).

| Step | Result | Time |
|---|---|---|
| `python code/main.py --no-llm` (no `.env`, no cache) | 250 rows, `VALIDATION: all rows valid`; methods full 70 / wait 61 / not_recommended 46 / installments 63 / partial 10 | 12 s |
| `python code/main.py` with no `.env` and no cache | prints `ANTHROPIC_API_KEY not set and no cache present: falling back to deterministic extraction (--no-llm).`, then the same valid output | 12 s |
| copy repo `.env` into the clone, `python code/main.py --no-polish` with EMPTY `code/cache/` | exit 0, 250 rows valid, same method/status counts; `code/cache/{images.json,messages.json,usage.jsonl}` created | 572 s |

Model calls in the empty-cache run: 231 (16 `image_extraction` + 215 `message_adjustment`, all
`claude-sonnet-5`), 464 280 input + 35 174 output tokens, about USD 1.28 at list price. No polish calls were
made (as instructed), so the clone's `usage.jsonl` is not the final-run report.

Output comparison (`output_nopolish.csv` vs the repo's `output.csv`): **0 differences in the six decision
columns for all 250 requests**; 94 rows differ only in `decision_explanation` (the repo file is polished, the
clone used template explanations). The clone's API output also matches its own `--no-llm` output in every
column (decisions and template explanations), i.e. the model evidence currently changes no decision.

Model non-determinism observed at the evidence level, absorbed by the merge: the fresh `messages.json`
disagrees with the repo cache on 2/215 adjustment types (one `salary_amount_change` vs
`one_time_confirmed_income`, one `no_effect` vs `unconfirmed_income`) and the fresh `images.json` swaps
`amount`/`alternative_amount` (8528 vs 8528.1) on one image; because `pipeline.merge_adjustment` takes the
regex-template record on a type mismatch and the image amount only fills a blank event, none of this reached
`output.csv`. Nothing in the main repo was modified or deleted; the clone is left at
`C:/Users/yalam/AppData/Local/Temp/bow_clean` (contains a copy of `.env`; delete it when done).
