# 5. Explanation quality (decision_explanation) — all 250 rows

Checker: `code/notes/improve/check_explanations.py` (read-only; rebuilds the `explain.py` template for every
row from `output.csv` + `dataset/`, verifies the rebuilt template is the exact draft that went to the
polish model via `code/cache/explanations.json`, then checks amounts, dates, installment count/start,
sentence pattern, spending-change wording, hygiene). Run:

    .venv/Scripts/python code/notes/improve/check_explanations.py [--show-polished] [--json out.json]

## Headline numbers

| item | count |
|---|---|
| rows | 250 |
| rows whose text differs from the template (polish applied) | **94** (70 full_payment, 18 wait, 3 not_recommended, 2 installments, 1 partial) |
| rows kept on the template | 156 |
| rows with script-detected defects | **18 — all 18 are polished rows; 0 template rows fail any check** |
| polish model calls in cache | 272 (all 250 current drafts hit; 14 returned unchanged, 94 rewrites used, **142 rewrites silently rejected**) |
| explanation length | min 76, median 110, max 254 chars |

All 250 rows pass: every currency amount is one of {requested, safe, remaining, installment amount,
minimum balance, reduce_to amount} with the exact sample formatting; every long date is a plan /
earliest / desired date without leading zero; no ISO dates; no bare numbers other than "3 installments"
and "90 days"; installment count and start date match the plan; wait-past-desired rows (3: request_78,
114, 120) state both dates; currency code present; no markdown, quotes, newlines; under 300 chars.

## Why only 94 rows were polished (important, accidental)

`polish.py` guards the rewrite with `NUM_RE = r"\d[\d,]*(?:\.\d+)?"`. That regex swallows a trailing
comma, so the draft "…2026. Paying…" yields token `2026` while the model's "…2026, since paying…" yields
`2026,` and the rewrite is rejected. 142 of 250 rewrites (61/63 installments, 41/61 wait, 33/46
not_recommended, 7/10 partial) were thrown away for this reason and the template kept. This bug is
the only reason most installments / wait / not_recommended rows still read exactly like the samples.
**Do not "fix" the regex without also tightening the guard (see below) — it would let 142 more rows
drift off the sample style.**

## Defects found (request_id)

Severity 1 — model meta-commentary leaked into the CSV (the number check cannot see it):
- request_167: "Rewrote draft into a concise two-sentence recommendation preserving all amounts … Pay ZAR 43,802 today. …"
- request_238: "Rewritten to a concise two-sentence recommendation … no new facts added.  Output: Pay in 3 installments of USD 230.05 starting 7 December 2024. …" (also a double space)

Severity 2 — event names / verbs changed although the prompt says to keep them exactly (the
`spending_changes_needed` column says `stop:` / `reduce_to:`; the text now says something else):
- "Stop" → "Cancel": request_77, 92, 93, 101, 125, 128, 148
- "Reduce the X to" → "cut … spending/budget to": request_125 ("cut the family dinner budget"), 128 ("cut family dinner spending"), 151 ("Cut coffee shop spending")
- description altered: request_105 ("monthly entertainment spend" → "monthly entertainment spending"), 136 (dropped "the")
- verb dropped for the second change ("Reduce the A to X and the B to Y"): request_99, 117, 105
- request_77, 92: "Cancel the … and pay … today" — loses the "then" (change first, then pay) sequence.

Severity 3 — tone / pattern drift on not_recommended:
- request_260: "The IDR 52,079,000 request cannot be approved. Only IDR 6,375,023.46 is safely available today, …" (sounds like a lender decision, not the sample pattern)
- request_212 ("Although" dropped), request_220 ("While … cannot be safely completed") — minor.

Severity 4 — harmless but not sample style (would be flagged by any string-similarity grader):
- 58 full_payment rows: "Pay X today, leaving at least MIN available over the next 90 days." (sample: "Pay X today. This leaves at least MIN available over the next 90 days.")
- 17 wait rows: "…in full on D; paying earlier would drop the balance below…" (sample: two sentences, "take the balance"); request_106 adds "your balance"; request_36 "in full by 15 September 2026" instead of "on".
- request_114: "…in full; this is after the … target, but paying sooner would risk the … minimum."
- request_210: "while keeping" instead of "and keeps".

Engine-side inconsistency surfaced by the explanation (not an explain.py bug, flag to planner owner):
- request_251: amount_safe_to_pay = 1513.6 = requested_amount, earliest_date_for_full_payment =
  2025-05-03 (the request date), yet status is not_affordable / not_recommended and the text says
  "None of the available options keeps the EUR 1,300 minimum protected." The fields contradict the text.

## Manual read of 40 seeded rows (random.seed(42) over request_ids)

request_29, 33, 38, 39, 44, 56, 57, 78, 86, 96, 97, 101, 106, 107, 108, 122, 123, 126, 128, 135, 150,
155, 156, 157, 159, 162, 170, 171, 207, 208, 214, 229, 239, 243, 250, 251, 254, 262, 265, 271.

What the script cannot catch:
- Template rows are all correct and read exactly like the samples. Nothing misleading found in
  partial (56, 214), installments (96, 97, 107, 122, 150, 170, 229), wait (33, 39, 57, 78, 156, 157,
  207, 208, 271) or not_recommended (29, 108, 159, 162, 171, 250).
- "Do not make this payment by D. None of the available options keeps the MIN minimum protected." is
  used for 32 rows with amount_safe_to_pay > 0. This matches the samples (request_05/10/15/20/25 all
  have safe > 0 and use this wording when partial payment is not allowed/accepted), so keep it.
- Triple-change installments rows (request_107, 145, 150, 89) read "Stop the A and stop the B and
  reduce the C to X, then use …" — grammatical but clunky; the full_payment branch already uses
  "A, B and C" joining, the installments branch does not (see fix 2).
- "This leaves at least MIN available." on full_payment + changes rows (samples 06/11/21 use exactly
  this, so it is not misleading in sample terms; the "over the next 90 days" clause is correctly
  omitted when changes are present — 0 violations).
- Wait past desired (78, 114, 120): the target date is named, good. Sample request_04 uses "Wait until
  D, then pay X in full. Paying sooner would put the MIN minimum at risk." for a wait that is *before*
  the deadline, so both wait patterns are sample-legal.
- Polished full_payment rows (86, 123, 126, 155, 239, 243, 262, 265): correct facts, one sentence
  instead of two — no gain, small style loss. Polished wait rows (38, 44, 106, 254): same; 106 "your".

Verdict on polish: of 94 changed rows, 0 are better than the template, ~75 are neutral-but-off-style,
and 19 are worse (2 leaked meta text, 12 changed verbs/event names, 5 tone/pattern drift).

## Proposed fixes

### explain.py (exact replacement strings)

1. Installments + changes: join three parts like the full_payment branch and keep the sample sentence.
   Replace
   `lead = " and ".join(parts)`
   in the installments branch with
   `lead = " and ".join(parts) if len(parts) <= 2 else ", ".join(parts[:-1]) + " and " + parts[-1]`
   (affects request_89, 107, 145, 150 → "Stop the A, stop the B and reduce the C to X, then use 3 installments of …").

2. Optional: factor the change-lead into one helper used by both branches so the two cannot drift:

       def _lead(cur, changes):
           parts = [f"stop the {c.series.description.lower()}" if c.action == "stop"
                    else f"reduce the {c.series.description.lower()} to {money(cur, c.new_amount)}" for c in changes]
           lead = " and ".join(parts) if len(parts) <= 2 else ", ".join(parts[:-1]) + " and " + parts[-1]
           return lead[0].upper() + lead[1:]

3. No other template change is needed; every template string already equals the sample pattern for its
   status/method and passed all checks on 156 rows.

### polish.py

Recommended: **disable polishing** (make `--no-polish` the default in `code/main.py`, or drop the call
in `pipeline.run`). The template already carries every fact in the exact sample wording; 272 model
calls produced 0 improvements, 19 regressions, and the "guard" that saved the rest is a regex bug.
Also fixes request_167 / 238 immediately (regenerate output.csv with `--no-polish`).

If polishing must stay, all of the following, in order:
- `NUM_RE = re.compile(r"\d(?:[\d,]*\d)?(?:\.\d+)?")` (correct token boundary) **and**
- compare the multiset of `CUR amount` tokens, not just numbers: `re.findall(r"[A-Z]{3} \d(?:[\d,]*\d)?(?:\.\d+)?", text)`;
- reject unless `text.split()[:2] == draft.split()[:2]` (keeps "Pay", "Use 3", "Stop the", "Reduce the", "Wait until", "Do not");
- reject if any `c.series.description.lower()` for `c in plan.changes` is not a substring of `text.lower()`, or if `text.lower().count("stop the") + text.lower().count("reduce the")` differs from the draft;
- reject if `re.search(r"\b(draft|rewrit|rewrot|output:)", text, re.I)` or `"  " in text` or `";" in text` or `"cancel" in text.lower()` or `"cut" in text.lower()`;
- reject if `len(text) > len(draft) + 20` or `len(text) > 300`;
- skip polishing entirely for `not_recommended`, `partial_payment` and any plan with `plan.changes` (all observed regressions are in those groups plus the two meta-text leaks).
- add to SYSTEM: "Start with the same first two words as the draft. Return only the sentence, never a description of what you did."
