# Audit 3: salary and fixed-date (monthly) projections

Script: `code/notes/improve2/audit_fixed_dates.py` (deterministic evidence path only:
`load_image_amounts(ds, False)`, `load_adjustments(ds, False)`, `StateBuilder(...).build(req)`).
Outputs: `audit_fixed_dates.out` (25 samples + 30 hidden users, `random.Random(7).sample`) and
`audit_fixed_dates_all.out` (`ALL=1`: all 25 samples + all 250 hidden requests).

## Coverage

| set | requests | scheduled-salary users | history-salary users | no regular payroll | monthly debit series checked |
|---|---|---|---|---|---|
| 25 samples + 30 hidden (seed 7) | 55 | 9 | 44 | 2 | 335 |
| everything | 275 | 47 | 198 | 30 | 1644 |

Freelance streams: 19 users, gig streams: 11 users (all 275).

## 1. Scheduled salary ("Next confirmed salary" row) - no violations

For all 47 users with a scheduled row: the first salary flow lands on the row's `settlement_date`
with the row's amount converted at that date (8 foreign-currency rows, e.g. user_25 1800 USD -> IDR,
user_257 1793 EUR -> USD, all converted with the settlement-date rate); later flows are
`add_months(first, k)`; no month carries two salary flows (the history projection is never added
on top of the scheduled row because `_build_income` takes the `scheduled is not None` branch
exclusively). Scheduled DOM is 15 for 46 rows and 23 for user_86 (whose last settled payroll
already moved to 07-23); the scheduled row wins, as designed. No message moves a scheduled row.

## 2. History-based salary - no violations

198 users. For every one: modal event-date DOM == modal settlement DOM (always 15), the first
projected date is >= request_date and is the first DOM-15 date after the last settled payroll, the
amount equals the modal amount of the latest payroll description (or the message amount), no
duplicate months. No salary history has a DOM >= 29 anywhere in the dataset, so month-end clamping
of salaries is never exercised (the code path `min(dom, monthrange)` is correct anyway).

Message-driven moves/resizes (102 entries in the full run, all matching the message):

* T05 salary_date_change (user_07 sample, 68, 95, 131, 167, 194, 212): last payroll already on the
  23rd; engine projects 23rd for the next AND following months (`add_months(first_date, k)`).
  Sample request_07 expects `earliest_date_for_full_payment = 2024-10-23`, i.e. the reference also
  keeps the 23rd for the second month. Consistent.
* T04 / T06 next_payment_only (user_06, 08, 49, 175 ...): first month uses the message amount
  (or the settled reduced amount), later months revert to the modal amount. Correct.
* T01 / T09 / T10 / T11 permanent with effective_date: series starts on that date. Correct.
* T07 commission pending (user_11, 80, 108): base salary kept, commission excluded. Correct.
* T14 regular_plus_arrears (user_163): arrears 13,680,000 IDR already settled as event_14948 on
  2024-08-20 -> not counted again; regular 30,400,000 projected. Correct.
* T15 household income ended (user_42, 50, 58, 154, 230, 238, 262): message amount used as the
  single stream (e.g. user_50: 78,120 primary -> 126,000 "remaining confirmed"). "Second household
  income" is never projected on its own (mismatches.md, supported by sample request_13). Note the
  T15 amount is larger than the settled primary payroll; it is what the message states, so no change.

Freelance (step = median gap, e.g. user_09: 13 days, mean amount) and gig streams: first date is
the first step after the last settlement that is > request_date; amounts equal the mean. No violations.
user_10's gig payouts are correctly suppressed by a `pending_credit_not_available` message.

## 3. Monthly debit series - dates and amounts: no violations; overlaps listed

1644 monthly series (all 275 requests): every projected date is on the history DOM; the first
projection is >= request_date (an occurrence ON request_date is counted, e.g. user_05 utilities
2025-11-06, user_06 rent 2026-01-03, user_19 rent 2024-09-04) and is `add_months(last_history, 1)`
stepped forward to request_date; no series is built when the median gap > 45 days or n < 3.

History day-of-month constancy: 11 (user, category) pairs in the whole dataset have a second
row in one month (user_26, 73, 77, 120, 138, 156, 167, 210, 214, 221, 275 - all `shopping`).
Every odd row is a "Card charge later reversed" / "Settled card charge reversal" pair, an
"Original card charge" that is the linked target of a "Possible duplicate card charge", or a
blank-amount image row; the engine already excludes linked rows / linked targets / image rows
(n_hist = 5, projections on the modal DOM). Nothing to fix.

Amounts: constant series (rent, insurance, debt, subscriptions, education ...) use the constant
(user_16 rent 57,100 x 1.12 = 63,952 per the T19 message); variable monthly series use the mean or
the nominal recovered from `minimum_allowed_amount` (within 0.6-1.4 x mean). No violations.

### Scheduled / pending rows in a category that also has a series (35 cases, all 275 requests)

The engine reserves BOTH the known row and the recurring projection. Evidence that this is the
intended reading:

* sample request_24 (user_24): "Scheduled insurance payment" 1,830 on 01-11 + insurance series
  2,510 on 01-06. Engine safe 13,603.32 vs expected 13,420; dropping either row would move the
  engine further away (15,433 / 16,113). Both counted is supported.
* sample request_04 (user_04): "Scheduled school fee" 1,704,300 on 06-11; user_04 has NO other
  education row, so no series and no overlap. (request_04's +2.2M gap vs expected is the payday
  grocery/transport issue already documented in mismatches.md, not a fixed-date issue.)
* sample request_16: "Outstanding rent balance" 100,000 on 08-16 + rent series from 09-01 (different
  months). Engine == expected exactly.
* sample request_23: "Pending pharmacy card charge" 1,553.20 on 05-11 + healthcare "Clinic
  payment" series 1,361.55 on 05-12. Engine 9,248.35 vs expected 9,152 (dropping the pending row
  would give ~10,800, further away).
* user_253 (hidden): failed 192 EUR on 03-05 + "Scheduled bill payment retry" 192 on 03-11 AND a
  settled "Electricity bill" 186.20 on 03-06 in the same month -> the generator's failed/retry row is
  an extra obligation, not the month's regular bill. So for the other retry users (55, 91, 139, 181,
  229, 259: retry on 09-07/08 next to a series projection on 09-08) counting both is consistent and
  is the financially safer interpretation.

Same-pattern hidden cases (both counted, no change recommended): "Scheduled utility debit" on
02-11 next to a utilities series on 02-05 for user_44, 104, 164, 224 (scheduled amount ~60 % of the
series amount, same shape as user_24's insurance); "Scheduled insurance payment" user_84;
"Scheduled school fee" user_244 (education series 2,945.80 on 06-07 + fee 3,517.80 on 06-11);
"Pending merchant debit / online order / pharmacy" one-offs next to shopping / healthcare series
(user_42, 60, 62, 82, 83, 100, 102, 120, 122, 142, 202, 222, 243, 260, 262); "Possible duplicate card
charge" rows (user_138, 156, 210) are ignored by the engine (`duplicate` + linked_event_id).

user_55: the image row "Water bill due" is a settled 723 INR receipt (already in the balance), not
the 13,884 monthly bill; the 06-08 projection and the 13,800 retry both stand.

## 4. Month-end rolling (history day 29/30/31)

None. Across the whole dataset no monthly debit series and no salary stream has a modal DOM >= 29
(monthly series DOMs run 1-16; days 29-31 occur only in short-cycle groceries / transport / dining
rows). `add_months` clamps to the month end, so the path is correct but never exercised.

## 5. Violations

None. Counts: 275 requests, 47 scheduled-salary users, 198 history-salary users, 30 freelance /
gig-only or no-income users, 1644 monthly series, 35 scheduled/pending-plus-series overlaps (all
judged correct), 11 mixed-DOM histories (all explained by linked / image rows already excluded).

## Recommended engine fixes

No fix required for salary or fixed-date projections. Optional hardening (no behaviour change on
this dataset): none of the audited paths depends on month-end clamping or on DOM > 28, so the
current `add_months` handling is sufficient.
