# Image evidence extraction (dataset/images.csv, 16 images)

All 16 related event rows in `dataset/financial_events.csv` have a BLANK `amount`; the image is the only source.
Home currency for every user is INR except user_03 (IDR). Only image_12 is in a foreign currency (USD) relative to the user's home currency (INR); event_7307 itself is recorded in USD, so the USD->INR rate for 2025-10-01 (83.33) applies.
No image contains any instruction addressed to the reader or an AI; only ordinary marketing / legal boilerplate (flagged per image, never followed).

## Summary table

| image_id | request_id | event_id | event description (csv) | csv amount | image amount | currency | image date | doc type | verdict |
|---|---|---|---|---|---|---|---|---|---|
| image_01 | request_03 | event_253 | August 2019 net salary (income, settled 2019-08-31) | blank | 4365000 (Net Pay) | IDR | Aug-2019 pay slip, printed 2019-09-02 | Payslip (HR dept, "Bank in Transit") | confirms |
| image_02 | request_16 | event_1442 | Outstanding rent balance (scheduled 2023-08-11 -> 2023-08-16) | blank | 100000 (Balance Due; total 200000, received 100000) | INR | 2023-08-11 | Rent receipt (owner Vimlesh, receipt 9453) | confirms (outstanding balance = 100000) |
| image_03 | request_17 | event_1545 | Bulk groceries and pantry purchase (settled 2026-02-27) | blank | 41272 (Net Amount / Cash Paid) | INR | 2026-02-27 16:10 | Bill of Supply, Riddhi Siddhi Nuts and Spices, bill 1125000158 | confirms |
| image_04 | request_19 | event_1700 | Delivered grocery order (settled 2024-09-03) | blank | 2854 (Item Bill; final total cut off) | INR | none visible | Delivery-app order screenshot (13 items, Delivered) | confirms (partial view) |
| image_05 | request_20 | event_1786 | Outstanding telecom bill (pending 2026-02-06 -> 2026-02-09) | blank | 704.05 (due till 06-Feb-2026); 822.05 if paid after 06-Feb-2026 | INR | due 2026-02-06 | Airtel bill account summary | confirms; late-fee ambiguity flagged |
| image_06 | request_33 | event_3051 | Grocery tax invoice (settled 2026-01-06) | blank | 1995 (Total) | INR | none visible | Tax invoice, Blink Commerce Pvt Ltd (Blinkit) | confirms |
| image_07 | request_35 | event_3231 | Restaurant tax invoice (settled 2025-10-29) | blank | 8528 (Grand Total, rounded from 8528.10) | INR | 2025-10-29 12:12 | Tax invoice, Nagarjuna 1984 KMR, bill 10, stamped PAID | confirms |
| image_08 | request_48 | event_4535 | Property maintenance invoice (settled 2026-07-24) | blank | 15339 (Total Amount Received) | INR | charge 2026-07-24, due 2026-08-30 | Payment receipt (paytm gateway, inv 6455) | confirms (paid 24 Jul, ahead of 30 Aug due date) |
| image_09 | request_55 | event_5170 | Water bill due (settled 2026-06-07) | blank | 723 (Total Amount Received) | INR | charge 2026-06-07, due 2026-07-02 | Payment receipt (paytm gateway, inv 6320) | confirms (paid 7 Jun) |
| image_10 | request_64 | event_6033 | Large grocery tax invoice (pending 2024-06-03 -> 2024-06-10) | blank | 79679.26 (Total = Balance Due) | INR | none visible | Tax invoice (22 line items, GST) | confirms (still due) |
| image_11 | request_73 | event_6859 | Hospital bill payable (scheduled 2023-01-19 -> 2023-01-23) | blank | 3650 (Total Bill / Balance; Amount Paid 0.00) | INR | 2023-01-19 | Provisional hospital bill, Jeevan Hospital, admission 000001 | confirms (unpaid) |
| image_12 | request_78 | event_7307 | Taxi fare (settled 2025-10-01, currency USD) | blank | 33.50 (Total; cash paid 40.00, change 6.50) | USD (foreign vs INR home; rate 2025-10-01 USD->INR 83.33 => 2791.56 INR) | 2025-10-01 21:45 | Taxi receipt, CityCab Service, trip CC-8923 | confirms |
| image_13 | request_84 | event_7941 | Tote bag order (settled 2026-04-03) | blank | 2298 (Total paid) | INR | none visible | Online order summary screenshot | confirms |
| image_14 | request_101 | event_9421 | Pharmacy purchase (settled 2025-11-02) | blank | 4543 (TOTAL) | INR | none visible | Handwritten pharmacy cash bill | confirms |
| image_15 | request_105 | event_9806 | Airline ticket purchase (settled 2026-06-07) | blank | 9968 (Grand Total incl taxes) | INR | 2026-06-07 | Airline GST invoice, InterGlobe Aviation (IndiGo), PNR UC83TT | confirms |
| image_16 | request_113 | event_10521 | EV charging wallet payment (settled 2026-09-03) | blank | 393.22 (Total) | INR | 2026-09-03 00:35 | EV charging invoice, charge point 1110 Krishnagiri, wallet | confirms |

## Per-image details

### image_01 -> event_253 (user_03, home IDR, request_03)
- Doc: "PAY SLIP Aug-2019", Human Resource Department. Employee M NURHUDA SY, Emp No 19050378, Relationship Manager, Cost Center "Bank in Transit - Surabaya Basuki Rahmat", Tax Ref 899763619907000, Tax status TK/0.
- Earnings (IDR): Salary 4,500,000; Allowance BPJS Pen 2% 90,000; Allowance JHT 3.7% 166,500; JKK 0.24% 10,800; JKM 0.3% 13,500; Subtotal/Total Earnings 4,780,800; tax allowance lines 0.
- Deductions (IDR): BPJS Pen 2% Company 90,000; BPJS Pen 1% Employee 45,000; JHT 3.7% 166,500; JHT 2% Employee 90,000; JKK 10,800; JKM 13,500; Subtotal/Total Deductions 415,800; Tax 0; Tax Penalty 0.
- Net Pay IDR 4,365,000 ("Four Million Three Hundred Sixty Five Thousand Rupiahs"). "Transferred to: Bank Central Asia - 2582373290 - M NURHUDA SY : IDR 4,365,000". Printed 2 Sep 2019 09:35 PM.
- Instructions to reader/AI: none.
- Related message_02 (employer, 2019-08-31, no related_event_id, Indonesian): regular salary confirmed for the next payroll; next payslip will show regular pay and a one-time adjustment separately. That concerns the September payroll, not this event.
- VERDICT: use 4365000 IDR as the settled August 2019 net salary credit on 2019-08-31. Image confirms the event. Home currency IDR, no conversion.

### image_02 -> event_1442 (user_16, INR, request_16)
- Doc: "Rent Receipt", Owner Vimlesh, Receipt No 9453, Date 11/08/23, tenant Yashwant, property in HSR Layout Bengaluru; body text says rent for "April 2022 to September 2022" (template text, inconsistent with the 2023 date; ignore).
- Amounts (INR): Rent & Maintenance 1,80,000.00; Water 5,000.00; Rental Tax 5,000.00; Electrical 10,000.00; Total Amount to be Received 2,00,000.00; Amount Received 1,00,000.00; Balance Due 1,00,000.00. Received by Sanjay.
- Boilerplate notes about PAN / revenue stamp: not instructions to follow.
- Related message_12 (StayLedger, 2023-08-01, no event id): renewed lease raises monthly rent 12% for the next rent payment. That is about the recurring "Monthly rent" series (57,100 -> ~63,952 from September 2023), not this one-off balance.
- VERDICT: the event "Outstanding rent balance" = the Balance Due of 100000 INR, scheduled debit settling 2023-08-16. Image confirms (100000 already paid, 100000 still due). Do not use 200000.

### image_03 -> event_1545 (user_17, INR, request_17)
- Doc: Bill of Supply, Riddhi Siddhi (Nuts and Spices), Koramangala Bangalore, GSTIN 29ALCPJ4001H1ZI, Bill No 1125000158, 27/02/2026 16:10 PM. 11 items / qty 76 (Coke Diet 5800, pulpy orange 750, the whole truth 13920, Rite Bite 4800, Ocean Fruit 2500, ferrero 2152, munch 750, 5 star 540, dark fantasy 1690, Butter 7290, dairy milk 1080).
- Net Amount 41272.0; Cash Paid 41272.00. An "INWARD" received stamp overlays the header.
- VERDICT: 41272 INR settled 2026-02-27. Confirms.

### image_04 -> event_1700 (user_19, INR, request_19)
- Doc: delivery-app order screenshot, "ITEM DETAILS", 13 items, Jeevan Bhima Nagar, status "Delivered". Line items sum to 2854 (95+531+0+186+122+464+184+144+75+366+190+121+376).
- "TOTAL ORDER BILL DETAILS": Item Bill Rs 2854.00. The next line (delivery fee) and the final total are cut off; a partially visible struck-through "16.00" suggests a waived delivery fee but is not legible enough to rely on.
- No date, no order number visible. No instructions.
- VERDICT: use 2854 INR (the only fully legible total) for the settled 2024-09-03 grocery debit. Confirms; the true charged total may be marginally higher but is not visible, so do not invent it.

### image_05 -> event_1786 (user_20, INR, request_20)
- Doc: Airtel (business) bill "YOUR ACCOUNT SUMMARY" / "THIS MONTH'S CHARGES". Previous balance 3,543.54; Payments -3,543.54; This month's charges +704.05 (Rentals 580.65, Usage 16.00, Taxes 107.40); Total Rs 704.05 ("Seven Hundred Four Rupees and Five Paise Only").
- "Amount due till 06-Feb-2026 = 704.05"; "Amount due after 06-Feb-2026 = 822.05" (late fee 118.00).
- Marketing banner "Now view, download and pay your bills anytime..." is advertising, not an instruction.
- Related message_14 is about a different event (event_1785 pending refund 8640 INR, not yet credited); unrelated to this bill.
- VERDICT: bill total 704.05 INR, due 2026-02-06 (= event_date). CSV says pending with settlement 2026-02-09, which is AFTER the due date, so under the "financially safer interpretation" rule the reserved debit could be 822.05. Primary value 704.05; alternative 822.05 recorded in the JSON as alt_amount. request_20 is a sample request (expected amount_safe_to_pay 5400) which can be used to test which value the organizers used.

### image_06 -> event_3051 (user_33, INR, request_33)
- Doc: Tax invoice from Blink Commerce Private Limited (formerly Grofers), GSTIN 29AAFCG9846E1Z7, CIN U74140HR2015FTC055568, FSSAI 10018064001545. 5 chocolate-bar lines (565, 552, 289, 289, 289) plus delivery/other charges (3.13, 3.06, 1.60, 1.60, 1.60). Qty 7. CGST 47.49 + SGST 47.49.
- Total 1995.00 ("One Thousand And Nine Hundred And Ninety-Five Rupees and Zero Paisa Only"). Reverse charge: No. No invoice date/number in the visible crop.
- Related message_23 (Cedar Bank) is about an internal transfer between the user's own accounts; unrelated.
- VERDICT: 1995 INR settled 2026-01-06. Confirms.

### image_07 -> event_3231 (user_35, INR, request_35)
- Doc: TAX INVOICE, Nagarjuna 1984 KMR, Koramangala Bangalore, GSTIN 29AACFA1961A1ZY, Bill No 10, Date 29-10-2025 12:12 PM, Token 1, Table P1, stamped "PAID".
- Items: Carrier Meals 2900, Parcel 450, Chicken Nagarjuna 2490, Chapathi 1800, Dal 310, containers/packing 30+96+46. SubTotal 8122.00, SGST 2.5% 203.05, CGST 2.5% 203.05, Total 8528.10, Grand Total (RS) 8528.
- VERDICT: 8528 INR settled 2025-10-29 (rounded grand total). Confirms; paid.

### image_08 -> event_4535 (user_48, INR, request_48)
- Doc: "Receipt" for maintenance bill, Invoice No 6455, Charge Date 24-07-2026, Due Date 30-08-2026. Lines: Maintenance Apr-Jun 2026 (1720 sqft x 8.07 x 3) 13,880.00; Club House 1,050.00; Infrastructure 409.00.
- Total Amount Received Rs 15,339.00 ("Rupees Fifteen Thousand Three Hundred Thirty Nine Only"). Account ICICI Bank, Txn 0ec470dedc1c455ab42f58e9c7729305, gateway paytm, convenience fee 0.00.
- Related message_35 (service provider, 2026-07-24): payment received 24 July 2026; receipt has final INR amount and original due date.
- VERDICT: 15339 INR settled 2026-07-24. Confirms; already paid, nothing further due on 30 Aug.

### image_09 -> event_5170 (user_55, INR, request_55)
- Doc: "Receipt", Water Bill Jan-Mar 2026, Invoice 6320, Charge Date 07-06-2026, Due Date 02-07-2026, Charged 723.00.
- Total Amount Received Rs 723.00. Indian Bank, Txn 39350810ed9045da91798478b89ca561, paytm, fee 0.00.
- VERDICT: 723 INR settled 2026-06-07. Confirms; paid.

### image_10 -> event_6033 (user_64, INR, request_64)
- Doc: multi-page tax invoice (22 line items: cereals, buttermilk, soft drinks, snack bars, chocolates), HSN codes, CGST/SGST 2.5% and 20%.
- Sub Total 72,045.00; CGST2.5 1,513.13; SGST2.5 1,513.13; CGST20 2,304.00; SGST20 2,304.00; Total Rs 79,679.26; Balance Due Rs 79,679.26 ("Seventy-Nine Thousand Six Hundred Seventy-Nine and Twenty-Six Paise Only"). No date/invoice number visible; "Thanks for your business" note.
- Related message_47 (UrbanCart, 2024-05-29, no event id): a foreign-currency refund still processing; separate matter (pending credit, do not count).
- VERDICT: 79679.26 INR, pending debit settling 2024-06-10. Confirms; balance still due (reserve it).

### image_11 -> event_6859 (user_73, INR, request_73)
- Doc: PROVISIONAL BILL, Jeevan Hospital (Reg DR86486, Pune), Patient "DUMMY PATIENT", Admission 000001, admitted 18-Jan-2023 12:19 PM, bill Date 19-Jan-2023, discharge blank.
- Room & Nursing 1650.00; OT 1000.00; Professional Fees 1000.00. Total Bill Amount 3650.00; Amount Payable 3650.00; Amount Paid 0.00; Balance 3650.00; "Paid amount in words: Zero". Detailed breakup visible (bed 250, nursing 1400, OT 1000, Dr fee 500 shown; page cut).
- VERDICT: 3650 INR scheduled debit settling 2023-01-23. Confirms; unpaid/provisional.

### image_12 -> event_7307 (user_78, home INR, request_78)
- Doc: taxi receipt, CityCab Service, License TC-5567, 01/10/2025 21:45, Trip CC-8923, Vehicle 142, Driver Mike R., 12.3 mi. Ride $28.50 + Airport Surcharge $5.00 = Subtotal $33.50, Tax $0.00, Total $33.50; Cash Paid $40.00, Change $6.50; barcode 892320251001.
- VERDICT: 33.50 USD settled 2025-10-01. FOREIGN currency vs INR home currency; event row already says USD. Using exchange_rates.csv 2025-10-01 USD->INR 83.33 => 2791.56 INR. Confirms.

### image_13 -> event_7941 (user_84, INR, request_84)
- Doc: online order details screenshot. DailyObjects Mumbai City Tote Bag Rs 699; Ivory - Navy All Time Tote Bag Rs 1,599. Item Total (2 items) Rs 2,298; Delivery Free; Total paid Rs 2,298 incl. taxes and delivery. No date/order number visible.
- Related message_64 (BuyBox, 2026-04-03): order paid in INR on 3 April 2026; receipt has final amount.
- VERDICT: 2298 INR settled 2026-04-03. Confirms.

### image_14 -> event_9421 (user_101, INR, request_101)
- Doc: handwritten pharmacy cash memo (partially cropped). Lines: 2 Samhan 1500.00; 2 Moov spray 724.00; 1 Axe oil 796.00; 2 Stayfree 550.00; 2 Benadryl 303.00 and 670.00 (six amounts in the column: 1500, 724, 796, 550, 303, 670). A signature scribble crosses the 670 line but it is NOT a strike-out: 1500+724+796+550+303+670 = 4543 exactly. TOTAL 4543.00. Footer "Prices Charged Include all Taxes", "Goods once sold cannot be taken back". No date.
- Related message_75 is about a prize payout (event_9420); unrelated.
- VERDICT: 4543 INR settled 2025-11-02. Confirms.

### image_15 -> event_9806 (user_105, INR, request_105)
- Doc: airline GST invoice, InterGlobe Aviation Limited (IndiGo). Date 07-Jun-2026, Passenger Akarsh Jain, PNR UC83TT, Flight 6E-861 DEL->BLR, Place of Supply Delhi, Currency INR.
- Air Travel 9,124.00 taxable + CGST 228 + SGST 228 = 9,580.00; Airport Charges 388.00 (non-taxable). Grand Total 9,968.00. Notes 1-9 are legal boilerplate.
- Related message_79 (Nova Securities) is about unrealized portfolio value (event_9805); unrelated and not cash.
- VERDICT: 9968 INR settled 2026-06-07. Confirms.

### image_16 -> event_10521 (user_113, INR, request_113)
- Doc: EV charging invoice, station Krishnagiri (Polupalli, Tamil Nadu), Charge Point 1110, CCS2, HSN 996749, 12.58 kWh @ 26.49/kWh, charged on 03/09/2026 12:35:10 am, duration 00:15:26, amount 333.24, CGST 9% 29.99, SGST 9% 29.99, Total 393.22, Payment method WALLET, "Three Hundred and Ninety Three Rupees And Twenty Two Paise Only". Jurisdiction boilerplate; "computer generated invoice".
- Related message_86 (MoneyHub, 2026-09-03): confirms the wallet charge AND states the employer confirmed a USD 1296 salary credit for 15 September 2026 (matches the monthly "International employer payroll" series of 1296 USD on the 15th; exchange_rates.csv has 2026-09-15 USD->INR 83.33). The parent should check whether a 2026-09-15 salary event row exists; if not, the message is the confirmation of that income.
- VERDICT: 393.22 INR settled 2026-09-03. Confirms.
