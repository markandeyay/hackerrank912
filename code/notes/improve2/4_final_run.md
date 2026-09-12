# 4. Final-run integrity (fresh model calls, polish off)

Date: 2026-09-12 (run finished 22:18:57 UTC). Command: `.venv/Scripts/python code/main.py` (no flags) after deleting
`code/cache/images.json`, `messages.json`, `explanations.json`, `usage.jsonl` and `last_run.json`.
Previous output saved as `code/notes/improve2/output_before_final_run.csv` (md5 ac2a78fa60f4b73eddceb6de7fdff027).

## Console

```
wrote 250 rows to C:\Users\yalam\hackerrank912\output.csv
VALIDATION: all rows valid
methods: {'full_payment': 70, 'wait': 61, 'not_recommended': 46, 'installments': 63, 'partial_payment': 10}
statuses: {'affordable_now': 58, 'affordable_later': 61, 'not_affordable': 46, 'affordable_with_plan': 85}
EXIT=0
```

## Byte identity

`output.csv` after the run: md5 ac2a78fa60f4b73eddceb6de7fdff027 - **byte-identical** to the saved copy (all 250 rows,
all seven scored/text columns including `decision_explanation`; 0 differing cells). `validate.py output.csv`: all rows valid.

## Model non-determinism in the regenerated evidence (none reached the decision)

Images (16/16 amounts present): 15 equal the manual transcription; `image_07` came back 8528.1 instead of 8528. It fills
`event_3231` (user_35, settled restaurant debit on 2025-10-29, the day before request_35's request date), so the amount is
already inside the opening balance and never enters the projection -> no effect.

Messages (215/215 present, same cache keys): 2 messages changed adjustment type between the old and the new model reading
(message_17, message_208), 14 new readings disagree with the regex template (T32 prize-claim -> scam_ignore, T33 prize
proceeds -> one_time_confirmed_income/scam_ignore, T14 arrears -> salary_amount_change, T17/T29 -> income types); in every
one of these the template capture wins in `merge_adjustment`, so the engine record is unchanged. 22 raw slot differences
(mostly `regular_salary_amount`, `currency`, `target`, `scope` flipping to/from null) yield 24 merged-record differences,
all in fields the engine does not read for that template (T05/T14 `scope` and T19 `percent` are supplied by the regex;
`regular_salary_amount`/`currency`/`target` are unused by `state.py` for these types; message_84 T16 `effective_date` is
redundant with the settled "Final employer payroll" row; message_88 T33 amount/date belong to a settled credit that is
never projected). Result: the deterministic reconciliation absorbed all model drift; decisions and explanations are identical.

Full diff listing:

```
rows old/new: 250 250 same ids: True
differing cells: 0
byte-identical files: True
cache sizes images old/new: 16 16  messages old/new: 215 215
image keys identical: True  message keys identical: True

== images: new model amount vs old cache vs manual transcription ==
  image_01 ev=event_253 new=4365000.0 manual=4365000
  image_02 ev=event_1442 new=100000.0 manual=100000
  image_03 ev=event_1545 new=41272.0 manual=41272
  image_04 ev=event_1700 new=2854.0 manual=2854
  image_05 ev=event_1786 new=704.05 manual=704.05
  image_06 ev=event_3051 new=1995.0 manual=1995
  image_07 ev=event_3231 new=8528.1 manual=8528  <-- differs from manual
  image_08 ev=event_4535 new=15339.0 manual=15339
  image_09 ev=event_5170 new=723.0 manual=723
  image_10 ev=event_6033 new=79679.26 manual=79679.26
  image_11 ev=event_6859 new=3650.0 manual=3650
  image_12 ev=event_7307 new=33.5 manual=33.5
  image_13 ev=event_7941 new=2298.0 manual=2298
  image_14 ev=event_9421 new=4543.0 manual=4543
  image_15 ev=event_9806 new=9968.0 manual=9968
  image_16 ev=event_10521 new=393.22 manual=393.22
  OLD/NEW image amount differs for key 0e69310f4f113c7c43d6a9c3 8528 -> 8528.1
images differing from manual: 1

== messages: new model vs old cache vs regex template ==
  MERGED record differs message_02: {'target': ('salary', 'none')}
  OLD/NEW slot currency differs message_07 T=T18_gig_payout_pending: 'INR' -> None; regex=None
  MERGED record differs message_07: {'currency': ('INR', None)}
  NEW vs REGEX type differs message_16 T=T32_prize_claim_processing: new=scam_ignore regex=pending_credit_not_available (template wins)
  OLD/NEW type differs message_17 T=T33_prize_proceeds_received: old=no_effect new=one_time_confirmed_income regex=no_effect
  NEW vs REGEX type differs message_17 T=T33_prize_proceeds_received: new=one_time_confirmed_income regex=no_effect (template wins)
  OLD/NEW slot amount differs message_17 T=T33_prize_proceeds_received: None -> 33550.0; regex=None
  OLD/NEW slot effective_date differs message_17 T=T33_prize_proceeds_received: None -> '2025-12-28'; regex=None
  OLD/NEW slot currency differs message_17 T=T33_prize_proceeds_received: None -> 'INR'; regex=None
  NEW vs REGEX type differs message_28 T=T33_prize_proceeds_received: new=one_time_confirmed_income regex=no_effect (template wins)
  OLD/NEW slot regular_salary_amount differs message_38 T=T11_first_salary_new_employer: 69000 -> None; regex=None
  MERGED record differs message_38: {'regular_salary_amount': (69000, None)}
  OLD/NEW slot regular_salary_amount differs message_42 T=T15_household_income_ended: 25840000 -> None; regex=None
  MERGED record differs message_42: {'regular_salary_amount': (25840000, None)}
  MERGED record differs message_46: {'target': ('none', 'other_expense')}
  OLD/NEW slot scope differs message_50 T=T05_salary_date_change: 'permanent' -> 'not_applicable'; regex='next_payment_only'
  MERGED record differs message_64: {'target': ('none', 'other_expense')}
  OLD/NEW slot regular_salary_amount differs message_70 T=T07_base_salary_commission_pending: 49280 -> None; regex=None
  MERGED record differs message_70: {'regular_salary_amount': (49280, None)}
  NEW vs REGEX type differs message_71 T=T32_prize_claim_processing: new=scam_ignore regex=pending_credit_not_available (template wins)
  MERGED record differs message_72: {'target': ('none', 'other_expense')}
  NEW vs REGEX type differs message_75 T=T33_prize_proceeds_received: new=one_time_confirmed_income regex=no_effect (template wins)
  OLD/NEW slot effective_date differs message_84 T=T16_employment_ended: '2026-04-01' -> None; regex=None
  MERGED record differs message_84: {'effective_date': ('2026-04-01', None)}
  OLD/NEW slot amount differs message_88 T=T33_prize_proceeds_received: 32450.0 -> None; regex=None
  OLD/NEW slot effective_date differs message_88 T=T33_prize_proceeds_received: '2024-08-30' -> None; regex=None
  OLD/NEW slot currency differs message_88 T=T33_prize_proceeds_received: 'INR' -> None; regex=None
  MERGED record differs message_88: {'amount': (32450.0, None), 'currency': ('INR', None), 'effective_date': ('2024-08-30', None)}
  NEW vs REGEX type differs message_90 T=T14_regular_plus_arrears: new=salary_amount_change regex=one_time_confirmed_income (template wins)
  OLD/NEW slot regular_salary_amount differs message_91 T=T09_salary_resumes_childcare: 176000 -> None; regex=None
  MERGED record differs message_91: {'regular_salary_amount': (176000, None)}
  OLD/NEW slot regular_salary_amount differs message_104 T=T01_salary_increase: 828 -> None; regex=None
  MERGED record differs message_104: {'regular_salary_amount': (828, None)}
  NEW vs REGEX type differs message_110 T=T33_prize_proceeds_received: new=scam_ignore regex=no_effect (template wins)
  OLD/NEW slot regular_salary_amount differs message_111 T=T10_first_salary_credit_date: 864 -> None; regex=None
  MERGED record differs message_111: {'regular_salary_amount': (864, None)}
  NEW vs REGEX type differs message_117 T=T17_reimbursement_not_salary: new=one_time_confirmed_income regex=no_effect (template wins)
  NEW vs REGEX type differs message_118 T=T29_foreign_bill_charged: new=unconfirmed_income regex=no_effect (template wins)
  OLD/NEW slot scope differs message_131 T=T05_salary_date_change: 'permanent' -> 'not_applicable'; regex='next_payment_only'
  MERGED record differs message_133: {'target': ('credit', 'other_expense')}
  NEW vs REGEX type differs message_134 T=T32_prize_claim_processing: new=scam_ignore regex=pending_credit_not_available (template wins)
  OLD/NEW slot currency differs message_146 T=T28_foreign_refund_processing: 'INR' -> None; regex=None
  MERGED record differs message_146: {'currency': ('INR', None), 'target': ('other_expense', 'none')}
  MERGED record differs message_164: {'target': ('none', 'other_expense')}
  OLD/NEW slot scope differs message_165 T=T05_salary_date_change: 'not_applicable' -> 'next_payment_only'; regex='next_payment_only'
  MERGED record differs message_167: {'target': ('credit', 'other_expense')}
  MERGED record differs message_172: {'target': ('other_expense', 'credit')}
  NEW vs REGEX type differs message_174 T=T17_reimbursement_not_salary: new=one_time_confirmed_income regex=no_effect (template wins)
  OLD/NEW slot scope differs message_176 T=T14_regular_plus_arrears: 'next_payment_only' -> 'not_applicable'; regex=None
  MERGED record differs message_176: {'scope': ('next_payment_only', None)}
  OLD/NEW slot regular_salary_amount differs message_194 T=T07_base_salary_commission_pending: 1548 -> None; regex=None
  MERGED record differs message_194: {'regular_salary_amount': (1548, None)}
  OLD/NEW slot regular_salary_amount differs message_196 T=T11_first_salary_new_employer: None -> 53680; regex=None
  MERGED record differs message_196: {'regular_salary_amount': (None, 53680)}
  OLD/NEW slot currency differs message_206 T=T08_seasonal_contract_ended: None -> 'INR'; regex=None
  MERGED record differs message_206: {'currency': (None, 'INR')}
  OLD/NEW type differs message_208 T=T29_foreign_bill_charged: old=no_effect new=unconfirmed_income regex=no_effect
  NEW vs REGEX type differs message_208 T=T29_foreign_bill_charged: new=unconfirmed_income regex=no_effect (template wins)
  NEW vs REGEX type differs message_209 T=T32_prize_claim_processing: new=scam_ignore regex=pending_credit_not_available (template wins)
  NEW vs REGEX type differs message_211 T=T14_regular_plus_arrears: new=salary_amount_change regex=one_time_confirmed_income (template wins)
  MERGED record differs message_214: {'target': ('other_expense', 'credit')}
  MERGED record differs message_215: {'target': ('credit', 'other_expense')}
messages: type old/new differ=2, new vs regex differ=14, raw slot diffs old/new=22, merged-record diffs (what the engine sees)=24
```

## Usage report

`code/evaluation/usage_report.py` regenerated `usage_report.md`: 231 calls (16 image_extraction, 215 message_adjustment,
0 explanation_polish) on claude-sonnet-5; 464,280 input + 35,654 output = 499,934 tokens; USD 1.2851 total,
USD 0.00514 / request, 1,999.7 tokens / request. The "Final run" paragraph of the generator was rewritten to count the
calls of the last invocation per job from the log (last `new_model_calls` lines) and to state why polishing is off.

## README

Added `## Architecture` (ten sentences) after the "How it works" section.
