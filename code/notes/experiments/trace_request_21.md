# Trace: request_21 (user_21, USD) — why the reference reserves 568 and picks cloud + streaming

Scripts (all read-only against the engine): `trace_request_21.py` (hypothesis sweep, subset search, nominal analysis),
`_b.py` (payday / payday+1 items per sample, change-selection orderings), `_c.py` (date-shift variants),
`_d.py` (per-series occurrence-count brute force for every sample), `_e.py` / `_f.py` (rescoring rule A).
Run with `.venv/Scripts/python code/notes/experiments/<script>` from the repo root.

## 1. The amount gap

Reference: `amount_safe_to_pay` 1543.35 = 3911.35 − 1800 − **568** (reserve).
Engine (pre-payday trough on 2026-04-12): fuel 53 + utilities 121.18 + groceries 83.63 (04-06) + streaming 47 + cloud 11 +
shopping 122.41 = **438.22** (the 537.19 in the task brief was an addition slip). Gap = **129.78**.

Nominal rounding cannot close it. Fixed items (53 + 47 + 11 = 111) are exact, so the variable pre-payday items would have to
sum to 457 against a mean-based 327.22 (+40 %); observed ranges are utilities 115–124, shopping 116–133, groceries 66–104,
so even max-of-history gives only 361.7. The gap is one transport occurrence (41.20) plus one ~83 item: groceries 04-16
(563.05, −0.9 %) or dining 04-17 (562.86, −0.9 %) — indistinguishable because groceries 83.63 ≈ dining 83.44.

Candidate rules tested across all 25 samples (`_a/_c/_d`):

* salary one day late / debit-first on payday: reserves on-payday items → fixes 02, 04, 18 but breaks 06, 15, 19, 22, 25
  (monthly items on payday are *not* reserved) and does nothing for 21 (its items are on payday+1).
* "everything through payday+1": fits 04, 18, 21, 23 but not 02, 03, 20 (their extra item is 3–5 days after payday).
* periodic dates shifted −1 day (V1): mean error 5.6 → 3.9 % but 21 unchanged and 25 breaks (+8.4 %).
* daily-rate model (mean/gap × days): implied days covered vary 7–15 vs 8–18 days to payday → rejected.
* **Rule A — every short-cycle (5/7/10/14/21-day) series contributes at least its next occurrence before the first payday,
  even when that occurrence falls after the payday.** Brute force over per-series counts (`_d.py`) shows the reference
  matches the calendar count wherever it is ≥ 1 (07, 08, 11, 14, 17, 19, 22, 24, 25 within 1.5 %) and uses exactly one
  occurrence wherever the calendar count is 0: 02 dining (−7.9 → −0.2 %), 03 transport (−4.4 → −0.3 %), 18 dining
  (−13.5 → +0.3 %), 20 dining (−10.9 → −0.4 %), 21 transport+dining (−22.8 → −0.9 %), 23 transport (−6.0 → −0.3 %).
  This is the organizers' "forecast essential variable spending conservatively".

Rule A for request_21: 438.22 + 41.20 + 83.44 = 562.86 → safe 1548.49, earliest 2026-04-15, status/method/plan/changes all
match the sample. Implied nominal total of the five variable items = 568 − 111 = 457 vs mean sum 451.86 (+1.1 %), e.g.
utilities 120 + shopping 125 + groceries 85 + transport 42 + dining 85; the residual is ordinary ±1 % noise, not a rule.

Score impact (`_f.py`, `periodic_before_payday_days=0`, rule A as *move next occurrence to payday−1*): 118 → **121/150**,
uncapped reserves within 2 %: 9 → 15 of 21; request_21 becomes an exact match. The *add* variant scores 116 because it
over-reserves the second cycle of request_16 (trough 2023-09-14) by 172 INR. Remaining mismatches: 06 (+9.7 %, the reference
has two *fewer* periodic occurrences — best fits (1,0,2)/(2,0,1); its transport series ends on the request date), 11 (+1.1 %
noise flips the June full payment), 17 (+0.6 % noise), 19 (−1.4 % noise in the partial split), 04 (−16.8 %: needs groceries on
payday 06-15 and transport on 06-16 as second occurrences — unexplained).

Interaction with the new engine option `periodic_before_payday_days=1` (periodic items *on* payday → payday−1): it fixes 18,
23, 13 and improves 04 (−5.4 %) but breaks 25 (+8.4 %: transport 03-15 is a second occurrence the reference does not
reserve) and cannot touch 21. Rule A covers 18 and 23 without hurting 25; with both switched on the score is unchanged at
116/150 (add) because of 16/25. Recommendation: rule A (move variant) with `win=0`; keep 04 as the open outlier.

## 2. Change-selection rule (confirmed)

Shortfall after paying 1574.40 today = 1574.40 − 1543.35 = 31.05. Candidates (user may reduce dining/streaming/shopping,
stop streaming/cloud_storage; groceries/utilities/rent protected), with the reduce action preferred when both are allowed:

| order key | candidate sequence | result |
|---|---|---|
| series amount ascending | cloud 11 (stop, 04-12) → streaming 47 (reduce, saves 23.50, 04-09) → dining 83.44 → shopping 122.41 | 11 + 23.50 = 34.50 ≥ 31.05 → `stop:event_1815|reduce_to:event_1816:23.50` |
| saving ascending | 11 → 23.50 → 42.44 → 72.81 | same |
| event_id ascending | 1815 → 1816 → 1817 → 1854 | same |
| amount/saving descending | shopping first | `reduce_to:event_1817:49.60` (wrong) |
| single sufficient change first | shopping (72.81) | wrong |
| stop preferred over reduce | cloud stop + streaming stop | `stop:1815|stop:1816` (wrong) |

So the reference is a greedy accumulation, cheapest first, reduce preferred over stop, stopping as soon as the cumulative
saving covers the shortfall, output in application order — exactly what `planner.greedy_changes` does (it additionally
requires each change to raise the failing trough, which is why dining, first due 04-17, and cloud in request_11, due on the
05-15 payday after the 05-14 trough, are skipped). Consistent with request_06 (`stop:event_476`, the cheapest sufficient
change) and request_11 (`reduce_to:event_989:665950`).
