# Trace: request_11 (user_11, IDR) — why the reference says earliest 2025-07-15 and reserve 16,880,550

Scripts: `exp_request_11.py` (single-request variants), `exp_rules_xsample.py` (same variants scored on all 25 samples).
Engine untouched.

## 1. Engine state (84-day window, salary-first netting)

* balance 63,531,795, min 34,140,600, requested 13,110,000, deadline 2025-06-12, user accepts full_payment only.
* Salary: Base salary 23,256,000 on the 15th x5 in history (Dec-Apr), commissions on the 24th (8.5M-20.0M) excluded.
  Message T07 restates the base as 38,760,000 (= 23,256,000 / 0.6); engine keeps 23,256,000.
* Monthly (DOM): housing 2,954,500 (5th), utilities 2,720,215 (8th), insurance 1,881,000 (9th), education 2,544,100 (10th),
  healthcare 2,943,993 (12th), cloud 168,150 (14th), entertainment 1,600,927 (16th).
* Periodic (last + step): groceries 1,421,333 /10 d (May 8, 18, 28, Jun 7, 17, 27, Jul 7, 17), transport 1,088,014 /14 d
  (May 11, 25, Jun 8, 22, Jul 6, 20), dining 1,350,023 /21 d (May 14, Jun 4, Jun 25, Jul 16). Histories are perfectly regular.

Daily series (engine): May 14 **46,460,467** (trough) -> May 15 69,716,467 -> Jun 14 47,113,531 -> Jun 15 70,369,531 ->
Jul 14 47,766,595 -> Jul 15 71,022,595 -> Jul 26 65,562,299. The balance climbs **+653,064 per salary cycle**
(salary 23,256,000 - cycle debits 22,602,936; each cycle carries only 3 groceries + 2 transport + 1 dining).

* safe = 46,460,467 - 34,140,600 = 12,319,867 (reserve 17,071,328; reference 16,880,550, ours +1.1 %).
* Full payment on May 15 fails at Jun 14 by 137,069; on **Jun 15 it passes at Jul 14 by 515,995** (47,766,595 - 13,110,000 -
  34,140,600) -> earliest Jun 15. Reference: Jul 15, so in the reference the Jun 15 payment must fail at Jul 14.

## 2. What would make June fail and July pass (thresholds, engine layout)

* Salary <= **22,998,002** (i.e. >= 257,998 lower per month) - no such number exists in the data (base rows are all
  23,256,000; the message says more, not less; skipping a salary or using 38.76M once gives safe ~ 0 or May 15).
* Or >= **258k more debits per cycle** (>= 707k in total between May 15 and Jul 14, >= 54k of it before Jun 14).
* July always passes (after the Jul 15 salary the balance is >= 57.9M and only ~5.5M of debits remain in any horizon).
* Horizon 90 vs 84: no effect (the Jul 14 day is binding either way).
* Nominal-amount noise alone cannot do it: with the trough pinned at May 14 the reference's pre-May-15 items sum to
  16,880,550, so the cycle can only exceed ours through entertainment + 2 x groceries + transport, which would have to be
  >= 6,075,772 vs our 5,531,607 (+9.8 %) - impossible for means of 5/18/13 rows. Same conclusion if the trough is Jul 14.

## 3. Reserve decomposition (16,880,550)

Fixed items are exact: housing 2,954,500 + insurance 1,881,000 + education 2,544,100 + cloud 168,150 = 7,547,750.
Variable remainder 9,332,800 vs our means u+h+g+t+d = 9,523,578 (-2.0 %; within +-3 %). Without cloud the remainder is
9,500,950 (-0.24 %). Alternative reading: a Jul 14 trough with periodic spend at its average rate gives 16,783,478 (-0.6 %).
The reserve therefore cannot tell whether the reference's trough is May 14 or Jul 14; the earliest date can.

## 4. The single rule that explains both: the reference's balance does not climb between paydays

Monthly-equivalent spend from history = 14,812,885 (monthly items) + groceries 3 x 1,421,333 + transport 1,088,014 x 30/14 +
dining 1,350,023 x 30/21 = **23,336,947 > salary 23,256,000** (net -80,947 / month). Our last+step layout drops one dining
(next Jul 16) and part of a transport (Jul 20) out of the Jun 15-Jul 14 cycle, under-counting the 30-day rate by 734k
(1,018k in the 31-day May cycle), which is exactly why our balance climbs +653k/cycle and June passes by 516k.
If short-cycle spending is charged at its average rate (daily accrual, or 30/step occurrences per cycle) the balance
drifts down, the trough becomes the last pre-payday day (Jul 14: 46,748,317 -> safe 12,607,717, reserve 16,783,478, -0.6 %),
and the earliest full-payment date is Jul 15 (`exp_rules_xsample.py accrual`). Any rule with cycle spend >= 22,956,322
(1.6 % above ours) reproduces Jul 15.

Consistency (post-hoc accrual for periodic series, all 25 samples): earliest 23/25 (base 22/25; only request_11 changes;
17 and 21 stay wrong), method 24/25 (same), changes 22/25 (same). Reserve errors move: 08 -0.1 -> -5.8 %, 15 +3.7 -> -3.8 %,
19 -1.4 -> 0.0 %, 23 -6.0 -> -3.1 %, 24 -0.6 -> +3.3 %, 25 +0.2 -> +3.8 %; within-2 % count 9 -> 7, mean |err| 4.7 -> 5.1 %.
So the reference is discrete elsewhere (request_15/23/25 skip-on-request-date and request_08/19 counts fit discrete hits);
the rule to adopt is narrower: **do not let the projected balance climb from cycle to cycle when the historical monthly
rate of spending is >= the salary** (equivalently, carry each periodic category's full 30/step monthly rate into every
cycle when computing the earliest date). Median amounts also give Jul 15 (24/25 earliest) but only because their reserve
is 2.3 % too high (gap 988k > 2-cycle gain 698k), and they break the method for 11 and the changes for 07.

## 5. Spending changes: why our greedy needs cloud and the reference does not

Reference gap = 13,110,000 - 12,510,645 = 599,355. Candidates (ours, cheapest first): stop cloud 168,150 (May 14, Jun 14,
Jul 14), reduce dining to 665,950 (saves 684,073 per hit, May 14 ...), reduce entertainment to 755,250 (845,677, May 16 ...).
Cheapest-first accumulation takes cloud (helps, insufficient) then dining. The reference used dining alone.
* If monthly items recur at last + median gap (31 d) cloud lands on May 15 (payday), does not lower the May 14 trough,
  and the greedy yields `reduce_to:event_989:665950` alone with reserve 16,903,178 (+0.13 %, the closest variant) - but
  then May 15 passes by 31k and Jun 15 by 684k, contradicting Jul 15; on all samples earliest drops to 21/25 (06, 19 break).
* With a Jul 14 trough (rule in section 4) cloud saves 3 x 168,150 = 504,450 < 599,355 and still "helps", so cheapest-first
  still returns cloud + dining. A candidate order that tries `reduce` candidates (profile reduce list: dining,
  entertainment) before `stop` candidates fits request_11 and request_06 but turns request_21 into streaming + shopping
  (reference: cloud stop + streaming reduce). No single ordering fits 06, 11 and 21 together with a "raises the trough"
  test; the closest global fit remains cheapest-first, and request_11 is the exception (cost: one extra `stop`).
