# Trace: request_19 (user_19, INR, request 2024-09-04, requested 39,660)

Script: `code/notes/experiments/trace_request_19.py` (read-only against the engine; monkeypatches the
estimator to test alternatives across all samples).

## Reference reserve

`199,545 − 92,800 − 28,820 = 77,925`. Fixed pre-payday items are exact: rent 36,100 (09-04, request
date) + debt 11,850 (09-13) + cloud 395 (09-14) = **48,345**, so the five variable items must sum to
**29,580**. The salary (131,000) lands 09-15, the trough is 09-14, and the reserve is everything
projected on 09-04..09-14.

## Engine decomposition (means of csv rows, image row excluded)

| item | date | engine | note |
|---|---|---|---|
| rent | 09-04 | 36,100.00 | fixed |
| utilities | 09-08 | 5,955.64 | mean of 5 |
| groceries | 09-11 | 4,772.82 | mean of 25 csv rows; 08-28 + 7 = 09-04 skipped (request date) |
| healthcare | 09-12 | 8,808.57 | mean of 5 |
| transport | 09-12 | 3,080.13 | mean of 13, 14-day, 08-29 + 14 |
| debt | 09-13 | 11,850.00 | fixed |
| cloud | 09-14 | 395.00 | fixed |
| shopping | 09-14 | 5,833.87 | mean of 5 |
| **total** | | **76,796.03** | gap to 77,925 = **1,128.97 (1.45 %)** |

(`04_sample_rules.md` quotes 76,722 because it still had the image row in the grocery mean: 4,699.)

## Hypotheses tested (single change from the mean baseline)

| hypothesis | reserve | error |
|---|---|---|
| grocery anchor on 09-03 (→ 09-10) instead of 08-28 (→ 09-11) | 76,796 | −1.45 % (still one occurrence before payday) |
| request-date grocery occurrence (09-04) NOT skipped | 81,569 | +4.68 % |
| family_support 12,650 on payday reserved / debit-first | 89,446 | +14.8 % |
| image grocery 2,854 as an extra known debit | 79,650 | +2.21 % |
| grocery mean incl. image row (4,699) | 76,722 | −1.54 % |
| grocery mean of last 12 / 8 weeks | 76,755 / 76,737 | −1.5 % |
| all variables: median / last / last-3 / midrange | 76,591 / 75,385 / 75,927 / 76,945 | −1.7 / −3.3 / −2.6 / −1.3 % |
| all variables: max | 80,329 | +3.09 % |
| monthly variables max, groceries/transport mean | 78,262 | +0.43 % |
| grocery max only (6,070.85) | 78,094 | +0.22 % |
| all variables: p75 | 78,329 | +0.52 % |
| all variables: mean × 1.04 | 77,934 | +0.01 % |
| **all variables: mean + ½·pstdev** | **77,895.75** | **−0.04 %** |
| all variables: mean + ½·sample stdev | 77,971 | +0.06 % |
| all variables: mean + 1·pstdev | 78,995 | +1.37 % |

Arithmetic for mean + ½σ: utilities 6,068.52 + healthcare 9,035.00 + shopping 5,991.85 + groceries
5,161.93 + transport 3,293.45 = 29,550.75; + 48,345 = 77,895.75.

No combination of round-hundred (or multiple-of-50) nominals within ±8 % (±5 %) of the means sums to
29,580, so the hidden nominals are not "means rounded to hundreds".

## Cross-sample consistency (reserve error (got − want)/want, 21 uncapped samples)

| rule | mean abs err | within 2 % | within 1 % | request_19 |
|---|---|---|---|---|
| mean (engine) | 4.75 % | 9/21 | 4/21 | −1.4 % |
| median | 5.00 % | 7/21 | 4/21 | −1.7 % |
| midrange | 4.80 % | 9/21 | 6/21 | −1.3 % |
| last | 5.98 % | 6/21 | 1/21 | −3.3 % |
| mean of last 3 | 5.43 % | 6/21 | 3/21 | −2.6 % |
| max | 10.88 % | 3/21 | 3/21 | +3.1 % |
| mean + ½σ | 5.15 % | 4/21 | 3/21 | −0.0 % |
| mean × 1.04 | 5.52 % | 3/21 | 1/21 | +2.5 % |
| periodic request-date not skipped | 6.56 % | 6/21 | 3/21 | +4.7 % |
| image rows in mean | 4.83 % | 8/21 | 3/21 | −1.5 % |
| debit-first on payday | 6.14 % | 9/21 | 4/21 | +14.8 % |

mean + ½σ fixes request_19 but pushes 06, 07, 11, 13, 15, 17, 25 (all already over-reserved) further
out and drops "within 2 %" from 9 to 4. The signed errors under the mean rule are symmetric
(−16.8 … +9.7 %), which is what hidden per-category nominals with ±20–30 % monthly noise look like.

## Conclusion

* Structure is fully confirmed: one grocery occurrence before payday (anchor choice irrelevant), rent
  on the request date counted, family_support on payday not reserved, trough on 09-14.
* The single assumption that differs is the **amount of the variable series**: the reference uses the
  generator's hidden nominal amounts, which for user_19 sum to 29,580, i.e. 3.97 % above the 5-month
  means (equivalently mean + ½σ to within 0.04 %). No estimator of the supplied history reproduces
  this across the other samples; it is irreducible noise, not a rule. Keep the mean.
* Practical consequence: the engine's partial split (29,948.97 / 9,711.03) vs (28,820 / 10,840)
  cannot be closed without over-reserving elsewhere; the plan format, dates, status and method match.
