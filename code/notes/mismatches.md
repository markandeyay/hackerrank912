# Sample mismatches and assumption differences

Score of the deterministic engine against `dataset/sample_requests.csv` (25 rows), run with
`python code/evaluation/main.py -v`:

| column | exact matches |
|---|---|
| affordability_status | 23 / 25 |
| recommended_payment_method | 24 / 25 |
| payment_plan | 23 / 25 |
| earliest_date_for_full_payment | 22 / 25 |
| spending_changes_needed | 22 / 25 |
| amount_safe_to_pay exact | 4 / 25 (the four capped at `requested_amount`) |
| amount_safe_to_pay within 2 % | 11 / 25 |
| overall exact (6 scored columns) | 118 / 150 (78.7 %) |

Nothing is hardcoded per request; every number comes from the dataset through the rules in `state.py` / `planner.py`.

## Why `amount_safe_to_pay` cannot match exactly

The organizers' reserve (balance − minimum − answer) is always a round number (13,996,350; 2,268,600; 452; 487; 1,134; 624 ...) while the histories carry cents. The reference therefore uses the generator's hidden nominal amounts for variable expenses (utilities, groceries, transport, dining, shopping, healthcare vary ±15-20 % month to month). We use the historical mean, which is the closest estimator among mean / median / last / last-3 / max / mean+std / p75 (grid-searched in `notes/04_sample_rules.md` and again on the final engine). The residual is a few percent of the reserved amount and is irreducible from the supplied data.

## Assumptions that differ from a literal reading of the statement

1. **Forecast window = 84 days** (12 weeks) instead of 90. With 90 days, samples 03, 12 and 13 contradict the published answers because a rent on day 87 is counted; 84-86 days reproduce all three. `HORIZON_DAYS` in `state.py` makes this a one-line change.
2. **Same-day netting on payday.** Salary landing on a day is available for that day's debits (sample 19: the family-support debit on payday is not reserved; sample 25 likewise). Sample 18 is the lone counter-example (its dining on payday is reserved) and is accepted as a mismatch.
3. **Short-cycle series** (5/7/10/14/21-day groceries, transport, dining) recur at `last + median gap`, and an occurrence that would fall exactly on `request_date` is skipped (samples 15, 23, 25). Monthly series recur on the same day of month and an occurrence on `request_date` is counted (samples 08, 19).
4. **Blank-amount rows** take the image amount everywhere, but are excluded from recurrence means (they are one-off documents: a bulk grocery invoice, a hospital bill, a taxi receipt). This improves samples 17 and 19.
5. **Salary regime rules.** A `scheduled` "Next confirmed salary" row anchors the monthly series; otherwise the settled payroll history does (modal day of month, regular amount = modal amount of the latest payroll description, so a one-off reduced or prorated month does not become the forecast). "Final employer payroll", seasonal-contract-ended and employment-ended messages stop income. Commissions, bonuses, arrears, prizes, refunds, unrealized gains and "Second household income" are never projected. The "confirmed base salary" in commission-pending messages restates the payroll on another basis (exactly 5/3 of the settled base in all nine instances); the settled base is used (sample 11).
6. **Installment eligibility**: `number_of_payments <= max_installment_months` (one supplied payment = one month; cadences are 28/30/31 days). Three evaluation requests have 3 × 31-day options against a cap of 3; they are treated as eligible.
7. **Status follows the chosen method**: `not_recommended` → `not_affordable` even when a later full payment exists but no accepted method can deliver it (samples 14, 24).
8. **`wait` past the deadline** is still recommended (as `affordable_later`) when it is the only safe eligible plan; ranking rule 1 orders plans, it does not filter them.

## Remaining per-sample differences

| sample | difference | cause |
|---|---|---|
| request_06 | `wait` instead of `full_payment` + `stop:event_476` | Our reserve is 52 EUR (9 %) higher than the reference's (two weekly dining occurrences vs one), so stopping the 19 EUR streaming plan is not enough in our forecast. |
| request_11 | earliest 2025-06-15 vs 2025-07-15; changes `stop:event_949|reduce_to:event_989:665950` vs `reduce_to:event_989:665950` | Reserve differs by 1.1 % (variable-expense noise), so the greedy change search also needs the cloud-storage stop; the June full payment passes by 1.5 % in our forecast. |
| request_17 | earliest 2026-04-15 vs 2026-03-15 | The March full payment fails by 0.5 % of the monthly spend in our forecast. |
| request_19 | partial split 29,948.97 / 9,711.03 vs 28,820 / 10,840 | `amount_safe_to_pay` differs by 1.6 % of the reserve; the plan format and dates are identical. |
| request_21 | `affordable_now` (safe = requested) vs `affordable_with_plan` with two spending changes | Reference reserves 568 USD, we reserve 537 (the request is 2 % from the boundary). |
| request_02, 03, 04, 10, 13, 20, 23 | `amount_safe_to_pay` off by 5-20 % of the reserve | Hidden nominal amounts; request_04 and request_20 also seem to include one extra weekly occurrence we do not place before payday. |
| request_05, 07, 08, 14, 15, 18, 22, 24, 25 | `amount_safe_to_pay` within 0.1-2 % of the reserve | Noise only. |

## Message and image interpretation

* Every one of the 215 messages matches one of 35 generator templates (`message_templates.json`); the model extraction (`evidence.py`) and the regex fallback agree on the adjustment type in the final run, and any field the model leaves empty is filled from the regex capture.
* Two advance-fee scam messages instruct the reader to pay a "release charge"; they are classified `scam_ignore` and never reach the forecast.
* image_05 shows 704.05 due by 6 Feb and 822.05 after; the event settles on 9 Feb. Sample 20's answer ends in `.05`, which confirms the 704.05 figure is the one to use.
