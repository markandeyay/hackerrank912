# Cross-column invariant audit of output.csv

Script: `code/notes/improve/audit_invariants.py` (independent of `code/validate.py`, stricter).
Run: `.venv/Scripts/python code/notes/improve/audit_invariants.py` -> exit 0 = no violations.
Full run output: `code/notes/improve/audit_invariants_run.txt`.

Audited: `output.csv` (250 rows) against `dataset/requests.csv`, `financial_profiles.csv`,
`financial_events.csv`, `request_payment_options.csv`, plus the organizer sample format in
`sample_requests.csv`.

## Violation table (final run)

| Invariant | Violations |
|---|---:|
| header / column order exact | 0 |
| one row per request_id, no duplicates, none missing | 0 |
| 0 <= amount_safe_to_pay <= requested_amount; <= 2 decimals | 0 |
| payment_plan parses; chronological; amounts have 0 or exactly 2 decimals | 0 |
| earliest_date within request_date .. request_date+84; > request_date unless statement-sanctioned | 0 |
| affordable_now => full_payment, plan = request_date:requested, earliest = request_date, changes none, safe = requested | 0 |
| affordable_later => wait, single payment of requested on earliest, earliest > request_date, changes none | 0 |
| affordable_with_plan => partial / installments / full_payment+changes; last payment <= desired_completion_date | 0 |
| not_affordable => not_recommended, plan none, changes none | 0 |
| method in payment_methods_user_will_consider; wait requires full_payment accepted | 0 |
| full_payment plan = request_date:requested; status now / with_plan | 0 |
| partial_payment: 2 payments, request_date:safe + earliest:(requested-safe), sums exact, allows_partial, 0<safe<requested, earliest<=desired | 0 |
| installments: plan == one supplied option (dates first+k*freq, count, amounts); status with_plan | 0 |
| installments: number_of_payments <= max_installment_months (blank => violation) | 0 |
| spending changes: <=3, same user, debit, flexibility/category/protect rules, new_amount == minimum_allowed_amount, no stop+reduce on same event, only with affordable_with_plan | 0 |
| decision_explanation non-empty and mentions home currency code | 0 |
| amount_safe_to_pay > 0 whenever headroom > 0 (see zero roster below) | 0 |
| **TOTAL** | **0** |

Distribution: affordable_now 58 / affordable_with_plan 85 / affordable_later 61 / not_affordable 46;
full_payment 70 (58 now + 12 with changes) / installments 63 / partial_payment 10 / wait 61 / not_recommended 46.

## Real defects found

None. Every row satisfies every cross-column invariant.

## False positives from the first pass (kept as documentation; the audit script was corrected)

1. **`earliest_date_for_full_payment == request_date` while status != affordable_now (23 rows)**:
   request_30, 59, 61, 75, 102, 110, 122, 154, 158, 164, 166, 174, 178, 197, 199, 203, 206, 213,
   215, 238, 241, 246 (all `affordable_with_plan` / `installments`) and request_251
   (`not_affordable`). In all 23 the user does **not** list `full_payment` in
   `payment_methods_user_will_consider` and `amount_safe_to_pay == requested_amount`.
   The statement explicitly sanctions this: "earliest_date_for_full_payment measures financial
   capacity independently of the user's payment-method preferences. It may equal request_date even
   when the selected recommendation is installments because the user has chosen not to consider
   full payment." The audit now only flags it when the user accepts full_payment (0 such rows).
   request_251 is consistent too: capacity exists today, the user only accepts partial/installments,
   the request does not allow partial, and no supplied installment option was safe/eligible.

2. **Plan amount formatted `529.10` vs requested_amount `529.1` (15 affordable_now rows)**:
   request_69, 112, 121, 142, 175, 177, 189, 191, 196, 223, 230, 235, 247, 258, 261.
   The organizer sample uses exactly this convention (`request_06: 2026-01-03:620.40`,
   `request_18: 2026-09-15:3246.10`), so 2-decimal plan amounts are the correct format.
   `amount_safe_to_pay` is written as `529.1` (matches the sample's `amount_safe_to_pay` style,
   e.g. `603.3`). Numeric equality holds in all 15.

## Intentional engine policy (warnings, not violations)

**affordable_later with earliest_date AFTER desired_completion_date (3 rows).** The statement
says the plan must complete by `desired_completion_date`; the engine still recommends `wait`
when it is the only safe eligible plan. Owner decision needed (alternative: `not_affordable` /
`not_recommended`). In all three the miss is by exactly one day (salary on the 15th vs deadline
on the 14th), partial payment is not allowed by the request, and the user does not consider
installments:

| request | request_date | desired | earliest | safe | requested | methods |
|---|---|---|---|---|---|---|
| request_78 | 2025-10-02 | 2025-10-14 | 2025-10-15 | 45955.21 | 50200 | full_payment, partial_payment (request disallows partial) |
| request_114 | 2026-01-04 | 2026-01-14 | 2026-01-15 | 58948.02 | 65300 | full_payment |
| request_120 | 2026-04-06 | 2026-04-14 | 2026-04-15 | 7110696.83 | 7714000 | full_payment |

Note: with `affordability_status` semantics, "affordable_later: the full amount is expected to
become safe later" is literally true for these rows; the risk is only if the grader treats the
deadline as a hard gate for `affordable_later`.

## amount_safe_to_pay == 0 roster (2 rows) - both classified LEGITIMATE

Verified with `.venv/Scripts/python code/debug_request.py <id> --llm --days 30`.

| request | headroom (balance - min) | status / method | next salary | classification |
|---|---:|---|---|---|
| request_64 (user_64, INR) | 62,473.01 | not_affordable / not_recommended | 2024-06-15 (54,997.80) | **legitimate** |
| request_97 (user_97, ZAR) | 8,865.89 | affordable_with_plan / installments (3 x 8145.28 from 2024-03-19) + stop:event_9006, reduce_to:event_9038:577.50 | 2024-03-15 (35,420) | **legitimate** |

- **request_64**: pending debit `event_6033` "Large grocery tax invoice" (blank CSV amount, filled
  from `image_10.png`; the image shows Total / Balance Due Rs 79,679.26) settles 2024-06-10, plus the
  scheduled school fee (2,240) and projected essentials. Without any payment the balance drops to
  7,949 on 06-10 (< min 36,100). After the 06-15 salary the balance never reaches
  min + 63,700 = 99,800 within 84 days (salary ~55k/month vs ~40k/month outgoings), so
  earliest is empty and the row is `not_affordable`. The user only accepts partial (request
  disallows) and installments (max 11); all options were unsafe. Correct.
- **request_97**: projected essentials before the 03-15 salary (utilities 2,078 + groceries 1,438 +
  loan 3,531 + music 219 + transport 810 + dining 1,167 = ~9,243) exceed the 8,865.89 headroom:
  balance hits 29,322 on 03-14 (< min 29,700) with no payment at all, so `amount_safe_to_pay`
  is 0 by definition (before optional spending changes). The recommended installment plan starts
  03-19 (after salary) and the two permitted changes (stop music_subscription 218.90, reduce
  dining to its minimum 577.50) lift the 03-14 trough above the minimum. Correct.

## Notes for the owner

- The `earliest_date == request_date` rows (23) and the 2-decimal plan amounts (15) are
  statement-conformant; do not "fix" them.
- The only open policy question is the 3 `wait`-after-deadline rows above.
- The audit also confirms every installment plan equals a supplied option and respects
  `max_installment_months`, every spending change uses the event's exact `minimum_allowed_amount`,
  and no `full_payment` / `affordable_with_plan` row lacks spending changes.
