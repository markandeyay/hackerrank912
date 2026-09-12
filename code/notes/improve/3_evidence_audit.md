# 3 - Evidence application audit (messages + images)

Scope: every request (sample_requests.csv + requests.csv) whose user has a message or an image:
219 requests (215 message users + 4 image-only users; no user has more than one request, no user has more than one message).
Method: `3_evidence_audit.py` builds each request's state twice, with the cached model + regex adjustments
(`StateBuilder(ds, images, adjs)`) and with `adjustments={}`, and diffs flows / series / notes / decision
(`3_evidence_audit_dump.txt`, `3_evidence_audit_records.json`). `3_checks.py <Txx>` prints per-template evidence.
Result: 69/219 states change with the adjustment; the other 150 are no-effect templates or messages whose fact the
engine already derives from events (see table). No message is sent after its user's request_date; no image event settles
after the request date; no blank amount is ever treated as zero (all 16 image amounts are present in the cache;
`amount_of()` returns None for a missing amount and the "missing amount ... ignored" note never fires).

## 1. Per-template verdict

| template | n | state changed | engine behaviour | verdict |
|---|---|---|---|---|
| T01 salary raise | 9 | 9/9 | stream = new amount from the effective date (07-15/08-15 = the normal payday) and every later payroll | OK |
| T02 regular salary confirmed | 1 | 0 | no effect; salary stream anchored on image_01 amount 4365000 IDR (request_03) | OK |
| T03 bonus pending | 8 | 0 | no bonus rows exist; nothing added | OK |
| T04 temporary reduced pay | 10 | 10/10 | next payroll = reduced amount, later payrolls revert to the modal regular amount | OK |
| T05 salary date change | 7 | 7/7 | next payroll moved to the 23rd, amount unchanged | OK, minor: later months also on the 23rd (D1) |
| T06 unpaid-leave reduction | 10 | 0 | message amount == historical regular amount in all 10 rows; next payroll = message amount | OK (data quirk; matches sample request_08) |
| T07 base salary, commission pending | 9 | 0 | keeps the settled "Base salary" rows (= 60% of the message figure); commissions never projected (NEVER_PROJECT_INCOME) | OK, conservative (J1) |
| T08 seasonal contract ended | 9 | 0 | no salary projected (without the message the stream was already dropped as stale > 45 days) | OK |
| T09 salary resumes | 8 | 0 | stream from the stated date at the stated amount; no childcare rows exist, none invented | OK |
| T10/T11 first salary | 21 | 0 | history already has two first-job payrolls at the same amount; stream continues monthly from the confirmed date | OK |
| T12 first salary scheduled | 6 | 6/6 | history has one prorated payroll; stream = full amount from the confirmed date | OK |
| T13 foreign salary | 6 | 0 | amount == existing foreign stream; converted with the exact rate row of each payday (e.g. 696 USD x 15833.33 on 2025-05-15) | OK |
| T14 regular + arrears | 8 | 0 | arrears amount already settled as "Promotion arrears payment" on the 20th of the previous month -> deduped, regular stream kept | OK (J2) |
| T15 household income ended | 7 | 7/7 | single stream at the stated remaining amount; second stream not projected | OK |
| T16 employment ended | 4 | 0 | "Final employer payroll" already stops the stream; message confirms | OK |
| T17 reimbursement not salary | 3 | 0 | settled refund row is in the balance, not projected | OK |
| T18 gig payout pending | 8 | 8/8 | whole gig stream dropped (not only the next payout) | OK vs sample request_10 (expected 12700 => organizers count no gig income) |
| T19 rent +12% | 7 | 7/7 | rent series = last rent x 1.12 from the next occurrence (all rents constant, so mean == last); request date never coincides with a rent date; request_16 also reserves the image_02 balance 100000 on 08-16 | OK |
| T20 invoice approved | 15 | 15/15 | one-off credit of the stated amount on the stated date; freelance stream suppressed | OK |
| T21 receipt confirms settled expense | 2 | 0 | image_08 / image_13 amounts fill the settled rows; nothing projected | OK |
| T22 wallet charge + foreign salary | 1 | 0 | 1296 USD on 2026-09-15 x 83.33 = 107995.68 INR, matches the existing stream (not double counted); image_16 393.22 fills event_10521 | OK |
| T23 internal transfer | 6 | 0 | no transfer event rows exist for any of the 6 users ("Apartment rent transfer" rows are ordinary rent); nothing to exclude | OK |
| T24 failed debit retry | 4 | 0 | every failed row has a scheduled retry row -> reserved once via the scheduled row, failed row skipped; the `payment_delayed` fallback fires only when no retry row exists | OK |
| T25 card dispute open | 6 | 0 | pending "Possible duplicate card charge" (linked to a settled original) is dropped, not reserved | INCONSISTENT with the notes (D2) |
| T26 two card minimums | 2 | 0 | no card-minimum rows exist near the request; nothing to collapse | OK |
| T27 refund initiated | 7 | 0 | pending refund credit never counted (same with/without) | OK |
| T28 foreign refund | 6 | 0 | no pending refund rows exist; nothing added | OK |
| T29 foreign bill charged | 3 | 0 | no foreign-currency debit rows exist; only the foreign salary stream, converted per payday | OK |
| T30/T31 valuations | 7 | 0 | unrealized non_cash rows skipped | OK |
| T32 prize claim processing | 4 | 0 | no prize rows pending; nothing added | OK |
| T33/T34 settled prize / sale | 9 | 0 | settled credits in the balance, not projected (windfall / investment excluded from recurrence) | OK |
| T35 scam | 2 | 0 | ignored | OK |

## 2. Defects / deviations found

D1. T05 salary date change moves every later payroll too (minor). `_build_income` projects `add_months(first_date, k)`,
so after the move to the 23rd the stream stays on the 23rd (request_07/68/95/131/167/194/212). The template note says
later months keep the usual day (15th). The effect is conservative (income 8 days later in months 2-3) and the history
itself shows the latest payroll already on the 23rd, so this is a judgment call; for the literal template reading only
k == 0 should use the effective date and k >= 1 the historical day-of-month.

D2. T25 pending duplicate card charge: engine and notes disagree. `StateBuilder.build` drops any pending debit whose
description contains "duplicate" and has a linked_event_id (note "pending duplicate charge ... ignored"), i.e. it applies
the statement's "ignore duplicate records" rule. `code/notes/03_messages.md` (T25 engine implication) says to keep the
pending debit reserved because the dispute is open and no reversal has been posted, i.e. the financially safer reading.
Affected: request_138 (134.75 EUR), request_156 (1617 ZAR), request_198 (8800 INR), request_210 (145.8 USD),
request_234 (45.65 EUR), request_252 (988000 IDR). The treatment is internally consistent (identical with or without the
message; the `dispute_ignore` adjustment adds nothing either way) but it is the less conservative of the two readings.
Recommendation: choose explicitly. If the rows are duplicates, update the T25 note; if the message is taken at face value
("charge stands until reversed"), reserve it at `max(sd, rq)` like other pending debits. None of the six is a sample.

D3. Settled image rows are excluded from recurrence means (`OPTIONS["exclude_image_rows_from_mean"] = True`).
12 of the 16 image amounts fill already-settled rows (image_01, 03, 04, 06, 07, 08, 09, 12, 13, 14, 15, 16); they are in
the balance already and, with this option, never influence any series estimate. Only image_02 (100000 scheduled),
image_05 (704.05 pending), image_10 (79679.26 pending), image_11 (3650 scheduled) and image_01 (salary anchor for
request_03, 4365000 IDR) change a forecast. This is deliberate (notes/mismatches.md item 5) and is closer to the samples
(request_17: 243023.68 excluded vs 240640.32 included, expected 243849.58; request_19: 29948.97 vs 30022.77, expected
28820), so it is not a defect, but the parent should know that image_12 (33.50 USD) is never converted in practice; when
included, the conversion uses the 2025-10-01 USD->INR row 83.33 (= 2791.56 INR) as required.

D4. Dead condition in the `_build_debit_series` rent-increase loop: `(a.get("target") in (...) or True)` is always
true, so any `expense_increase_percent` record raises the rent series regardless of target. Harmless today (all 7 T19
messages target rent) but should be tightened to `a.get("target") == "rent"`.

No case was found where an adjustment was missing, applied twice, or applied in the wrong direction. Every adjustment
that adds income (T01, T09-T15, T20, T22) adds it once, on the stated date, in the stated currency, converted with that
date's rate row; every adjustment that removes income (T08, T15, T16, T18) leaves no residual credit flows; every
no-effect template leaves the state identical with and without the message.

## 3. Judgment calls worth a second look (not defects)

J1. T07: the message says "confirmed base salary is X" but the settled "Base salary" rows are exactly 0.6 X for all 9
users (request_11/76/80/92/104/108/164/176/248). The engine keeps the settled 0.6 X (safer). If the organizers meant the
message figure to be the base, the projection is 40% low for these users. No sample has a T07 user.

J2. T14: the arrears amount is already settled on the 20th of the month before sent_at for all 8 users; the engine
treats the message as describing that settled credit (45-day dedupe window). Alternative reading: a second arrears
credit on the next payday. The engine's reading follows the "settled event" / safer-interpretation rule.

J3. T18: the engine drops the entire gig stream for the horizon, which sample request_10 supports (expected safe 12700 is
only reachable with no gig income), although the template literally says only the next payout is pending.

## 4. Model vs template disagreements (all resolved in favour of the template, all correct)

| message | template type | model type | comment |
|---|---|---|---|
| message_90, message_211 | T14 one_time_confirmed_income | salary_amount_change | template keeps the regular amount and dedupes the arrears; the model would only have set the stream amount (same result) |
| message_117, message_174 | T17 no_effect | one_time_confirmed_income | model would have re-added a settled reimbursement (wrong); template right |
| message_118 | T29 no_effect | unconfirmed_income | both add nothing; template right |
| message_16, 71, 134, 209 | T32 pending_credit_not_available | scam_ignore | both add nothing |
| message_75, message_28 | T33 no_effect | one_time_confirmed_income | model would have re-added settled prize proceeds (wrong); template right |
| message_110 | T33 no_effect | scam_ignore | both add nothing |

No template choice looks wrong. The merge takes the template record wholesale when the types differ, so the model's
amount/date slots are discarded in these cases; that is the desired behaviour here.

## 5. Image checks

All 16 blank-amount events use the cached image amount (`load_image_amounts`), in the event's own currency:
image_01 4365000 IDR (salary anchor, request_03), image_02 100000 INR balance due (not 200000; known debit 2023-08-16 in
request_16), image_03 41272, image_04 2854, image_05 704.05 INR (pending known debit 2026-02-09 in request_20; not
822.05), image_06 1995, image_07 8528, image_08 15339, image_09 723, image_10 79679.26 (pending known debit 2024-06-10),
image_11 3650 (scheduled known debit 2023-01-23), image_12 33.50 USD (settled; converted with the 2025-10-01 rate 83.33
when used), image_13 2298, image_14 4543, image_15 9968, image_16 393.22. Rate rows exist for every foreign-salary payday
used (USD->IDR 2025-05-15, EUR->ZAR 2025-05-15 / 08-15 / 11-15, USD->INR 2025-10-01 / 2025-11-15 / 2026-09-15), so the
nearest-date fallback in `Dataset.convert` is never exercised for message-driven amounts.
