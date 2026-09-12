# 1 — Noise-band calibration and the fixed-category estimator (improve2 / subagent 1)

Script: `code/notes/improve2/1_noise_band.py [band|fixed|est|variants|detail|grid250|all]` (engine untouched; subclasses
`StateBuilder` and re-estimates only the non-leaked variable series; deterministic evidence path, `use_llm=False`).
Baseline reproduced before starting: `code/evaluation/main.py --table` = 121/150 columns, 17/25 within 2 %.

## 1. The noise band of the leaked series (nominal = k × minimum_allowed_amount)

r = observed / nominal for every event of every series with a constant minimum (k = 2.0 dining/entertainment/gym/streaming,
2.5 shopping; all 349 recovered nominals lie on the currency grid EUR/USD 1, INR 10, IDR 100, ZAR 0.2 — 100 % hits).
No leaked series has an event currency different from the home currency.

| category | cur | n | min r | max r | mean r | skew | a_hat | KS p vs U[clean] | chi² p |
|---|---|---|---|---|---|---|---|---|---|
| dining | EUR | 416 | 0.7205 | 1.2794 | 0.992 | +0.09 | 0.281 | 0.45 | 0.52 |
| dining | IDR | 349 | 0.7203 | 1.2783 | 0.999 | +0.05 | 0.281 | 0.87 | 0.91 |
| dining | INR | 468 | 0.7215 | 1.2800 | 0.995 | 0.00 | 0.280 | 0.81 | 0.31 |
| dining | USD | 261 | 0.7227 | 1.2795 | 0.993 | +0.02 | 0.281 | 0.59 | 0.11 |
| dining | ZAR | 431 | 0.7203 | 1.2794 | 1.022 | −0.16 | 0.281 | **0.008** | 0.08 |
| entertainment | EUR | 20 | 0.8851 | 1.1146 | 0.971 | +0.32 | 0.127 | 0.06 | 0.02 |
| entertainment | IDR | 60 | 0.8853 | 1.1187 | 1.005 | −0.01 | 0.121 | 0.47 | 0.30 |
| entertainment | INR | 65 | 0.8809 | 1.1177 | 1.006 | −0.21 | 0.122 | 0.30 | 0.36 |
| entertainment | USD | 35 | 0.8900 | 1.1152 | 0.991 | +0.28 | 0.119 | 0.17 | 0.36 |
| entertainment | ZAR | 40 | 0.8814 | 1.1132 | 1.008 | −0.29 | 0.122 | 0.48 | 0.79 |
| shopping | EUR | 65 | 0.8804 | 1.1166 | 1.001 | −0.19 | 0.122 | 0.78 | 0.38 |
| shopping | IDR | 50 | 0.8801 | 1.1148 | 1.005 | −0.02 | 0.122 | 0.57 | 0.19 |
| shopping | INR | 110 | 0.8837 | 1.1196 | 1.004 | +0.01 | 0.120 | 0.53 | 0.61 |
| shopping | USD | 60 | 0.8814 | 1.1186 | 1.000 | −0.07 | 0.123 | 0.74 | 0.12 |
| shopping | ZAR | 75 | 0.8820 | 1.1095 | 0.992 | +0.19 | 0.117 | 0.78 | 0.92 |
| **dining** | all | 1925 | 0.7203 | 1.2800 | 1.001 | −0.01 | **0.2801** | 0.60 | 0.52 |
| **entertainment** | all | 220 | 0.8809 | 1.1187 | 1.000 | −0.03 | **0.1200** | 0.48 | 0.48 |
| **shopping** | all | 360 | 0.8801 | 1.1196 | 1.000 | 0.00 | **0.1204** | 0.995 | 0.90 |
| gym / streaming | all | 70 / 332 | 1.0000 | 1.0000 | constant | | | | |

(a_hat = (max−min)/2 · (n+1)/(n−1), unbiased for the half-width under uniform noise; KS against U[0.72,1.28] / U[0.88,1.12];
chi² over 10 equal bins.)

* **Band edges are clean**: dining [0.72, 1.28], entertainment and shopping [0.88, 1.12]. The sample extremes sit exactly where
  a uniform draw puts them (expected gap width/(n+1): dining 0.00029, observed 0.00026 / 0.00003; entertainment 0.00109,
  observed 0.00093 / 0.00127; shopping 0.00066, observed 0.00010 / 0.00041). No value crosses the clean edge.
* **Symmetric and flat**: pooled mean r = 1.001 / 1.000 / 1.000, skew ≈ 0; 0.02-wide histogram bins are flat (dining 56–85
  per bin around 69; shopping 26–39 around 30). KS and chi² accept uniformity on every pooled category and on 19 of the 20
  category × currency cells. The one rejection (dining/ZAR, mean r 1.022, p = 0.008) is a 2.8σ fluctuation of the mean over
  431 draws: its edges are the same 0.7203/1.2794, no individual ZAR series is outside the band, and the two highest series means
  (user_01 1.11, user_140 1.11, n = 13) are 2.5σ events. Entertainment/EUR (n = 20) is small-sample noise.
* **The band depends on the category only, not on the currency**: a_hat per currency 0.280–0.281 (dining) and 0.117–0.127
  (entertainment/shopping, all within ±0.007 of 0.12 with n = 20–110).

## 3. Do the fixed (non-leaked) categories share the band? — Yes, exactly

Per-series s = (max−min)/(max+min) for every variable series (leaked and fixed), all users:

| category | leaked | series | n/series | max s | mean a_hat | median a_hat | implied a |
|---|---|---|---|---|---|---|---|
| groceries | no | 275 | 21.1 | 0.2789 | 0.2796 | 0.2851 | 0.28 |
| transport | no | 275 | 20.4 | 0.2787 | 0.2810 | 0.2832 | 0.28 |
| dining | no | 97 | 16.0 | 0.2759 | 0.2756 | 0.2804 | 0.28 |
| dining | yes | 153 | 12.6 | 0.2784 | 0.2794 | 0.2851 | 0.28 |
| utilities | no | 275 | 5.2 | 0.1195 | 0.1219 | 0.1269 | 0.12 |
| healthcare | no | 68 | 5.0 | 0.1145 | 0.1135 | 0.1148 | 0.12 |
| shopping | no | 70 | 5.0 | 0.1184 | 0.1242 | 0.1284 | 0.12 |
| shopping | yes | 72 | 5.0 | 0.1180 | 0.1202 | 0.1255 | 0.12 |
| entertainment | no | 60 | 5.0 | 0.1123 | 0.1214 | 0.1277 | 0.12 |
| entertainment | yes | 44 | 5.0 | 0.1147 | 0.1212 | 0.1215 | 0.12 |

The maximum s never exceeds the band's a (a series cannot have s > a under U[1−a, 1+a]), and the unbiased a_hat agrees with the
leaked categories to ±0.006. So `observed = nominal × U(0.72, 1.28)` for groceries / transport / dining and `× U(0.88, 1.12)`
for utilities / healthcare / shopping / entertainment, leaked or not. A data-driven rule reproduces this exactly:
a(category) = max over series of s, rounded up to 0.02.

## 2. Estimators for the fixed block — full scorer on the 25 samples

Every estimator uses the feasible interval [L, U] = [max/(1+a), min/(1−a)] (the nominal must lie inside it). Columns: six
scored columns exact /150 (baseline 121), within 1 % / 2 %, mean |rel| reserve error over the 21 uncapped samples, normalised
total |gap| (EUR/USD 1, ZAR 10, INR 100, IDR 10 000), raw total |gap|.

| estimator for fixed series | w1 % | w2 % | mean rel | med rel | normAbs | total gap | cols /150 | columns lost / gained |
|---|---|---|---|---|---|---|---|---|
| (d) mean — engine | 12 | 17 | 2.62 % | 1.02 % | 753.0 | 2,459,466 | 121 | — |
| midrange (max+min)/2 | 14 | 16 | 2.58 % | 0.76 % | 784.6 | 2,474,376 | 118 | lost request_11 status/method/plan |
| (a) imid = (L+U)/2 | 15 | 16 | 2.54 % | 0.77 % | 753.5 | 2,539,148 | 118 | lost request_11 ×3 |
| (b) MLE proper = L (lower endpoint) | 8 | 10 | 3.69 % | 2.25 % | 1045.1 | 3,368,099 | 119 | lost request_11 ×3, gained 17 earliest |
| (b') posterior mean, flat prior, density ∝ n^−N | 13 | 16 | 2.58 % | 0.71 % | 780.5 | 2,503,810 | 118 | lost request_11 ×3 |
| (c) imid snapped to grid in [L,U] | 15 | 16 | 2.56 % | 0.75 % | 760.4 | 2,539,003 | 118 | lost request_11 ×3 |
| round mean to grid (no interval) | 10 | 17 | 2.60 % | 1.02 % | 748.4 | 2,459,492 | 121 | — |
| **clamp mean into [L,U]** (no grid) | 13 | 17 | 2.50 % | 1.02 % | 735.2 | 2,452,496 | 121 | — |
| **clamp mean into [L,U] + snap to grid** | **13** | **17** | **2.42 %** | 0.88 % | **725.2** | **2,452,558** | **123** | **gained request_08 and request_18 amount exact** |
| same, band × 1.05 or × 0.95 | 13 | 17 | 2.42 % | 0.88 % | 725.2 | 2,452,558 | 123 | identical |
| same, ZAR grid 1 instead of 0.2 | 13 | 17 | 2.42 % | 0.88 % | 726.6 | 2,452,572 | 123 | identical |
| same, grid × 5 | 14 | 17 | 2.42 % | 0.78 % | 729.3 | 2,451,861 | 121 | loses both exact amounts |
| snap only when the interval holds 1 grid point | 11 | 17 | 2.52 % | 0.89 % | 736.8 | 2,459,450 | 121 | — |
| snap only when ≤ 2 grid points | 12 | 17 | 2.50 % | 0.89 % | 734.8 | 2,459,448 | 122 | gained request_08 |
| clamp+snap, wide categories only | 13 | 17 | 2.46 % | 0.92 % | 734.4 | 2,452,781 | 122 | gained request_08 |
| clamp+snap, narrow categories only | 11 | 17 | 2.59 % | 1.02 % | 744.5 | 2,459,293 | 121 | — |

Notes on (b): the likelihood of a uniform band is (2an)^−N on [L, U], so the true MLE is the lower endpoint L; it is biased
low by ~a/N and is clearly the worst estimator here (w2 10/25). The midpoint (a) and the posterior mean (b') are the
MLE-consistent, unbiased choices — and both flip request_11 (reserve +1.02 % → +0.46…0.60 %) from full-with-changes to
`wait`, exactly as the previous pass found, because they move every series, including the ones whose mean is already
feasible. The **clamp** only moves a mean that the noise model proves impossible (29 of the 102 fixed series in the samples;
none in request_11), so it can never flip a knife-edge sample the mean gets right.

Why two samples become exact: EUR/USD nominals are integers and the feasible interval of a long groceries/transport
series is only 0.2–4 units wide, so the interval plus the grid pins the nominal.
request_08: groceries mean 59.04 but [L,U] = [61.27, 63.88] → 62; transport [36.88, 37.07] → 37; utilities 76.83 → 77;
reserve becomes exactly 452, answer 284.57. request_18: groceries mean 93.42 but [89.84, 90.06] → 90; utilities 111.27 vs
[111.96, 114.31] → 112; answer exactly 462. (`detail` mode prints every series.)

Well-determinedness of snapping (grid points inside [L, U], all 1,018 fixed series of the 250 evaluation users):
EUR 39 one-point / 35 two-point / 141 more (median width 3.5 units); USD 30 / 14 / 122 (4.3); INR 4 / 6 / 241 (30);
IDR and ZAR always ≥ 3 (median 513 and 351 units). So the grid is decisive only for ~1/3 of EUR/USD series; elsewhere the
snap is a harmless rounding and the clamp is the whole effect. The mean lies outside its feasible interval in 45 % of
groceries and transport series, 27 % dining, 16 % utilities, 19 % shopping, 11 % entertainment, 8 % healthcare, by 1–2.4 % on
average (max 9.8 %).

## 4. Recommendation

**Switch the fixed-category estimator from the plain mean to the mean clamped into the feasible interval and snapped to the
currency grid** (`x = min(max(mean, max/(1+a)), min/(1−a))`, then the nearest grid point inside the interval; a = 0.28 for
groceries/transport/dining, 0.12 for utilities/healthcare/shopping/entertainment, grid EUR/USD 1, INR 10, IDR 100, ZAR 0.2).

* It is a strict refinement of the mean: unchanged whenever the mean is compatible with the noise model, so no plan changes
  (121 → 123 columns, nothing lost; request_11 untouched), and it is the only estimator in the table that improves every
  aggregate at once: normAbs 753 → 725 (−3.7 %), mean |rel| 2.62 → 2.42 %, within-1 % 12 → 13, within-2 % 17 → 17.
* It is robust: identical results with the band scaled ±5 % and with the ZAR grid at 1 instead of 0.2; the exact band
  (section 3) and the grid (section 1) are both verified on the whole dataset, not on the samples.
* Keep both parameters data-derived, not hardcoded: a(category) = max over series of (max−min)/(max+min) rounded up to 0.02
  reproduces 0.28/0.12 exactly; the grid is the largest unit that divides every recovered leaked nominal per currency.
* Do **not** adopt midrange, imid, the MLE endpoint or the posterior mean: each loses request_11's three columns for no gain
  within 2 %.
* Honest size of the effect: two EUR samples become exact because the integer grid pins a narrow interval; on IDR/INR/ZAR
  the change is a 1–2 % shift of one or two series in ~40 % of requests, worth ~0.3 % of a reserve. The remaining error is
  still structural (04, 06, 10, 13, 15 — occurrence counts, not amounts).
