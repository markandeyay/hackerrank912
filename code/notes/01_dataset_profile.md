# 01 - Dataset profile (Buy or Wait?)

Profiled with pandas 3.0 on the files in `dataset/`. All CSVs were read as strings (`dtype=str, keep_default_na=False`) so blanks are real blanks. Every number below was computed, not estimated. Section 9 (Gotchas) is the part to read first when designing the engine.

Files: financial_profiles (275 rows), financial_events (25,342), exchange_rates (134), requests (250), sample_requests (25), request_payment_options (790), messages (215), images (16), output (250 blank rows). All files use CRLF line endings, no BOM. `messages.csv` is UTF-8 and contains U+2019 curly apostrophes (`We’ll`); read it with `encoding="utf-8"`. `requests.csv` has 6 non-ASCII bytes (same curly apostrophes). All other files are pure ASCII. No leading/trailing whitespace anywhere; no case inconsistencies in any categorical column.

---

## 1. Exact schema, nulls, unique counts

### financial_profiles.csv (275 x 10)
| column | blank | unique | notes |
|---|---|---|---|
| user_id | 0 | 275 | user_01..user_275 |
| home_currency | 0 | 5 | INR 67, EUR 62, IDR 55, ZAR 51, USD 40 |
| current_available_balance | 0 | 275 | numeric, 683.69 .. 136,691,818.94 |
| minimum_balance_to_keep | 0 | 192 | numeric, 400 .. 41,430,800 |
| financial_priorities | 0 | 9 | pipe-separated, always 2 tokens |
| expense_categories_to_protect | 0 | 8 | pipe-separated, 3-4 tokens |
| expense_categories_user_is_willing_to_reduce | 39 | 19 | pipe-separated |
| expense_categories_user_is_willing_to_stop | 62 | 11 | pipe-separated |
| payment_methods_user_will_consider | 0 | 7 | pipe-separated |
| max_installment_months | 119 | 12 | integer 2..12; blank iff `installments` not in methods |

### financial_events.csv (25,342 x 14)
| column | blank | unique | notes |
|---|---|---|---|
| event_id | 0 | 25342 | event_1..event_25342, monotonically increasing in file order |
| user_id | 0 | 275 | |
| event_type | 0 | 8 | |
| description | 0 | 164 | |
| category | 0 | 22 | |
| direction | 0 | 3 | debit / credit / non_cash |
| amount | 16 | 17786 | numeric 2.0 .. 48,830,000; no negatives; 16 blanks (all have an image) |
| currency | 0 | 5 | |
| event_date | 0 | 1308 | YYYY-MM-DD |
| settlement_date | 10 | 1311 | blank only for the 10 `unrealized` valuations |
| status | 0 | 6 | |
| linked_event_id | 25284 | 59 | 58 populated rows |
| flexibility | 0 | 4 | |
| minimum_allowed_amount | 22435 | 302 | populated on exactly the 2,907 reducible / reducible_or_stoppable rows |

Amount decimals: 16,602 rows with 2 dp, 2,807 with 1 dp, 5,933 integers. `minimum_allowed_amount`: 1,779 integers, 1,073 with 1 dp, 55 with 2 dp.

### exchange_rates.csv (134 x 4)
`rate_date` (39 unique), `from_currency` (USD 88, EUR 46), `to_currency` (INR 33, IDR 30, EUR 25, USD 24, ZAR 22), `rate` (5 distinct values). No duplicate (date, from, to).

### requests.csv (250 x 8) and sample_requests.csv (25 x 15)
| column | blank | unique (eval / sample) |
|---|---|---|
| request_id | 0 | 250 / 25 (request_26..275 / request_01..25) |
| user_id | 0 | 250 / 25 (one request per user; user number == request number) |
| request_date | 0 | 61 / 25 |
| request_type | 0 | 9 / 9 |
| requested_amount | 0 | 248 / 25 (187 integers, 79 one-dp, 9 two-dp) |
| desired_completion_date | 0 | 170 / 24 |
| allows_partial_payment | 0 | `true` / `false` (lower-case strings) |
| request_text | 0 | 250 / 25 |
Sample-only output columns: amount_safe_to_pay (0 blank), affordability_status (4 values), recommended_payment_method (5 values), payment_plan (19 unique), earliest_date_for_full_payment (7 blank = the 6 not_affordable rows + 1), spending_changes_needed (4 unique), decision_explanation.

### request_payment_options.csv (790 x 9)
| column | blank | unique | notes |
|---|---|---|---|
| payment_option_id | 0 | 790 | payment_option_01..790, increasing within each request |
| request_id | 0 | 275 | covers all 250 eval + 25 sample requests |
| payment_method | 0 | 2 | installments 515, full_payment 275 |
| payment_amount | 0 | 787 | 7.29 .. 83,923,000 (404 two-dp, 119 one-dp, 267 integer) |
| number_of_payments | 0 | 9 | 1:275, 24:96, 15:89, 21:88, 18:87, 3:80, 6:65, 2:7, 4:3 |
| first_payment_date | 0 | 194 | |
| payment_frequency_days | 275 | 4 | blank for full_payment; 28:180, 31:169, 30:166 |
| financing_fee | 0 | 515 | 0 for every full_payment row |
| total_payable_amount | 0 | 787 | |

### messages.csv (215 x 7)
`message_id` (215 unique), `user_id` (215 unique: exactly one message per user, 215 of 275 users), `request_id` (87 blank), `related_event_id` (176 blank), `sent_at` (ISO-8601 with `Z`, 120 unique), `source_type` (5), `message_text` (215 unique).

### images.csv (16 x 4)
`image_id` image_01..16, `user_id`, `request_id`, `related_event_id` all populated and unique. All 16 PNGs exist in `dataset/media/images/` (111 KB .. 756 KB).

### output.csv (250 x 8)
Header only + 250 rows with request_id filled (request_26..request_275) and all other columns blank.

---

## 2. Categorical distributions

### financial_events
- event_type: expense 20,525; subscription 2,488; income 1,696; debt_payment 567; investment_purchase 29; refund 22; investment_valuation 10; investment_sale 5.
- category: groceries 5,812; transport 5,626; dining 3,479; salary 1,690; utilities 1,452; rent 1,355; cloud_storage 833; shopping 813; streaming 683; debt_repayment 553; entertainment 521; insurance 456; music_subscription 451; healthcare 356; delivery_membership 351; education 306; housing 246; gym 170; family_support 125; investment 44; work_expense 14; windfall 6.
- direction: debit 23,609; credit 1,723; non_cash 10.
- currency: INR 6,457; EUR 5,585; IDR 4,992; ZAR 4,489; USD 3,819.
- status: settled 25,148; pending 71; scheduled 70; cancelled 22; failed 21; unrealized 10.
- flexibility: fixed 21,138; reducible 2,682; stoppable 1,297; reducible_or_stoppable 225.

event_type x category is one-to-one except: `utilities` is expense (1,438) + debt_payment (14 = failed attempts and retries); `shopping` is expense (798) + refund (15); `work_expense` is expense (7) + refund (7); `investment` splits into purchase 29 / sale 5 / valuation 10; `salary` and `windfall` are the only income categories.

flexibility x category: only these categories ever carry non-fixed rows: dining (reducible 1,925), shopping (reducible 360), entertainment (reducible 220), streaming (reducible 127 / reducible_or_stoppable 205 / stoppable 215), gym (50 / 20 / 40), cloud_storage (stoppable 547), delivery_membership (stoppable 205), music_subscription (stoppable 290). Everything else (rent, groceries, transport, utilities, salary, debt, insurance, education, healthcare, housing, family_support, investment, windfall, work_expense) is 100% fixed. Income and all non-subscription/expense types are fixed.

### financial_profiles
- home_currency: INR 67, EUR 62, IDR 55, ZAR 51, USD 40.
- payment_methods_user_will_consider: full_payment 60; partial_payment|installments 52; installments 41; full_payment|partial_payment 40; full_payment|installments 35; full_payment|partial_payment|installments 28; partial_payment 19. Token totals: full_payment 163, installments 156, partial_payment 139.
- max_installment_months: blank 119; 3:18, 4:17, 12:16, 11:16, 5:16, 2:15, 7:14, 6:13, 10:12, 8:10, 9:9. Blank exactly for the 119 users whose methods exclude installments; all 156 installment-considering users have a value.
- financial_priorities (9 combos): emergency_savings|travel 46; retirement_investment|emergency_savings 42; education|debt_repayment 36; education|emergency_savings 34; emergency_savings|housing 29; healthcare|family_support 25; education|family_support 24; debt_repayment|emergency_savings 20; healthcare|retirement_investment 19.
- expense_categories_to_protect (8 combos): rent|groceries|transport 63; rent|insurance|transport 46; rent|utilities|groceries 42; rent|education|groceries|debt_repayment 36; rent|healthcare|family_support|groceries 25; housing|utilities|education 24; rent|utilities|debt_repayment 20; housing|healthcare|utilities 19. Tokens: rent 232, groceries 166, transport 109, utilities 105, education 60, debt_repayment 56, insurance 46, healthcare 44, housing 43, family_support 25.
- willing_to_reduce tokens: dining 153, shopping 72, streaming 66, entertainment 44, gym 14; 39 users blank. Top combos: dining 80, shopping 35, dining|streaming 22, dining|entertainment 20, streaming 17.
- willing_to_stop tokens: cloud_storage 109, streaming 84, music_subscription 58, delivery_membership 41, gym 12; 62 users blank. Top combos: cloud_storage 57, streaming|cloud_storage 52, streaming 32, music_subscription 26, music_subscription|delivery_membership 24.
- 10 users have both reduce and stop blank. 45 users list the same category (streaming or gym) in both reduce and stop. Protect never overlaps reduce or stop (0 users).

### requests / sample_requests
- request_type (eval): family_transfer 28, purchase 28, investment 28, debt_repayment 28, travel 28, housing 28, education 28, emergency_expense 27, other 27. Sample: 3 each, except emergency_expense 2 and other 2.
- allows_partial_payment: eval false 170 / true 80; sample false 13 / true 12.

### request_payment_options
- payment_method: installments 515, full_payment 275. number_of_payments and payment_frequency_days as in the schema table.

### messages
- source_type: employer 126, service_provider 31, financial_service 23, bank 18, merchant 17.

### exchange_rates
- from_currency: USD 88, EUR 46. to_currency: INR 33, IDR 30, EUR 25, USD 24, ZAR 22.

---

## 3. financial_events.csv deep dive

### 3.1 status x direction x event_type
| status / direction | debt_payment | expense | income | inv_purchase | inv_sale | inv_valuation | refund | subscription | total |
|---|---|---|---|---|---|---|---|---|---|
| cancelled / debit | 0 | 22 | 0 | 0 | 0 | 0 | 0 | 0 | 22 |
| failed / debit | 7 | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 21 |
| pending / credit | 0 | 0 | 0 | 0 | 0 | 0 | 8 | 0 | 8 |
| pending / debit | 0 | 63 | 0 | 0 | 0 | 0 | 0 | 0 | 63 |
| scheduled / credit | 0 | 0 | 47 | 0 | 0 | 0 | 0 | 0 | 47 |
| scheduled / debit | 7 | 16 | 0 | 0 | 0 | 0 | 0 | 0 | 23 |
| settled / credit | 0 | 0 | 1649 | 0 | 5 | 0 | 14 | 0 | 1668 |
| settled / debit | 553 | 20410 | 0 | 29 | 0 | 0 | 0 | 2488 | 23480 |
| unrealized / non_cash | 0 | 0 | 0 | 0 | 0 | 10 | 0 | 0 | 10 |

Every credit is income, refund, or investment_sale. Every non_cash row is an unrealized investment_valuation. All subscriptions, debt payments and investment purchases are settled debits (plus 7 scheduled debt retries and 7 failed debt attempts).

### 3.2 Blank amount rows (16) - all have an image
| event_id | user | request | type/category | description | currency | event_date | settlement | status | image |
|---|---|---|---|---|---|---|---|---|---|
| event_253 | user_03 | request_03 | income/salary | August 2019 net salary | IDR | 2019-08-31 | 2019-08-31 | settled | image_01 |
| event_1442 | user_16 | request_16 | expense/rent | Outstanding rent balance | INR | 2023-08-11 | 2023-08-16 | scheduled | image_02 |
| event_1545 | user_17 | request_17 | expense/groceries | Bulk groceries and pantry purchase | INR | 2026-02-27 | 2026-02-27 | settled | image_03 |
| event_1700 | user_19 | request_19 | expense/groceries | Delivered grocery order | INR | 2024-09-03 | 2024-09-03 | settled | image_04 |
| event_1786 | user_20 | request_20 | expense/utilities | Outstanding telecom bill | INR | 2026-02-06 | 2026-02-09 | pending | image_05 |
| event_3051 | user_33 | request_33 | expense/groceries | Grocery tax invoice | INR | 2026-01-06 | 2026-01-06 | settled | image_06 |
| event_3231 | user_35 | request_35 | expense/dining | Restaurant tax invoice | INR | 2025-10-29 | 2025-10-29 | settled | image_07 |
| event_4535 | user_48 | request_48 | expense/housing | Property maintenance invoice | INR | 2026-07-24 | 2026-07-24 | settled | image_08 |
| event_5170 | user_55 | request_55 | expense/utilities | Water bill due | INR | 2026-06-07 | 2026-06-07 | settled | image_09 |
| event_6033 | user_64 | request_64 | expense/groceries | Large grocery tax invoice | INR | 2024-06-03 | 2024-06-10 | pending | image_10 |
| event_6859 | user_73 | request_73 | expense/healthcare | Hospital bill payable | INR | 2023-01-19 | 2023-01-23 | scheduled | image_11 |
| event_7307 | user_78 | request_78 | expense/transport | Taxi fare | **USD** (home INR) | 2025-10-01 | 2025-10-01 | settled | image_12 |
| event_7941 | user_84 | request_84 | expense/shopping | Tote bag order | INR | 2026-04-03 | 2026-04-03 | settled | image_13 |
| event_9421 | user_101 | request_101 | expense/healthcare | Pharmacy purchase | INR | 2025-11-02 | 2025-11-02 | settled | image_14 |
| event_9806 | user_105 | request_105 | expense/transport | Airline ticket purchase | INR | 2026-06-07 | 2026-06-07 | settled | image_15 |
| event_10521 | user_113 | request_113 | expense/transport | EV charging wallet payment | INR | 2026-09-03 | 2026-09-03 | settled | image_16 |

The 16 blank-amount event_ids are exactly the 16 `images.related_event_id` values (no image without a blank, no blank without an image). All are one-off descriptions (never recur). 13 are `settled` (already reflected in the balance, so the amount matters only for recurrence/explanations), 2 are `pending` debits (event_1786 telecom bill, event_6033 grocery invoice: must be reserved) and 1 is `scheduled` (event_1442 rent balance, event_6859 hospital bill is also scheduled: both must be reserved). Image contents seen so far: image_01 is an Indonesian pay slip with Net Pay IDR 4,365,000 (identical to user_03's regular monthly `Payroll credit`); image_12 is a taxi receipt with Total $33.50 (USD, needs USD->INR 2025-10-01 = 83.33, which is the only non-15th rate row); image_05 is an Airtel bill showing "Amount due till 06-Feb-2026 = 704.05" and "Amount due after 06-Feb-2026 = 822.05" while the event settles 2026-02-09 (after the due date) - decide which figure to use (conservative = 822.05).

### 3.3 Foreign-currency rows (currency != home_currency): 140 rows, 27 users
- 139 are salary income (`International employer payroll` 55 rows / `Payroll credit` 78 / `Next confirmed salary` 8 scheduled) + 1 expense (event_7307 USD taxi, blank amount).
- Pairs: USD->INR 54 (52 settled + 2 scheduled), USD->IDR 28 (25+3), USD->EUR 22 (20+2), EUR->ZAR 20, EUR->USD 16 (15+1). Direction is always credit except the taxi.
- settlement_date == event_date for all 140. An `exchange_rates` row for (settlement_date, currency -> home_currency) exists for **all 140**; the reverse pair exists too for 27 rows (the EUR<->USD ones only). 33 exchange-rate rows are not used by any event.
- Users with foreign salaries: 25, 39, 41, 48, 63, 64, 71, 79, 84, 98, 109, 113, 125, 153, 169, 173, 183, 184, 214, and 8 more (all 15th-of-month payroll). For these users the projected future salary must be converted using the rate row for the projected settlement date (rates are constant per pair, so any date works in practice; see section 4).

### 3.4 minimum_allowed_amount vs amount and flexibility
- Populated on 2,907 rows = exactly all `reducible` (2,682) and `reducible_or_stoppable` (225) rows; never on `stoppable` or `fixed`.
- ratio `minimum_allowed_amount / amount`: min 0.357, 25% 0.433, median 0.500, 75% 0.541, max 0.694. Never greater than amount. For subscriptions the ratio is exactly 0.50 (e.g. streaming 47 -> 23.5, 560500 -> 280250).
- For a recurring reducible series (same user + description) the `minimum_allowed_amount` is constant across occurrences even though `amount` varies (e.g. user_01 dining rows all carry 489.5).
- In the sample solutions `reduce_to:<event_id>:<new_amount>` uses exactly the event's `minimum_allowed_amount` (event_989 -> 665950, event_1816 -> 23.5) and references the **latest occurrence** of that series (event_989 is the last "Weekend food delivery" row; event_476 / event_1815 / event_1816 are the last rows of their monthly subscription series).

### 3.5 linked_event_id chains (58 rows, all targets exist, same user, target dated <= linker)
| pattern (linker -> target) | count | linker desc / status | target desc / status | amounts |
|---|---|---|---|---|
| refund settled -> expense settled | 7 | Settled card charge reversal / settled (settle +1d) | Card charge later reversed / settled | equal |
| refund settled -> expense settled | 7 | Employer expense reimbursement / settled | Reimbursable work expense (work_expense) / settled ~30d earlier | equal |
| refund pending -> expense settled | 8 | Pending merchant refund / **pending** (settles 10d after event, 7d after request) | Purchase awaiting refund / settled ~21d earlier | equal |
| expense settled -> expense cancelled | 8 | Settled card purchase / settled | Card authorization / **cancelled** 2d earlier | equal |
| expense pending -> expense settled | 6 | Possible duplicate card charge / **pending** | Original card charge / settled ~11d earlier | equal |
| debt_payment scheduled -> debt_payment failed | 7 | Scheduled bill payment retry / **scheduled** (event_date == request_date, settles +4d) | Failed bill payment attempt / failed 2d earlier | equal |
| investment_sale settled -> investment_purchase settled | 5 | Investment sale proceeds / settled (credit) | Investment contribution / settled ~3 months earlier | sale ~1.83x purchase |
| investment_valuation unrealized -> investment_purchase settled | 10 | Current portfolio valuation / unrealized, non_cash, blank settlement | Investment contribution / settled ~3 months earlier | 0.4x .. 2x purchase |

Full list of linker event_ids: 99, 101, 1544, 1785, 1856, 1960, 2361, 2363, 3230, 4994, 5169, 6290, 6532, 6858, 7186, 7306, 8576, 9805, 10043, 10802, 11127, 11129, 12382, 12709, 12809, 13032, 13492, 13663, 13745, 13747, 14026, 14399, 15327, 16691, 17401, 17579, 17662, 18269, 19182, 19334, 19753, 20129, 20379, 20615, 21102, 21307, 21309, 21582, 21785, 22361, 23203, 23307, 23856, 24056, 24352, 24534, 25074, 25342. No target is linked by more than one row. 14 of the 29 investment purchases have no link at all (plain settled debits).

Interpretation for the engine: (a) the 6 "Possible duplicate card charge" pending rows are the duplicates the spec says to ignore (bank messages confirm the dispute is open); (b) the 7 scheduled retries replace the failed attempts and must be reserved (failed rows themselves must not be counted); (c) the 8 pending refunds are pending credits - do not count; (d) cancelled authorizations are superseded by the settled purchase - do not count the cancelled row; (e) unrealized valuations are never cash.

### 3.6 Failed (21) and cancelled (22) rows
- failed: all category `utilities`, all event_date 2 days before request_date, settlement == event_date. 7 are `debt_payment` "Failed bill payment attempt" (each has a scheduled retry linking to it: users 55, 91, 139, 181, 229, 253, 259). 14 are `expense` with descriptions "Failed utility debit" (5), "Failed subscription debit" (5), "Failed card payment" (4) and **no** retry row (users 5, 25, 45, 65, 85, 105, 125, 145, 165, 185, 205, 225, 245, 265). Whether an un-retried failed utility bill should be reserved is a judgement call (spec: ignore failed transactions).
- cancelled: all category `shopping`, all fixed, event_date 2-4 days before request, settlement +1/+2d. 8 "Card authorization" rows are followed by a settled "Settled card purchase" linking to them; 14 standalone "Cancelled card/booking/merchant authorization" rows have no follow-up.

### 3.7 event_date vs settlement_date
| status | rows | gap mean | min | max | rows with gap != 0 |
|---|---|---|---|---|---|
| settled | 25,148 | 0.005 | 0 | 8 | 62 (29 expense, 14 income, 5 investment_sale, 14 refund) |
| pending | 71 | 4.3 | 2 | 10 | 71 (all) |
| scheduled | 70 | 1.9 | 0 | 7 | 23 (all debits); the 47 scheduled salaries have gap 0 |
| cancelled | 22 | 1.4 | 1 | 2 | 22 |
| failed | 21 | 0 | 0 | 0 | 0 |
| unrealized | 10 | blank settlement | | | |
Gap value counts (non-zero): 1d 68, 4d 28, 2d 21, 3d 15, 5d 15, 7d 15, 8d 8, 10d 8. The 14 settled income rows with a gap are salaries that settled late (e.g. user_07 event_578 Payroll credit event 2024-08-15 settled 2024-08-23; several employer messages announce "confirmed salary is now expected on the 23rd, this replaces the earlier payroll date"). Use settlement_date for cash timing.

### 3.8 Events relative to request_date
- Events with event_date > request_date: **only 47**, all `scheduled` income "Next confirmed salary" (8-20 days after request, median 11; all settle same day). No settled row is dated after its user's request_date.
- Events dated exactly on request_date: 21 scheduled debits (7 debt retries, 5 "Scheduled school fee", 5 "Scheduled insurance payment", 4 "Scheduled utility debit") settling 4-7 days later.
- Non-settled rows dated on/before request_date: pending 71 (63 debits + 8 refunds), scheduled 23 debits, failed 21, cancelled 22, unrealized 10.
- Pending/scheduled summary (offsets in days relative to request_date):

| status | description | n | event offset | settle offset | blank amt |
|---|---|---|---|---|---|
| pending | Pending pharmacy card charge (healthcare) | 14 | -1 | +4 | 0 |
| pending | Pending merchant debit (shopping) | 14 | -1 | +3 | 0 |
| pending | Pending fuel authorization (transport) | 14 | -1 | +2 | 0 |
| pending | Pending online order charge (shopping) | 13 | -1 | +1 | 0 |
| pending | Possible duplicate card charge (shopping) | 6 | -1 | +3 | 0 |
| pending | Outstanding telecom bill (utilities) | 1 | -1 | +2 | 1 |
| pending | Large grocery tax invoice (groceries) | 1 | -1 | +6 | 1 |
| pending refund | Pending merchant refund | 8 | -3 | +7 | 0 |
| scheduled | Scheduled bill payment retry (debt/utilities) | 7 | 0 | +4 | 0 |
| scheduled | Scheduled school fee (education) | 5 | 0 | +7 | 0 |
| scheduled | Scheduled insurance payment | 5 | 0 | +7 | 0 |
| scheduled | Scheduled utility debit | 4 | 0 | +7 | 0 |
| scheduled | Outstanding rent balance | 1 | -1 | +4 | 1 |
| scheduled | Hospital bill payable | 1 | -1 | +3 | 1 |
| scheduled income | Next confirmed salary | 47 | +8..+20 | same | 0 |

89 users have at least one non-salary pending/scheduled row; only 4 users have more than one. **228 of 275 users have no explicit future salary row**, so future income must come from recurrence of settled salary history (sample request_03 has no scheduled salary yet `earliest_date_for_full_payment` = 2019-11-15, the projected payday).

### 3.9 Per-user counts and history window
- Events per user: min 56, 25% 75, median 98, 75% 104, max 129, mean 92.
- Earliest event per user is 175-179 days before request_date for **every** user (exactly ~6 months of history). Latest settled event is 1-7 days before request (median 2).
- Settled events in the 90 days before request: 27-65 per user (mean 47).
- Global date range 2019-03-09 .. 2026-09-03 (event_date). Requests 2019-09-03 .. 2026-09-04.

### 3.10 Recurrence patterns
Aggregated over settled rows per (user, description):
| group | descriptions | per month | same day-of-month? | amount |
|---|---|---|---|---|
| rent (232 users) | Apartment rent transfer, Monthly rent, Residential rent payment, Landlord standing order, Shared housing rent | exactly 1 | yes (1 DOM per user) | constant (1 distinct amount per user); 5-6 rows per user |
| subscriptions (496 user-series) | Cloud storage plan, Online backup subscription, Shared storage plan, Video streaming plan, Streaming subscription, Family streaming plan, Music service subscription, Music subscription, Audio streaming plan, Delivery service plan, Food delivery membership, Grocery delivery membership, Community fitness plan, Gym membership, Fitness club membership | exactly 1 | yes | constant |
| utilities | Water and power payment, Municipal utilities, Household utility payment, Energy provider bill, Electricity and water bill, Electricity bill | 1 | yes | varies ~ +/-16% (max-min)/mean |
| debt | Loan repayment, Personal loan payment, Vehicle loan payment, Education loan instalment, Credit card repayment | 1 | yes | constant |
| insurance / education / housing / family_support | Health/Vehicle/Household insurance premium, Insurance policy payment, School fee payment, Professional training fee, Child education fee, Course tuition, Home association fee, Building maintenance payment, Home repair reserve, Property maintenance contribution, Childcare contribution, Dependent care payment, Family support payment, Parent support transfer | 1 | yes | constant |
| healthcare (recurring) | Diagnostic test, Therapy appointment, Family healthcare expense, Clinic payment, Regular medicine purchase | 1 | yes | varies ~15% |
| shopping / entertainment (monthly) | Monthly shopping spend, Household shopping, Clothing and household items, Online retail purchases, Personal shopping, Games and recreation, Monthly entertainment spend, Local event tickets, Cinema and events, Weekend entertainment | 1 | yes | varies ~16% |
| groceries (all users) | 8 descriptions (Local market purchase, Grocery delivery, Supermarket basket, Household groceries, Bulk pantry shop, Neighbourhood grocer, Fresh food shop, Weekly produce market) | ~1.2 per description-month, ~2.9 rows each over 6 months | no (2-3 DOMs) | varies ~22% |
| transport (all users) | 8 descriptions (Local taxi, Vehicle charging, Rail pass, Fuel refill, Commuter pass, Metro and bus fares, Ride-hailing trip, Parking and tolls) | same as groceries | no | varies ~21% |
| dining (reducible) | 8 descriptions (Takeaway order, Neighbourhood restaurant, Weekend food delivery, Family dinner, Quick-service meal, Bakery and snacks, Coffee shop, Lunch with colleagues) | ~2.1 rows each over 6 months | no | varies ~15% |
| salary | see below | 1 (or 2 / 4) | yes | constant for 171 users |
Groceries, transport and dining should be modelled as category-level monthly totals (sum of all 8 descriptions per month), not as per-description recurrences. Rent/subscription/debt/insurance/education/utilities are per-description monthly recurrences with a stable day-of-month.

Salary detail (1,690 rows): 34 descriptions. `Payroll credit` 806 rows / 162 users. Day-of-month: 15th 1,162 rows; other DOMs are freelancers (8 & 22, or 7 & 20: `Website/Content/Design/Consulting/Freelance/Application/Client retainer/Independent work` payments, 2 per month, amounts vary 15-20%), gig workers weekly (4/11/18/25 or 5/12/19/26: `Delivery/Driver/Task marketplace payout`, `Weekly app earnings`, amounts vary ~50%), base + commission (15th `Base salary` + 24th `Performance commission` / `Account commission payment` / `Monthly sales commission`), and second household incomes on the 20th/21st/26th. 202 users have a single salary DOM, 61 have 2, 11 have 4, 1 has 3. Distinct settled salary amounts per user: 1 (171 users), 2 (45), 3-6 (29), 10-21 (30 freelancers/gig). Salary rows per user: median 5, max 21.

Special salary descriptions (each 1-2 rows per user, signalling a regime change): `Prorated first salary` (7 users), `First-job payroll` (16, only 2 rows of history), `New employer payroll` (11, follows 4 `Previous employer payroll` rows at the same amount), `Final employer payroll` (7: employment ended), `Payroll before leave` / `Payroll after returning from leave` (9: months missing in between), `Seasonal contract payment` / `Temporary assignment pay` / `Peak-season wages` (contract ended), `Promotion arrears payment` (12, one-off), `Quarterly performance bonus` (10, one-off), `August 2019 net salary` (1, blank amount). Scheduled `Next confirmed salary` equals the last settled salary for 41 users; differs for 6 (user_01 12826 prorated -> 23320; users 99, 100, 190, 192, 217 where the last settled row was a smaller one-off).

Concrete examples:
- **user_01** (ZAR, request 2024-03-03, balance 58,481.10, min 18,000, methods full_payment only): salary = `Prorated first salary` 12,826 settled 2024-02-15 then `Next confirmed salary` 23,320 scheduled 2024-03-15 (only 2 salary rows). Recurring: `Apartment rent transfer` 5,148 on the 2nd (6 rows Oct-Mar), `Household utility payment` ~1,386-1,652 on the 6th, `Professional training fee` 1,821.60 on the 8th, `Education loan instalment` 3,487 on the 11th, `Music service subscription` 235.40 on the 11th (fixed), `Delivery service plan` 306.90 on the 13th (stoppable), groceries 8 descriptions ~3-5 per month, dining reducible with minimum_allowed 489.5. Also a card charge reversed (event_98/99), a cancelled authorization superseded by a settled purchase (event_100/101), and `Pending fuel authorization` 567.60 (pending, settles 2024-03-05). Sample answer: affordable_now, full 25,256.
- **user_02** (IDR, request 2025-08-05, balance 60,383,889.20, min 29,158,400, methods partial|installments, max 7 months): `Payroll credit` 33,345,000 on the 15th (Mar-Jul, no scheduled row). Fixed monthly: `Home repair reserve` 3,534,000 on the 4th (already settled 2025-08-04), `Municipal utilities` ~2.0M on the 7th, `Household insurance` 1,132,400 on the 8th, `Course tuition` 3,040,000 on the 9th, `Clinic payment` ~1.5M on the 11th, `Shared storage plan` 369,550 on the 13th (stoppable), `Cinema and events` ~1.3M on the 15th (reducible, min 670,700); groceries/transport/dining variable. `Pending merchant debit` 1,651,100 settles 2025-08-08. Sample answer: safe 17,229,139.20; installments 3 x 15,952,906.67 from 2025-08-08; earliest full 2025-09-15 (payday).
- **user_26** (IDR, request 2025-08-03, balance 100,845,250, min 24,768,300, methods full|installments, max 5): freelancer with 10 salary rows on the 8th and 22nd (Website/Content/Design/Independent/Freelance/Application/Client retainer payments 8.8M-17.7M, no scheduled row). `Residential rent payment` 10,374,000 on the 3rd (Mar-Jul; Aug not yet), `Water and power payment` ~1.8-2.1M on the 7th, `Video streaming plan` 560,500 on the 10th (reducible_or_stoppable, min 280,250), `Cloud storage plan` 214,700 on the 13th (fixed for this user), `Clothing and household items` ~1.3M on the 13th; plus a settled reversal pair (2360/2361), a cancelled authorization + settled purchase (2362/2363) and a standalone cancelled booking authorization (2364). Eval request_26: family_transfer 15,656,000 by 2025-10-07, allows_partial false; options: full, 15 x 1,148,106.67 from 08-06, 6 x 2,818,080 from 08-10, 24 x 795,846.67 from 08-17.

### 3.11 Duplicates
No two rows share (user_id, amount, event_date, description). The only "duplicate" concept in the data is the 6 pending `Possible duplicate card charge` rows linked to an `Original card charge` (section 3.5).

---

## 4. exchange_rates.csv
| from -> to | rows | rate (constant) | first date | last date |
|---|---|---|---|---|
| USD -> INR | 33 | 83.33 | 2024-01-15 | 2026-11-15 |
| USD -> IDR | 30 | 15833.33 | 2023-10-15 | 2026-06-15 |
| USD -> EUR | 25 | 0.92 | 2023-10-15 | 2026-03-15 |
| EUR -> USD | 24 | 1.09 | 2024-04-15 | 2026-09-15 |
| EUR -> ZAR | 22 | 20 | 2023-10-15 | 2026-01-15 |
Dates: every 15th of the month from 2023-10-15 to 2026-11-15 (not every pair on every date; see coverage above) plus a single 2025-10-01 USD->INR row for the taxi image event. Rates never change within a pair, so a lookup keyed on (date, from, to) with fallback to the pair's constant rate is safe. There are no INR/IDR/ZAR -> anything rows and no USD->ZAR or EUR->INR/IDR rows; none are needed by the events.

---

## 5. requests.csv and sample_requests.csv
- 250 eval requests (request_26..275) for users user_26..user_275; 25 samples (request_01..25) for user_01..25. Zero user overlap. Every user has exactly one request; every request's user exists in profiles and events (no orphans in any direction).
- request_date range 2019-09-03 .. 2026-09-04 (2019: 1, 2023: 2, 2024: 89, 2025: 90, 2026: 93). request_date is never the same as any settled event date; it is 1-7 days after the last settled event.
- desired_completion_date - request_date: min 6, 25% 35.5, median 64, 75% 72, max 86 days. Peak at 69-73 days. Always inside the 90-day forecast window.
- requested_amount by currency (eval): EUR 271.70-3,537.60 (median 1,423); IDR 2.19M-83.9M (median 21.6M); INR 22,200-553,000 (median 115,500); USD 199.89-5,059.20 (median 1,699); ZAR 2,560-124,278 (median 29,062).
- requested_amount / (balance - minimum): <=0.5 for 62 requests, 0.5-1.0 for 90, 1-1.5 for 36, 1.5-2 for 26, 2-3 for 23, 3-5 for 18, >5 for 20. So ~45% of requests exceed today's raw headroom before any reserves.
- allows_partial_payment x user considers partial (all 275): false/no 89, false/yes 94, true/no 47, true/yes 45. Only **40 eval requests** can ever receive `partial_payment`. 38 eval users consider only installments; 16 consider only partial_payment (they can never get full_payment or wait).
- request_text always embeds the amount with currency and usually the deadline; no text mentions bonuses/refunds/cancellations. 55 contain "wait", 5 "installment". Text is not needed for computation.
- Sample outcome mix: affordable_now 3 (full_payment), affordable_with_plan 9 (installments 5, full_payment with spending changes 3, partial_payment 1), affordable_later 7 (wait), not_affordable 6 (not_recommended). Sample facts worth encoding: `wait` plans put the full amount on `earliest_date_for_full_payment`, which is a payday (15th) or the desired date; `earliest_date_for_full_payment` can equal request_date while the recommendation is installments (request_12, user does not accept full_payment); it can also be later than desired_completion_date while the request is still solved with spending changes today (request_06, request_11, request_21); `amount_safe_to_pay` is reported with up to 2 dp (17229139.2, 87170.56, 243849.58); not_affordable rows leave `earliest_date_for_full_payment` empty and use two explanation templates ("None of the available options keeps the X minimum protected" vs "Although X is available today, the full amount cannot be completed safely within 90 days").

---

## 6. request_payment_options.csv
- Options per request: 2 (65 requests), 3 (180), 4 (30). Every request has exactly one `full_payment` option and 1-3 `installments` options. Within a request, payment_option_id is increasing; the full_payment option is the first option in 205 requests but **not** in 70 (do not assume position).
- full_payment rows (275): payment_amount == requested_amount (all 275, exact), number_of_payments 1, first_payment_date == request_date (all 275), payment_frequency_days blank, financing_fee 0, total == amount.
- installments rows (515): `payment_amount * number_of_payments == total_payable_amount` holds to 1e-8 for all 515; `total_payable_amount == requested_amount + financing_fee` for all 515. Fee as % of requested: n=2 -> 4%; n=3 -> 4% (6% for 6 rows); n=4 -> 6%; n=6 -> 8%; n=15 -> 10% (3.5% variants); n=18 -> 14%; n=21 -> 18%; n=24 -> 22% (3.5%/5% variants). Fee is monotone in n within a request, so "minimize total paid" always prefers fewer payments among installments and full_payment beats all installments.
- first_payment_date - request_date for installments: 0d (106), 1d (2), 3d (156), 5d (2), 6d (1), 7d (104), 14d (144). Only 20.6% start on request_date.
- frequency x n: n=2 {28:6, 31:1}; n=3 {28:29, 30:18, 31:33}; n=4 {30:3}; n=6 {28:25, 30:21, 31:19}; n=15 {30:89}; n=18 {31:87}; n=21 {28:88}; n=24 {28:32, 30:35, 31:29}. Plan dates = first_payment_date + k * frequency (verified against all 5 sample installment plans, e.g. 2026-04-19 +31 -> 05-20 -> 06-20).
- Last installment <= desired_completion_date for only **81 of 515** options: all 7 n=2 and 74 of 80 n=3; never for n >= 4 (6-payment plans span >= 140 days). 6 more n=3 plans finish within 90 days but after the desired date.
- Compared with the user's max_installment_months (only meaningful for the 156 users who consider installments): n <= max for 94 options, n > max for 193 (long 15/18/21/24-payment options are almost always over the cap). Combining user-considers-installments AND n <= max AND ends by desired date leaves **80 eligible options in 80 distinct requests** (73 with n=3, 7 with n=2); the other 76 installment-considering requests have none. If months are computed as n * frequency / 30 instead of n, 4 of those 80 (n=3, frequency 31, max 3: request_139 option_395, request_145 option_412, request_241 option_695, request_256 option_737) would fall just over the cap (3.1 > 3). Sample request_17 (max 3, chose 3 x 30d) does not disambiguate; treating the cap as number_of_payments <= max is the simpler reading.
- Installment plan amounts in the sample `payment_plan` are copied verbatim from `payment_amount` (e.g. `15952906.67`, `22590.19`).

---

## 7. financial_profiles.csv
- Currency counts: INR 67, EUR 62, IDR 55, ZAR 51, USD 40.
- current_available_balance > minimum_balance_to_keep for all 275 users. minimum / balance ratio: min 0.17, median 0.48, max 0.77. Headroom (balance - min) medians: EUR 1,294; IDR 22.8M; INR 105,830; USD 1,388; ZAR 31,583.
- Payment-method membership: full_payment 163 users, installments 156, partial_payment 139 (combos in section 2). max_installment_months present iff installments considered.
- Flexible events line up exactly with the profile: every `reducible` event is in a category the user listed under reduce; every `stoppable` event is in the user's stop list; every `reducible_or_stoppable` event is in both lists (the 45 users with streaming/gym in both); every event in a protected category is `fixed`. Only 28 fixed events sit in a user's reduce/stop categories (cannot be changed). Flexibility never varies within a (user, description) series. 265 users have at least one flexible series (median 6 descriptions, max 12); 10 users have none.

---

## 8. messages.csv and images.csv
- 215 messages, one per user, for 198 eval users and 17 sample users (60 users have none). request_id populated on 128 (116 eval requests), related_event_id on 39, both on 28, neither on 76. When request_id is present it always belongs to the same user. sent_at is 0-11 days before request_date (never after).
- Language: 45 Indonesian messages = exactly the messages of IDR users; 170 English. Same templates in both languages.
- source_type x (has_event, has_request): bank (0,8,3,7 for none/req-only/event-only/both), employer (55, 68, 2, 1), financial_service (4, 2, 5, 12), merchant (3, 6, 1, 7), service_provider (14, 16, 0, 1).
- Message families (counts approximate, EN + ID):
  - employer / payroll (126): first salary confirmed with amount + date (new job, history has 0-2 salary rows); salary increased to X from a date; next salary reduced to X due to unpaid leave; temporary reduced monthly pay continues next payroll; regular salary X resumes on date and a new recurring childcare payment starts the same month; salary date moved to the 23rd (replaces the 15th); employment ended, no further salary; seasonal contract ended, no income confirmed; quarterly bonus not yet approved (exclude); confirmed base salary, commission still pending (exclude commission); one household income ended, remaining monthly salary X; regular salary X plus one-time arrears adjustment Y in the same payroll; foreign-currency salary converts at settlement-date rate; latest employer credit is an expense reimbursement, not salary (3, linked to work_expense refunds).
  - service_provider (31): client approved an invoice of X settling on a date, other invoices unconfirmed (freelancers, ~15); gig payout still pending / not withdrawable (~8); renewed lease raises monthly rent by 12% from the next payment (3).
  - financial_service (23): prize claim verified but not credited (do not count); prize proceeds already received, no further payment (6, linked to the settled `Prize proceeds` windfalls); portfolio value up/down, no cash (10, linked to unrealized valuations); investment sale proceeds settled (5); scam "you have been selected for a cash prize, pay the release charge today" (2: message_67, message_142 - ignore); message_86 (user_113) combines the EV-charging receipt with "employer has confirmed a USD 1296 salary credit for 15 September 2026".
  - bank (18): previous debit failed, another attempt will be made (7, linked to the failed debt rows); extra card charge under investigation, no reversal yet (6, linked to the pending duplicate charges); matching debit and credit are a transfer between the user's own accounts (2); minimum payments due on two separate card accounts, one payment does not cover the other (2).
  - merchant (17): refund initiated, not yet received (8, linked to pending refunds); foreign-currency refund still processing, home-currency amount unknown (4); bill charged in foreign currency, final amount at settlement (2, incl. the USD taxi user); receipt confirms the tote bag amount (1).
- No message contains "ignore", "override", "system prompt", "assistant" or "recommend"; the only instruction-like content is the two prize-scam messages.
- Windfall rows: 6 settled `Prize proceeds` (users 24, 38, 101, 115, 129, 143), 5-9 days before request, each with a message saying no more is coming.

### images.csv joined with financial_events (full event rows)
| image | user | request | event | type | description | category | dir | amount | cur (home) | event_date | settlement | status | flex | request_date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| image_01 | user_03 | request_03 | event_253 | income | August 2019 net salary | salary | credit | blank | IDR (IDR) | 2019-08-31 | 2019-08-31 | settled | fixed | 2019-09-03 |
| image_02 | user_16 | request_16 | event_1442 | expense | Outstanding rent balance | rent | debit | blank | INR | 2023-08-11 | 2023-08-16 | scheduled | fixed | 2023-08-12 |
| image_03 | user_17 | request_17 | event_1545 | expense | Bulk groceries and pantry purchase | groceries | debit | blank | INR | 2026-02-27 | 2026-02-27 | settled | fixed | 2026-03-01 |
| image_04 | user_19 | request_19 | event_1700 | expense | Delivered grocery order | groceries | debit | blank | INR | 2024-09-03 | 2024-09-03 | settled | fixed | 2024-09-04 |
| image_05 | user_20 | request_20 | event_1786 | expense | Outstanding telecom bill | utilities | debit | blank | INR | 2026-02-06 | 2026-02-09 | pending | fixed | 2026-02-07 |
| image_06 | user_33 | request_33 | event_3051 | expense | Grocery tax invoice | groceries | debit | blank | INR | 2026-01-06 | 2026-01-06 | settled | fixed | 2026-01-07 |
| image_07 | user_35 | request_35 | event_3231 | expense | Restaurant tax invoice | dining | debit | blank | INR | 2025-10-29 | 2025-10-29 | settled | fixed | 2025-10-30 |
| image_08 | user_48 | request_48 | event_4535 | expense | Property maintenance invoice | housing | debit | blank | INR | 2026-07-24 | 2026-07-24 | settled | fixed | 2026-07-25 |
| image_09 | user_55 | request_55 | event_5170 | expense | Water bill due | utilities | debit | blank | INR | 2026-06-07 | 2026-06-07 | settled | fixed | 2026-06-08 |
| image_10 | user_64 | request_64 | event_6033 | expense | Large grocery tax invoice | groceries | debit | blank | INR | 2024-06-03 | 2024-06-10 | pending | fixed | 2024-06-04 |
| image_11 | user_73 | request_73 | event_6859 | expense | Hospital bill payable | healthcare | debit | blank | INR | 2023-01-19 | 2023-01-23 | scheduled | fixed | 2023-01-20 |
| image_12 | user_78 | request_78 | event_7307 | expense | Taxi fare | transport | debit | blank | USD (INR) | 2025-10-01 | 2025-10-01 | settled | fixed | 2025-10-02 |
| image_13 | user_84 | request_84 | event_7941 | expense | Tote bag order | shopping | debit | blank | INR | 2026-04-03 | 2026-04-03 | settled | fixed | 2026-04-04 |
| image_14 | user_101 | request_101 | event_9421 | expense | Pharmacy purchase | healthcare | debit | blank | INR | 2025-11-02 | 2025-11-02 | settled | fixed | 2025-11-03 |
| image_15 | user_105 | request_105 | event_9806 | expense | Airline ticket purchase | transport | debit | blank | INR | 2026-06-07 | 2026-06-07 | settled | fixed | 2026-06-08 |
| image_16 | user_113 | request_113 | event_10521 | expense | EV charging wallet payment | transport | debit | blank | INR | 2026-09-03 | 2026-09-03 | settled | fixed | 2026-09-04 |
No image event has a linked_event_id or minimum_allowed_amount. Image user == event user for all 16. Only 3 of the 16 images matter for the cash forecast (event_1442, event_1786, event_6033, event_6859 are the non-settled ones: 4 rows, of which the settled ones are already in the balance); the settled 12 only matter for explanations and for not mis-detecting recurrence.

---

## 9. Gotchas (read before designing the engine)

1. **No future salary row for 228 of 275 users.** Only 47 users have a scheduled `Next confirmed salary`. Future income must be projected from settled salary recurrence (same day-of-month, last constant amount), and the projected settlement date is where `earliest_date_for_full_payment` and `wait` plans land in the samples. Messages then amend this projection (reduced/increased/first/ended/moved-to-23rd salaries).
2. **Salary regime changes are encoded in descriptions and messages, not statuses**: `Final employer payroll`, `Seasonal contract payment`, `Payroll before leave` (gap months), `Previous employer payroll` -> `New employer payroll`, `Prorated first salary` (scheduled amount is larger), `First-job payroll` (only 2 rows). Naive "average of last N salaries" will be wrong for these ~80 users. One-offs (`Promotion arrears payment`, `Quarterly performance bonus`, `Prize proceeds`, `Employer expense reimbursement`, `Investment sale proceeds`) must not be projected.
3. **Freelancers / gig workers** (about 60 users) have 2 or 4 income events per month with 15-50% amount variation; service_provider messages say only the confirmed invoice counts and gig payouts are not withdrawable until closed. Conservative projection is needed.
4. **All 140 foreign-currency rows are salary except one blank-amount USD taxi (event_7307)**; conversion is always available on the settlement date, rates are constant per pair, and the only non-15th rate row (2025-10-01 USD->INR) exists solely for that taxi image. Balances/requests/options are already in home currency.
5. **Blank amounts (16) are exactly the image events.** Two are pending and two are scheduled debits that must be reserved; one image (image_05) shows two amounts (704.05 due by 06-Feb vs 822.05 after) while the event settles 2026-02-09.
6. **status semantics**: `pending` rows are dated 1-3 days before the request and settle 1-10 days after it (reserve debits, ignore the 8 pending refunds); `scheduled` debits are dated on the request_date itself (reserve); `failed` rows are all utilities and 7 have a scheduled retry (reserve the retry, not the failure); `cancelled` authorizations are all shopping and 8 are superseded by a settled purchase; `unrealized` rows have blank settlement_date and direction non_cash.
7. **6 "Possible duplicate card charge" pending rows are the duplicates to ignore** (bank messages confirm). No other exact duplicates exist.
8. **Events dated after request_date are only the 47 scheduled salaries.** Every other row is on/before request_date, so "history" = everything up to request_date; the balance in the profile already reflects settled rows.
9. **History is exactly ~6 months for everyone** (175-179 days), so monthly recurrences have 5-6 observations; the current month's rent/subscription may already be settled (e.g. user_02 home repair reserve on the 4th settled the day before the request) - do not double count within the forecast.
10. **Groceries/transport/dining are 8 rotating descriptions each** with 2-3 different days of month; recurrence must be detected at category level (monthly total), not per description. Dining is the main reducible category (1,925 rows) and its `minimum_allowed_amount` is constant per series.
11. **Spending changes**: sample `reduce_to` uses exactly `minimum_allowed_amount` and both `stop`/`reduce_to` reference the latest event_id of the series. Only reducible (2,682), stoppable (1,297) and reducible_or_stoppable (225) rows are eligible and they always match the profile lists; `stoppable` rows have no minimum_allowed_amount (stop only); `reducible_or_stoppable` may do either (stop and reduce of the same event are mutually exclusive).
12. **Installment eligibility is narrow**: only n=2/3 plans can finish by desired_completion_date (81 of 515 options); after applying `max_installment_months` and the user's methods, 80 requests have exactly one eligible installment option and 76 installment-considering requests have none. Long 15/18/21/24-payment options are never viable. Four n=3 x 31-day options sit at 3.1 "months" vs a cap of 3 - decide whether the cap is on payments or on months.
13. **full_payment option is not always option #1** (70 requests). Installment first_payment_date is 0-14 days after the request; plan dates are first + k*frequency. Copy payment_amount strings verbatim into the plan.
14. **Partial payment is rarely possible**: only 40 eval requests have allows_partial=true AND a user who considers partial_payment. 16 eval users accept only partial_payment (never full/wait) and 38 accept only installments; `wait` requires the user to accept full_payment.
15. **Messages**: one per user, UTF-8 with curly apostrophes, 45 in Indonesian (all IDR users), sent 0-11 days before the request. The 76 messages with no request_id and no event_id are still relevant (mostly payroll changes). Two messages are prize scams instructing the user to pay a release fee - treat as noise. "Rent increases by 12% from the next payment" (3 users) and "new recurring childcare payment begins" (about 7 users, amount not stated) change the forecast. Two bank messages (message_23 user_33, message_135 user_171) describe an internal transfer between the user's own accounts, but those users have no non-salary credit rows at all, so there is no event pair to neutralise - the messages are distractors. Likewise the two "minimum payments due on two separate card accounts" messages (users 172, 202) map only to their ordinary monthly `Loan repayment` rows.
16. **Late salary settlements**: 14 settled salary rows settled 4-8 days after event_date, matching employer messages that move payday to the 23rd; use settlement_date for cash timing and honour the message for the next payday.
17. **Formatting**: `allows_partial_payment` is the lower-case string `true`/`false`; requested amounts have 0-2 decimals and sample `amount_safe_to_pay` has up to 2 decimals; sample plan amounts keep trailing `.40`/`.60` when the requested amount has them (`2026-01-03:620.40`, `2025-04-15:996.60`) but plain `25256` when integer - i.e. they echo the request/option string formatting.
18. Every user, request and option is internally consistent (no missing joins, no negative amounts, no whitespace/case issues, no balance below minimum), so the engine can assume clean joins and focus on the semantics above.
