# Notes index

Analysis and audit reports that drove the engine design. Nothing here is executed by `main.py`; the engine reads only
`02_images_manual.json` (fallback image amounts when there is no API key and no cache) and `../message_templates.json`.

## Initial analysis (session start)

| file | what it is |
|---|---|
| `01_dataset_profile.md` | Schema, value distributions, status semantics, linked-event chains, recurrence patterns and gotchas of every CSV in `dataset/`. |
| `02_images.md`, `02_images_manual.json` | Manual reading of the 16 images (document type, amounts, dates) next to the event each one documents; the JSON is the offline fallback for blank amounts. |
| `03_messages.md`, `03_message_regexes.json`, `03_messages_parsed.json` | The 35 message templates (English and Indonesian), what each implies for the forecast, the regexes that capture their slots, and all 215 messages parsed. |
| `04_sample_rules.md`, `04_sample_reconstruction.json`, `04_sample_sim_prototype.py` | Reverse-engineering of the 25 solved samples: the rules the reference appears to follow and the per-sample arithmetic. |
| `mismatches.md` | The living record: score per column after each pass, every assumption that differs from a literal reading of the statement, and every remaining sample difference with its cause. |

## `experiments/` (first mismatch pass)

| file | what it is |
|---|---|
| `trace_request_06/11/17/19/21.md` | End-to-end trace of each sample that missed a column: state, daily series, binding day, candidate plans, and the single rule that differs. |
| `reserve_hypotheses.md` | Grid of reserve estimators and scheduling rules (rounding, max, last-month sums, monthly-only, per-cycle caps, payday ordering) scored on all 25 samples. |
| `horizon_test.md` | 84- vs 90-day window on all 25 samples with the per-sample evidence. |

## `improve/` (pass 1: six audits)

| file | what it is |
|---|---|
| `1_reserve_model.md` | `minimum_allowed_amount` leaks the generator's nominal amount (factor 2.0 / 2.5 per category); adopted. |
| `2_invariants.md`, `audit_invariants.py` | Independent cross-column invariant audit of all 250 output rows (0 violations); the script is re-run before every commit. |
| `3_evidence_audit.md` | Every message and image adjustment traced with/without on the state; no missing, doubled or wrong-direction application. |
| `4_outliers.md` | Status/method mix vs the samples and a debug of 65 flagged rows (0 bugs). |
| `5_explanations.md`, `check_explanations.py` | Explanation audit of all 250 rows; why model polishing was disabled. |
| `6_tests.md` | The unit-test suite and the clean-clone run (with and without cache). |

## `improve2/` (pass 2: generator calibration)

| file | what it is |
|---|---|
| `1_noise_band.md` | Uniform noise band around the nominals (0.28 / 0.12 half-widths), currency grid, and the band-clamped estimator; adopted. |
| `2_exact_interval.md` | Every short-cycle series has a constant gap; the engine is already the exact-interval projection. |
| `3_fixed_dates.md` | Salary and monthly-series date audit on all 275 users (0 violations). |
| `4_final_run.md`, `output_before_final_run.csv` | The real extraction run (231 calls) and its byte-identity check against the cached run. |

## `improve3/` (pass 3: reverse-engineering and boundaries)

| file | what it is |
|---|---|
| `1_residual_backsolve.md` | Reference reserve minus every certain item, per sample, and the hypothesis scoreboard (none explains 20 of 25). |
| `2_occurrence_counts.md` | Implied occurrence counts for the eight remaining misses and 34 scheduling rules scored; the request_date+1 skip was adopted. |
| `3_sensitivity.md` | Hidden rows whose decision flips when variable reserves move by 1 % / 3 %, with margins and the safer outcome per row (not applied; see `mismatches.md`). |
| `4_edge_cases.md` | Twelve edge-case categories on the hidden set (ended income, first salaries, foreign salaries, the installment cap, deadline-missing waits, ...); all consistent. |
