# 03 - messages.csv template analysis

Source: `dataset/messages.csv` (215 rows; 165 English, 50 Indonesian). Every message has a fixed intro sentence (company/bank name varies), one or two content sentences generated from a slot template, and a trailing ref (`Payroll ref EMP-nnnn` / `Case ref SER-nnnn` / `Txn ref BAN-nnnn` / `Order ref MER-nnnn` / `Account ref FIN-nnnn`). Intro sentences and refs carry no financial information; the regexes in `03_message_regexes.json` key on the content sentences only (use `re.search`). All 215 messages match exactly one template (verified, 0 misses, 0 double matches).

Machine-readable outputs: `03_message_regexes.json` (patterns + adjustment type per template) and `03_messages_parsed.json` (one object per message).

## 1. Template overview

| id | adjustment_type | n | EN/ID | source_type | with request_id | with related_event_id | gist |
|---|---|---|---|---|---|---|---|
| T01_salary_increase | salary_amount_change | 9 | 6/3 | employer | 5 | 0 | Permanent salary raise to {amount} effective {date}. |
| T02_salary_confirmed_onetime_unspecified | no_effect | 1 | 0/1 | employer | 1 | 0 | Regular salary confirmed; a one-time adjustment will appear separately but no amount is given. |
| T03_bonus_pending_review | unconfirmed_income | 8 | 5/3 | employer | 3 | 0 | Quarterly bonus not approved: amount and date unknown. |
| T04_temporary_reduced_pay | salary_amount_change | 10 | 7/3 | employer | 6 | 0 | Next payroll is a temporarily reduced amount {amount}. |
| T05_salary_date_change | salary_date_change | 7 | 6/1 | employer | 3 | 0 | Next confirmed salary moves to {date}. |
| T06_salary_reduced_unpaid_leave | salary_amount_change | 10 | 10/0 | employer | 9 | 0 | Next salary only is reduced to {amount} (unpaid leave). |
| T07_base_salary_commission_pending | salary_amount_change | 9 | 7/2 | employer | 5 | 0 | Base salary {amount} confirmed; commission on open deals is not earned yet. |
| T08_seasonal_contract_ended | income_ended | 9 | 5/4 | employer | 5 | 0 | Seasonal contract ended; no further income confirmed. |
| T09_salary_resumes_childcare | salary_amount_change | 8 | 8/0 | employer | 5 | 0 | Salary {amount} resumes on {date} after leave; a new recurring childcare expense (amount unspecified) starts the same month. |
| T10_first_salary_credit_date | one_time_confirmed_income | 14 | 13/1 | employer | 7 | 0 | First salary {amount} confirmed for {date}. |
| T11_first_salary_new_employer | one_time_confirmed_income | 7 | 5/2 | employer | 3 | 0 | First salary from new employer {amount} confirmed for {date}. |
| T12_first_salary_scheduled | one_time_confirmed_income | 6 | 3/3 | employer | 1 | 0 | First salary {amount} approved and scheduled for {date}. |
| T13_foreign_salary_confirmed | one_time_confirmed_income | 6 | 5/1 | employer | 3 | 0 | Foreign-currency salary {amount} confirmed for {date}; convert at the settlement-date rate. |
| T14_regular_plus_arrears | one_time_confirmed_income | 8 | 6/2 | employer | 4 | 0 | Regular salary {amount} plus a one-time arrears credit {amount2} on the next payroll. |
| T15_household_income_ended | salary_amount_change | 7 | 5/2 | employer | 5 | 0 | One household income stream ended; remaining confirmed monthly salary is {amount}. |
| T16_employment_ended | income_ended | 4 | 3/1 | employer | 3 | 0 | Employment ended; no salary after the final settlement. |
| T17_reimbursement_not_salary | no_effect | 3 | 2/1 | employer | 1 | 3 | Employer credit is a one-off expense reimbursement, not salary; do not treat as recurring. |
| T18_gig_payout_pending | pending_credit_not_available | 8 | 5/3 | service_provider | 4 | 0 | Gig-platform payout still pending; balance not withdrawable. |
| T19_rent_increase_percent | expense_increase | 7 | 6/1 | service_provider | 4 | 0 | Monthly rent rises by {percent}% from the next rent payment. |
| T20_invoice_approved | one_time_confirmed_income | 15 | 13/2 | service_provider | 8 | 0 | One invoice {amount} approved, settling {date}; other invoices unconfirmed. |
| T21_receipt_confirms_settled_expense | no_effect | 2 | 2/0 | merchant, service_provider | 2 | 2 | Receipt confirms a settled expense whose amount is blank in events; read amount from the linked image. |
| T22_wallet_charge_plus_foreign_salary | one_time_confirmed_income | 1 | 1/0 | financial_service | 1 | 1 | Wallet charge confirmed (amount from image) and a foreign-currency salary {amount} confirmed for {date_long}. |
| T23_internal_transfer | internal_transfer_ignore | 6 | 5/1 | bank | 6 | 0 | Matching debit/credit pair is an own-account transfer; net zero. |
| T24_debit_failed_retry | payment_delayed | 4 | 4/0 | bank | 3 | 4 | Failed bill debit will be retried; the bill is still owed. |
| T25_card_dispute_open | dispute_ignore | 6 | 5/1 | bank | 4 | 6 | Disputed duplicate card charge; no reversal yet, so the debit still counts and no credit is assumed. |
| T26_two_card_minimums | no_effect | 2 | 2/0 | bank | 2 | 0 | Two separate card minimums are both due; do not merge them as duplicates. |
| T27_refund_initiated_not_received | pending_credit_not_available | 7 | 6/1 | merchant | 6 | 7 | Merchant refund initiated but not credited. |
| T28_foreign_refund_processing | pending_credit_not_available | 6 | 6/0 | merchant | 4 | 0 | Foreign-currency refund still processing; home-currency value unknown until settlement. |
| T29_foreign_bill_charged | no_effect | 3 | 2/1 | merchant | 2 | 0 | A bill was charged in foreign currency; convert with the settlement-date rate (still a debit). |
| T30_portfolio_value_up | no_effect | 4 | 4/0 | financial_service | 4 | 4 | Unrealized portfolio gain; no cash. |
| T31_investment_value_down | no_effect | 3 | 1/2 | financial_service | 1 | 3 | Unrealized investment loss; no cash. |
| T32_prize_claim_processing | pending_credit_not_available | 4 | 3/1 | financial_service | 2 | 0 | Prize payment verified but not credited. |
| T33_prize_proceeds_received | no_effect | 6 | 6/0 | financial_service | 3 | 6 | Prize already settled; one-off, no further payments. |
| T34_investment_sale_settled | no_effect | 3 | 2/1 | financial_service | 3 | 3 | Investment sale proceeds already settled as cash; no more pending. |
| T35_scam_prize_fee | scam_ignore | 2 | 1/1 | financial_service | 0 | 0 | Advance-fee prize scam; ignore entirely. |

Adjustment-type totals: one_time_confirmed_income=57, salary_amount_change=53, no_effect=27, pending_credit_not_available=25, income_ended=13, unconfirmed_income=8, salary_date_change=7, expense_increase=7, internal_transfer_ignore=6, dispute_ignore=6, payment_delayed=4, scam_ignore=2.

## 2. Template details

### T01_salary_increase  (n=9, salary_amount_change)

- English form: Your monthly salary has increased to {CUR} {amount}. The change applies from {date}. The revised amount will appear on your next payslip.
- Indonesian form: Gaji bulanan Anda naik menjadi {CUR} {amount}. Perubahan ini berlaku mulai {date}. Jumlah yang diperbarui akan terlihat pada slip gaji berikutnya.
- source_type: employer; request_id populated in 5/9; related_event_id populated in 0/9
- Captured fields: amount, currency, date
- Engine implication: Permanent raise. Set the recurring salary amount to {amount} for every salary credit on/after {date}. Earlier scheduled credits keep the old amount.
- message_ids: message_01, message_26, message_33, message_40, message_89, message_104, message_126, message_151, message_169

### T02_salary_confirmed_onetime_unspecified  (n=1, no_effect)

- English form: (no English instance) Your regular salary for the next payroll is confirmed. Your next payslip will show the regular pay and any one-off adjustment separately.
- Indonesian form: Gaji rutin untuk penggajian berikutnya sudah dikonfirmasi. Slip gaji berikutnya akan menampilkan gaji rutin dan penyesuaian satu kali secara terpisah.
- source_type: employer; request_id populated in 1/1; related_event_id populated in 0/1
- Captured fields: none
- Engine implication: No amount, no date. Keep the historical recurring salary. Do NOT invent a one-off credit. The only instance (message_02, user_03/request_03) coincides with image_01 -> event_253 'August 2019 net salary' whose amount is blank: the salary amount for that payroll must come from the image, and that already-settled credit is the whole effect. If a later image/event states the adjustment amount, count it once on its settlement date; otherwise nothing.
- message_ids: message_02

### T03_bonus_pending_review  (n=8, unconfirmed_income)

- English form: Your quarterly bonus is still subject to the final performance review. The final amount and payment date have not been approved yet. We'll send another update once payroll confirms the amount and date.
- Indonesian form: Bonus kuartalan Anda masih menunggu hasil akhir penilaian kinerja. Jumlah akhir dan tanggal pembayaran belum disetujui. Kami akan mengirim pembaruan setelah tim payroll mengonfirmasi jumlah dan tanggalnya.
- source_type: employer; request_id populated in 3/8; related_event_id populated in 0/8
- Captured fields: none
- Engine implication: unconfirmed_income: exclude any bonus. If financial_events has a pending/scheduled bonus row for the user, do not count it until it settles.
- message_ids: message_03, message_48, message_98, message_144, message_159, message_177, message_199, message_212

### T04_temporary_reduced_pay  (n=10, salary_amount_change)

- English form: Your temporary monthly pay is {CUR} {amount}. The reduced amount continues for the next payroll. This is the amount currently scheduled for the affected pay cycle.
- Indonesian form: Gaji bulanan sementara Anda adalah {CUR} {amount}. Jumlah yang lebih rendah masih berlaku untuk penggajian berikutnya. Inilah jumlah yang saat ini dijadwalkan untuk periode penggajian tersebut.
- source_type: employer; request_id populated in 6/10; related_event_id populated in 0/10
- Captured fields: amount, currency
- Engine implication: Next salary credit (first one after sent_at) = {amount}. Subsequent salaries revert to the regular historical amount (conservative alternative: keep reduced amount for the whole forecast if history already shows reduced pay).
- message_ids: message_04, message_36, message_65, message_77, message_100, message_122, message_138, message_153, message_171, message_193

### T05_salary_date_change  (n=7, salary_date_change)

- English form: Your confirmed salary is now expected on {date}. This replaces the payroll date shown in the earlier update. Please use the revised date for anything you normally pay around payday.
- Indonesian form: Gaji yang sudah dikonfirmasi kini diperkirakan masuk pada {date}. Tanggal ini menggantikan tanggal penggajian pada pemberitahuan sebelumnya. Gunakan tanggal terbaru ini untuk pembayaran yang biasanya dilakukan saat gajian.
- source_type: employer; request_id populated in 3/7; related_event_id populated in 0/7
- Captured fields: date
- Engine implication: Move the next salary credit (the one that would fall in the month of {date}) to {date}. Amount unchanged. Later months keep the usual day.
- message_ids: message_05, message_50, message_73, message_101, message_131, message_154, message_165

### T06_salary_reduced_unpaid_leave  (n=10, salary_amount_change)

- English form: Your next salary is reduced to {CUR} {amount}. The adjustment is due to approved unpaid leave. The adjustment will be visible on your next payslip.
- Indonesian form: (no Indonesian instance)
- source_type: employer; request_id populated in 9/10; related_event_id populated in 0/10
- Captured fields: amount, currency
- Engine implication: Next salary credit only = {amount}; later salaries revert to regular. NOTE: in some rows the stated amount equals the historical regular salary (e.g. user_08 history shows 1422.85 regular and an already-settled 782.57 in Jan); apply the message amount to the next payroll as stated.
- message_ids: message_06, message_44, message_87, message_102, message_115, message_132, message_140, message_148, message_155, message_195

### T07_base_salary_commission_pending  (n=9, salary_amount_change)

- English form: Your confirmed base salary is {CUR} {amount}. The commission shown for open deals is still pending approval. Open deals will stay out of the payout until the commission is marked as earned.
- Indonesian form: Gaji pokok yang dikonfirmasi adalah {CUR} {amount}. Komisi dari transaksi yang masih berjalan belum disetujui. Transaksi yang masih berjalan tidak masuk pembayaran sampai komisinya dinyatakan diperoleh.
- source_type: employer; request_id populated in 5/9; related_event_id populated in 0/9
- Captured fields: amount, currency
- Engine implication: Recurring salary = base {amount}. Exclude any commission events that are pending/unsettled (unconfirmed_income).
- message_ids: message_08, message_58, message_60, message_70, message_78, message_82, message_128, message_139, message_194

### T08_seasonal_contract_ended  (n=9, income_ended)

- English form: The current seasonal contract has ended. No off-season income or renewal has been confirmed. We'll contact you separately if another shift block or contract is approved.
- Indonesian form: Kontrak musiman saat ini telah berakhir. Belum ada pendapatan di luar musim atau perpanjangan kontrak yang dikonfirmasi. Kami akan menghubungi Anda jika jadwal kerja atau kontrak berikutnya disetujui.
- source_type: employer; request_id populated in 5/9; related_event_id populated in 0/9
- Captured fields: none
- Engine implication: income_ended from sent_at date: do not project any further salary/contract credits, even if history looks recurring.
- message_ids: message_09, message_21, message_45, message_103, message_160, message_166, message_186, message_189, message_206

### T09_salary_resumes_childcare  (n=8, salary_amount_change)

- English form: Regular salary of {CUR} {amount} resumes on {date}. A new recurring childcare payment begins in the same month. The updated pay and deductions will appear from the next cycle.
- Indonesian form: (no Indonesian instance)
- source_type: employer; request_id populated in 5/8; related_event_id populated in 0/8
- Captured fields: amount, currency, date
- Engine implication: Salary {amount} counted on {date} and monthly thereafter (history typically shows a gap for leave). Childcare: amount not stated -> only add if a childcare expense row exists in financial_events; otherwise no expense change (do not invent).
- message_ids: message_10, message_63, message_66, message_91, message_97, message_113, message_120, message_170

### T10_first_salary_credit_date  (n=14, one_time_confirmed_income)

- English form: Your first salary will be {CUR} {amount}. The confirmed credit date is {date}. The money will appear after the bank posts the credit.
- Indonesian form: Gaji pertama Anda sebesar {CUR} {amount}. Tanggal kredit yang dikonfirmasi adalah {date}. Dana akan terlihat setelah bank mencatat kreditnya.
- source_type: employer; request_id populated in 7/14; related_event_id populated in 0/14
- Captured fields: amount, currency, date
- Engine implication: one_time_confirmed_income {amount} on {date}. If history already shows the same monthly salary, treat as confirmation (dedupe). Do not project months beyond {date} unless history supports a recurrence.
- message_ids: message_11, message_22, message_29, message_32, message_54, message_85, message_107, message_111, message_143, message_162, message_178, message_181, message_188, message_200

### T11_first_salary_new_employer  (n=7, one_time_confirmed_income)

- English form: Your first salary from the new employer is {CUR} {amount}. It is confirmed for {date}. Bank processing may take the usual time after the payroll is released.
- Indonesian form: Gaji pertama dari perusahaan baru adalah {CUR} {amount}. Pembayaran sudah dikonfirmasi untuk {date}. Pemrosesan bank dapat memerlukan waktu seperti biasa setelah gaji dikirim.
- source_type: employer; request_id populated in 3/7; related_event_id populated in 0/7
- Captured fields: amount, currency, date
- Engine implication: Same as T10.
- message_ids: message_31, message_38, message_80, message_116, message_124, message_149, message_196

### T12_first_salary_scheduled  (n=6, one_time_confirmed_income)

- English form: Your first salary of {CUR} {amount} is scheduled for {date}. Payroll has approved the payment and sent it for processing. The credit will show only after the bank processes the payroll file.
- Indonesian form: Gaji pertama Anda sebesar {CUR} {amount} dijadwalkan pada {date}. Tim payroll sudah menyetujui pembayaran dan mengirimkannya untuk diproses. Dana baru akan terlihat setelah bank memproses berkas penggajian.
- source_type: employer; request_id populated in 1/6; related_event_id populated in 0/6
- Captured fields: amount, currency, date
- Engine implication: Same as T10.
- message_ids: message_81, message_125, message_156, message_182, message_190, message_210

### T13_foreign_salary_confirmed  (n=6, one_time_confirmed_income)

- English form: Your salary of {CUR} {amount} is confirmed for {date}. The receiving bank will convert it using the rate applied on the settlement date. The amount received in your home currency will depend on the settlement-date conversion.
- Indonesian form: Gaji sebesar {CUR} {amount} dikonfirmasi untuk {date}. Bank penerima akan mengonversinya dengan kurs pada tanggal penyelesaian. Jumlah yang diterima dalam mata uang utama bergantung pada kurs tanggal penyelesaian.
- source_type: employer; request_id populated in 3/6; related_event_id populated in 0/6
- Captured fields: amount, currency, date
- Engine implication: one_time_confirmed_income {amount} {CUR} on {date}; convert to home currency with exchange_rates row dated {date} ({CUR}->home). Dedupe against a scheduled salary event on the same date.
- message_ids: message_53, message_74, message_95, message_137, message_191, message_204

### T14_regular_plus_arrears  (n=8, one_time_confirmed_income)

- English form: Your regular salary for the next payroll is {CUR} {amount}. The same payroll includes a one-time arrears adjustment of {CUR} {amount2}. Your next payslip will show the regular pay and any one-off adjustment separately.
- Indonesian form: Gaji rutin Anda untuk penggajian berikutnya adalah {CUR} {amount}. Penggajian yang sama mencakup penyesuaian tunggakan satu kali sebesar {CUR} {amount2}. Slip gaji berikutnya akan menampilkan gaji rutin dan penyesuaian satu kali secara terpisah.
- source_type: employer; request_id populated in 4/8; related_event_id populated in 0/8
- Captured fields: amount, currency, amount2, currency2
- Engine implication: Regular salary confirmed at {amount}; add ONE extra credit {amount2} on the next salary date after sent_at. Dedupe: if an 'arrears' event with that amount is already settled/scheduled (e.g. user_28 event_2508), do not add again. In parsed JSON `amount` = arrears amount2; regular amount is in notes.
- message_ids: message_20, message_27, message_62, message_90, message_112, message_127, message_176, message_211

### T15_household_income_ended  (n=7, salary_amount_change)

- English form: One household employment record has ended. The remaining confirmed monthly salary is {CUR} {amount}. Any income that has ended should be removed from future estimates.
- Indonesian form: Salah satu sumber pendapatan kerja rumah tangga telah berakhir. Sisa gaji bulanan yang dikonfirmasi adalah {CUR} {amount}. Pendapatan yang sudah berakhir harus dikeluarkan dari perkiraan berikutnya.
- source_type: employer; request_id populated in 5/7; related_event_id populated in 0/7
- Captured fields: amount, currency
- Engine implication: Users have two salary streams (e.g. 'Primary household salary' + 'Second household income'). Keep only ONE recurring salary = {amount} per month; drop the other stream from the forecast.
- message_ids: message_30, message_37, message_42, message_119, message_180, message_187, message_203

### T16_employment_ended  (n=4, income_ended)

- English form: Your employment has ended. There are no regular salary payments scheduled after the final settlement. Details of any final settlement will be sent separately.
- Indonesian form: Hubungan kerja Anda telah berakhir. Tidak ada pembayaran gaji rutin yang dijadwalkan setelah penyelesaian akhir. Rincian penyelesaian akhir akan dikirim secara terpisah.
- source_type: employer; request_id populated in 3/4; related_event_id populated in 0/4
- Captured fields: none
- Engine implication: income_ended: no salary after the last settled 'Final employer payroll'. Do not invent a final-settlement amount.
- message_ids: message_57, message_84, message_129, message_192

### T17_reimbursement_not_salary  (n=3, no_effect)

- English form: The latest employer credit is the reimbursement for your earlier work expense. The claim is now closed and no additional reimbursement is scheduled. This payment is linked to an earlier work expense, not your regular salary.
- Indonesian form: Dana terbaru dari perusahaan adalah penggantian atas biaya kerja Anda sebelumnya. Klaim sudah ditutup dan tidak ada penggantian tambahan yang dijadwalkan. Pembayaran ini terkait biaya kerja sebelumnya, bukan gaji rutin Anda.
- source_type: employer; request_id populated in 1/3; related_event_id populated in 3/3
- Captured fields: none
- Engine implication: Confirms a settled one-off credit (already in balance). Exclude it from salary recurrence detection; no future reimbursement.
- message_ids: message_117, message_150, message_174

### T18_gig_payout_pending  (n=8, pending_credit_not_available)

- English form: The next {company} payout is still pending. The weekly earnings shown in the {company} app can change until the payout is closed. The balance isn't withdrawable until the payout shows as completed.
- Indonesian form: Pembayaran berikutnya dari {company} masih tertunda. Penghasilan mingguan di aplikasi {company} masih dapat berubah sampai pembayaran diselesaikan. Saldo belum dapat ditarik sampai status pembayaran menunjukkan selesai.
- source_type: service_provider; request_id populated in 4/8; related_event_id populated in 0/8
- Captured fields: company
- Engine implication: pending_credit_not_available: exclude pending gig payout credits until settled; only settled weekly payouts count toward recurrence.
- message_ids: message_07, message_19, message_34, message_43, message_94, message_123, message_158, message_168

### T19_rent_increase_percent  (n=7, expense_increase)

- English form: The renewed lease increases monthly rent by {percent}%. The new amount applies from the next rent payment. The new amount will be used for the next rent payment.
- Indonesian form: Perpanjangan sewa menaikkan biaya sewa bulanan sebesar {percent}%. Jumlah baru berlaku mulai pembayaran sewa berikutnya. Jumlah baru akan digunakan untuk pembayaran sewa berikutnya.
- source_type: service_provider; request_id populated in 4/7; related_event_id populated in 0/7
- Captured fields: percent
- Engine implication: expense_increase on the user's recurring rent event: new_amount = last settled rent * (1 + {percent}/100), for every projected rent debit after sent_at. (All 7 instances say 12%.)
- message_ids: message_12, message_51, message_55, message_61, message_105, message_147, message_175

### T20_invoice_approved  (n=15, one_time_confirmed_income)

- English form: The client approved an invoice payment of {CUR} {amount}. Settlement is expected on {date}; the other submitted invoices are still awaiting approval. Only invoices marked as confirmed should be included in the upcoming payout.
- Indonesian form: Klien menyetujui pembayaran faktur sebesar {CUR} {amount}. Penyelesaian diperkirakan pada {date}; faktur lain yang diajukan masih menunggu persetujuan. Hanya faktur yang sudah dikonfirmasi yang dapat dimasukkan dalam pembayaran berikutnya.
- source_type: service_provider; request_id populated in 8/15; related_event_id populated in 0/15
- Captured fields: amount, currency, date
- Engine implication: one_time_confirmed_income {amount} on {date}. Freelancers: do not project other invoices/irregular history as recurring income; other submitted invoices are unconfirmed.
- message_ids: message_18, message_24, message_46, message_49, message_56, message_68, message_72, message_76, message_83, message_93, message_96, message_109, message_130, message_141, message_173

### T21_receipt_confirms_settled_expense  (n=2, no_effect)

- English form: Your property maintenance payment was received on {D Month YYYY}. The receipt has the final {CUR} amount and the original due date.  |  {Merchant} confirmed that the tote bag order was paid in {CUR} on {D Month YYYY}. The receipt has the final amount.
- Indonesian form: (no Indonesian instance)
- source_type: merchant, service_provider; request_id populated in 2/2; related_event_id populated in 2/2
- Captured fields: currency, date_long
- Engine implication: no_effect on the forecast beyond confirming the linked settled event; the event's blank amount must be read from the image (image_08 -> event_4535, image_13 -> event_7941). The settled debit is already reflected in current balance.
- message_ids: message_35, message_64

### T22_wallet_charge_plus_foreign_salary  (n=1, one_time_confirmed_income)

- English form: Your wallet was charged for the session at {place} on {D Month YYYY} at {time}. The receipt contains the final {CUR} amount. Your employer has confirmed a {CUR} {amount} salary credit for {D Month YYYY}. The salary will use the exchange rate when it settles.
- Indonesian form: (no Indonesian instance)
- source_type: financial_service; request_id populated in 1/1; related_event_id populated in 1/1
- Captured fields: amount, currency, date_long
- Engine implication: Two facts: (1) confirms settled event_10521 (amount from image_16); (2) one_time_confirmed_income USD 1296 on 2026-09-15, converted with the USD->INR rate dated 2026-09-15.
- message_ids: message_86

### T23_internal_transfer  (n=6, internal_transfer_ignore)

- English form: The matching debit and credit came from a transfer between your two accounts. Both accounts are registered under the same account holder. Both entries will remain visible in your transaction history.
- Indonesian form: Debit dan kredit dengan jumlah yang sama berasal dari transfer antara dua rekening Anda. Kedua rekening terdaftar atas nama pemilik yang sama. Kedua transaksi akan tetap terlihat dalam riwayat rekening Anda.
- source_type: bank; request_id populated in 6/6; related_event_id populated in 0/6
- Captured fields: none
- Engine implication: internal_transfer_ignore: the matching debit/credit pair is net zero; exclude both from income/expense recurrence detection.
- message_ids: message_13, message_23, message_41, message_135, message_202, message_213

### T24_debit_failed_retry  (n=4, payment_delayed)

- English form: The previous debit attempt failed. The bill is still outstanding and another debit will be attempted. The bill is still open and another debit may be attempted.
- Indonesian form: (no Indonesian instance)
- source_type: bank; request_id populated in 3/4; related_event_id populated in 4/4
- Captured fields: none
- Engine implication: payment_delayed: the linked 'failed' utilities debit is still owed; reserve its amount as a pending debit expected shortly after the failed date (treat like a pending expense).
- message_ids: message_69, message_179, message_198, message_201

### T25_card_dispute_open  (n=6, dispute_ignore)

- English form: The extra card charge is still being investigated. A reversal has not been posted to the account yet. The dispute is open and no reversal has been posted yet.
- Indonesian form: Tagihan kartu tambahan masih dalam penyelidikan. Dana pembalikannya belum tercatat di rekening. Sengketa masih terbuka dan dana pembalikan belum tercatat.
- source_type: bank; request_id populated in 4/6; related_event_id populated in 6/6
- Captured fields: none
- Engine implication: dispute_ignore: keep the pending 'Possible duplicate card charge' debit reserved; do not add any reversal credit.
- message_ids: message_106, message_121, message_157, message_164, message_183, message_197

### T26_two_card_minimums  (n=2, no_effect)

- English form: There are minimum payments due on two separate card accounts this month. A payment to one card will not cover the amount due on the other card. The minimums belong to separate accounts, so one payment won't clear the other.
- Indonesian form: (no Indonesian instance)
- source_type: bank; request_id populated in 2/2; related_event_id populated in 0/2
- Captured fields: none
- Engine implication: no_effect: both card-minimum debits are real; never collapse them as duplicates.
- message_ids: message_136, message_161

### T27_refund_initiated_not_received  (n=7, pending_credit_not_available)

- English form: Your refund has been initiated but has not reached your account yet. [Most refunds are completed within ten business days.] We'll send another update when the credit is completed.
- Indonesian form: Pengembalian dana sudah diproses, tetapi belum masuk ke rekening Anda. Sebagian besar pengembalian dana selesai dalam sepuluh hari kerja. Kami akan mengirim pembaruan saat kredit sudah selesai.
- source_type: merchant; request_id populated in 6/7; related_event_id populated in 7/7
- Captured fields: none
- Engine implication: pending_credit_not_available: exclude the linked pending refund credit until it settles.
- message_ids: message_14, message_25, message_39, message_59, message_152, message_172, message_215

### T28_foreign_refund_processing  (n=6, pending_credit_not_available)

- English form: The foreign-currency refund is still processing. [The final home-currency credit will be calculated when the refund settles.] The home-currency credit may change with the settlement-date rate.
- Indonesian form: (no Indonesian instance)
- source_type: merchant; request_id populated in 4/6; related_event_id populated in 0/6
- Captured fields: none
- Engine implication: pending_credit_not_available: exclude the pending foreign refund.
- message_ids: message_47, message_133, message_146, message_167, message_184, message_214

### T29_foreign_bill_charged  (n=3, no_effect)

- English form: The bill was charged in a foreign currency. Your bank will confirm the final home-currency amount when the transaction settles. The final home-currency amount will use the rate applied when it settles.
- Indonesian form: Tagihan dikenakan dalam mata uang asing. Bank Anda akan mengonfirmasi jumlah akhir dalam mata uang utama saat transaksi selesai. Jumlah akhir dalam mata uang utama menggunakan kurs saat transaksi selesai.
- source_type: merchant; request_id populated in 2/3; related_event_id populated in 0/3
- Captured fields: none
- Engine implication: no_effect beyond normal handling: the foreign debit stands; convert with the exchange_rates row for its settlement date.
- message_ids: message_118, message_145, message_208

### T30_portfolio_value_up  (n=4, no_effect)

- English form: Your portfolio's displayed market value has increased substantially. No units have been sold and no cash proceeds have been generated. The displayed value will continue to move with market prices.
- Indonesian form: (no Indonesian instance)
- source_type: financial_service; request_id populated in 4/4; related_event_id populated in 4/4
- Captured fields: none
- Engine implication: no_effect: unrealized non_cash valuation; never count as cash.
- message_ids: message_15, message_52, message_79, message_207

### T31_investment_value_down  (n=3, no_effect)

- English form: The displayed value of the investment has fallen. The holding has not been sold and there has been no cash transaction. The displayed value will continue to move with market prices.
- Indonesian form: Nilai investasi yang ditampilkan telah turun. Investasi tersebut belum dijual dan tidak ada transaksi tunai. Nilai yang ditampilkan akan terus berubah mengikuti harga pasar.
- source_type: financial_service; request_id populated in 1/3; related_event_id populated in 3/3
- Captured fields: none
- Engine implication: no_effect: unrealized loss, no cash impact.
- message_ids: message_163, message_185, message_205

### T32_prize_claim_processing  (n=4, pending_credit_not_available)

- English form: Your prize claim has been verified and is still in payment processing. The payment has not been credited to your account yet. We'll confirm again if and when the money is actually credited.
- Indonesian form: Klaim hadiah Anda sudah diverifikasi dan masih dalam proses pembayaran. Pembayaran tersebut belum masuk ke rekening Anda. Kami akan mengonfirmasi kembali jika dana benar-benar masuk.
- source_type: financial_service; request_id populated in 2/4; related_event_id populated in 0/4
- Captured fields: none
- Engine implication: pending_credit_not_available: exclude prize/lottery proceeds until settled.
- message_ids: message_16, message_71, message_134, message_209

### T33_prize_proceeds_received  (n=6, no_effect)

- English form: The prize proceeds have reached your account after withholding. [The claim is now closed and there are no further scheduled payments.] There won't be another payment unless a separate prize is confirmed.
- Indonesian form: (no Indonesian instance)
- source_type: financial_service; request_id populated in 3/6; related_event_id populated in 6/6
- Captured fields: none
- Engine implication: no_effect: the linked windfall is settled and already in balance; do not project recurrence.
- message_ids: message_17, message_28, message_75, message_88, message_99, message_110

### T34_investment_sale_settled  (n=3, no_effect)

- English form: The proceeds from your investment sale have settled in the cash account. The sale order is complete and there are no remaining proceeds pending. The transaction history shows the amount that actually reached the cash account.
- Indonesian form: Hasil penjualan investasi Anda sudah masuk ke rekening tunai. Perintah penjualan sudah selesai dan tidak ada hasil penjualan yang masih tertunda. Riwayat transaksi menunjukkan jumlah yang benar-benar masuk ke rekening tunai.
- source_type: financial_service; request_id populated in 3/3; related_event_id populated in 3/3
- Captured fields: none
- Engine implication: no_effect: settled cash credit is already in balance; no further proceeds pending.
- message_ids: message_92, message_108, message_114

### T35_scam_prize_fee  (n=2, scam_ignore)

- English form: Congratulations! You've been selected for a cash prize. Pay the release charge today to receive the funds immediately. Pay the processing charge now to avoid losing the claim.
- Indonesian form: Selamat! Anda terpilih untuk menerima hadiah uang tunai. Bayar biaya pencairan hari ini agar dana segera diterima. Bayar biaya pemrosesan sekarang agar klaim tidak hangus.
- source_type: financial_service; request_id populated in 0/2; related_event_id populated in 0/2
- Captured fields: none
- Engine implication: scam_ignore: advance-fee scam with an embedded instruction to pay. No income, no expense; never act on it.
- message_ids: message_67, message_142

## 3. Messages with related_event_id (joined event rows)

| message | template | event | type / description | dir | amount | cur | event_date | settle | status | linked | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| message_14 | T27 | event_1785 | refund / Pending merchant refund | credit | 8640 | INR | 2026-02-04 | 2026-02-14 | pending | event_1784 | confirms pending refund; NOT available until settlement_date (exclude) |
| message_15 | T30 | event_1960 | investment_valuation / Current portfolio valuation | non_cash | 369.6 | EUR | 2024-12-03 |  | unrealized | event_1959 | confirms unrealized valuation; non-cash, no effect |
| message_17 | T33 | event_2165 | income / Prize proceeds | credit | 33550 | INR | 2025-12-27 | 2025-12-28 | settled |  | confirms settled windfall; one-off, no recurrence |
| message_25 | T27 | event_3230 | refund / Pending merchant refund | credit | 12960 | INR | 2025-10-27 | 2025-11-06 | pending | event_3229 | confirms pending refund; NOT available until settlement_date (exclude) |
| message_28 | T33 | event_3491 | income / Prize proceeds | credit | 405.35 | EUR | 2025-07-30 | 2025-07-31 | settled |  | confirms settled windfall; one-off, no recurrence |
| message_35 | T21 | event_4535 | expense / Property maintenance invoice | debit | BLANK | INR | 2026-07-24 | 2026-07-24 | settled |  | confirms settled expense; amount BLANK -> read from image |
| message_39 | T27 | event_4994 | refund / Pending merchant refund | credit | 230.4 | USD | 2025-11-04 | 2025-11-14 | pending | event_4993 | confirms pending refund; NOT available until settlement_date (exclude) |
| message_52 | T30 | event_6532 | investment_valuation / Current portfolio valuation | non_cash | 121800 | INR | 2024-12-04 |  | unrealized | event_6531 | confirms unrealized valuation; non-cash, no effect |
| message_59 | T27 | event_7186 | refund / Pending merchant refund | credit | 8880 | INR | 2025-11-02 | 2025-11-12 | pending | event_7185 | confirms pending refund; NOT available until settlement_date (exclude) |
| message_64 | T21 | event_7941 | expense / Tote bag order | debit | BLANK | INR | 2026-04-03 | 2026-04-03 | settled |  | confirms settled expense; amount BLANK -> read from image |
| message_69 | T24 | event_8575 | debt_payment / Failed bill payment attempt | debit | 166 | EUR | 2024-09-01 | 2024-09-01 | failed |  | delays: failed debit will be retried; keep amount reserved as pending |
| message_75 | T33 | event_9420 | income / Prize proceeds | credit | 139700 | INR | 2025-10-26 | 2025-10-27 | settled |  | confirms settled windfall; one-off, no recurrence |
| message_79 | T30 | event_9805 | investment_valuation / Current portfolio valuation | non_cash | 70200 | INR | 2026-06-06 |  | unrealized | event_9804 | confirms unrealized valuation; non-cash, no effect |
| message_86 | T22 | event_10521 | expense / EV charging wallet payment | debit | BLANK | INR | 2026-09-03 | 2026-09-03 | settled |  | confirms settled expense (amount BLANK -> image_16) AND adds USD 1296 salary on 2026-09-15 |
| message_88 | T33 | event_10699 | income / Prize proceeds | credit | 32450 | INR | 2024-08-29 | 2024-08-30 | settled |  | confirms settled windfall; one-off, no recurrence |
| message_92 | T34 | event_11129 | investment_sale / Investment sale proceeds | credit | 13062500 | IDR | 2026-03-29 | 2026-03-30 | settled | event_11128 | confirms settled sale proceeds; already cash |
| message_99 | T33 | event_11925 | income / Prize proceeds | credit | 561 | USD | 2026-03-27 | 2026-03-28 | settled |  | confirms settled windfall; one-off, no recurrence |
| message_106 | T25 | event_12709 | expense / Possible duplicate card charge | debit | 134.75 | EUR | 2026-04-06 | 2026-04-10 | pending | event_12708 | confirms pending duplicate charge stands; no reversal credit |
| message_108 | T34 | event_13032 | investment_sale / Investment sale proceeds | credit | 53350 | INR | 2025-12-26 | 2025-12-27 | settled | event_13031 | confirms settled sale proceeds; already cash |
| message_110 | T33 | event_13207 | income / Prize proceeds | credit | 8228 | ZAR | 2025-04-29 | 2025-04-30 | settled |  | confirms settled windfall; one-off, no recurrence |
| message_114 | T34 | event_13663 | investment_sale / Investment sale proceeds | credit | 19602 | ZAR | 2024-05-30 | 2024-05-31 | settled | event_13662 | confirms settled sale proceeds; already cash |
| message_117 | T17 | event_14026 | refund / Employer expense reimbursement | credit | 818.4 | ZAR | 2025-02-01 | 2025-02-02 | settled | event_14025 | confirms settled one-off reimbursement; not salary |
| message_121 | T25 | event_14399 | expense / Possible duplicate card charge | debit | 1617 | ZAR | 2026-04-02 | 2026-04-06 | pending | event_14398 | confirms pending duplicate charge stands; no reversal credit |
| message_150 | T17 | event_17401 | refund / Employer expense reimbursement | credit | 83.16 | EUR | 2025-02-03 | 2025-02-04 | settled | event_17400 | confirms settled one-off reimbursement; not salary |
| message_152 | T27 | event_17662 | refund / Pending merchant refund | credit | 65.12 | EUR | 2025-04-30 | 2025-05-10 | pending | event_17661 | confirms pending refund; NOT available until settlement_date (exclude) |
| message_157 | T25 | event_18269 | expense / Possible duplicate card charge | debit | 8800 | INR | 2026-07-06 | 2026-07-10 | pending | event_18268 | confirms pending duplicate charge stands; no reversal credit |
| message_163 | T31 | event_19182 | investment_valuation / Current portfolio valuation | non_cash | 1664400 | IDR | 2024-06-05 |  | unrealized | event_19181 | confirms unrealized valuation; non-cash, no effect |
| message_164 | T25 | event_19334 | expense / Possible duplicate card charge | debit | 145.8 | USD | 2026-04-05 | 2026-04-09 | pending | event_19333 | confirms pending duplicate charge stands; no reversal credit |
| message_172 | T27 | event_20379 | refund / Pending merchant refund | credit | 9440 | INR | 2025-10-31 | 2025-11-10 | pending | event_20378 | confirms pending refund; NOT available until settlement_date (exclude) |
| message_174 | T17 | event_20615 | refund / Employer expense reimbursement | credit | 2166000 | IDR | 2025-01-31 | 2025-02-01 | settled | event_20614 | confirms settled one-off reimbursement; not salary |
| message_179 | T24 | event_21101 | debt_payment / Failed bill payment attempt | debit | 73 | EUR | 2024-03-02 | 2024-03-02 | failed |  | delays: failed debit will be retried; keep amount reserved as pending |
| message_183 | T25 | event_21582 | expense / Possible duplicate card charge | debit | 45.65 | EUR | 2026-07-03 | 2026-07-07 | pending | event_21581 | confirms pending duplicate charge stands; no reversal credit |
| message_185 | T31 | event_21785 | investment_valuation / Current portfolio valuation | non_cash | 2690400 | IDR | 2025-02-01 |  | unrealized | event_21784 | confirms unrealized valuation; non-cash, no effect |
| message_197 | T25 | event_23203 | expense / Possible duplicate card charge | debit | 988000 | IDR | 2026-07-04 | 2026-07-08 | pending | event_23202 | confirms pending duplicate charge stands; no reversal credit |
| message_198 | T24 | event_23306 | debt_payment / Failed bill payment attempt | debit | 192 | EUR | 2024-03-05 | 2024-03-05 | failed |  | delays: failed debit will be retried; keep amount reserved as pending |
| message_201 | T24 | event_23855 | debt_payment / Failed bill payment attempt | debit | 42 | EUR | 2024-09-02 | 2024-09-02 | failed |  | delays: failed debit will be retried; keep amount reserved as pending |
| message_205 | T31 | event_24352 | investment_valuation / Current portfolio valuation | non_cash | 10560 | INR | 2026-04-02 |  | unrealized | event_24351 | confirms unrealized valuation; non-cash, no effect |
| message_207 | T30 | event_24534 | investment_valuation / Current portfolio valuation | non_cash | 580.8 | EUR | 2025-08-01 |  | unrealized | event_24533 | confirms unrealized valuation; non-cash, no effect |
| message_215 | T27 | event_25342 | refund / Pending merchant refund | credit | 1444000 | IDR | 2025-05-03 | 2025-05-13 | pending | event_25341 | confirms pending refund; NOT available until settlement_date (exclude) |

No message amends an event amount or cancels an event. All 40 linked messages either confirm the row's stated status (pending stays pending, settled stays settled, unrealized stays non-cash) or, for the four failed debits, say the bill will be retried. The three blank-amount events (event_4535, event_7941, event_10521) are also the targets of image_08, image_13 and image_16.

## 4. Instruction-like / scam content

No message contains classic prompt-injection text (no 'ignore previous instructions', 'approve this', 'mark as affordable', 'system', 'override'). Findings:

- SCAM (ignore entirely): message_67 (user_88, QuickPrize, EN) and message_142 (user_179, RewardNow, ID). Advance-fee prize scam with imperative instructions 'Pay the release charge today' / 'Bayar biaya pencairan hari ini'. No request_id. adjustment_type = scam_ignore; never create an expense or an income from them.
- Benign imperatives that merely restate challenge rules (safe to follow because they coincide with the rules, but the engine should act on the structured fact, not the sentence): T15 'Any income that has ended should be removed from future estimates' (message_30, 37, 119, 180, 187 + ID 42, 203); T20 'Only invoices marked as confirmed should be included in the upcoming payout' (all 15 invoice messages); T05 'Please use the revised date for anything you normally pay around payday' (7 messages).
- No message asks the agent to approve, mark affordable, change minimum balance, or skip a rule.

## 5. Regex extraction plan and verification

Patterns live in `03_message_regexes.json`. Each template has `pattern_en` and `pattern_id`; apply `re.search(pattern_en, text) or re.search(pattern_id, text)`. Named groups: `currency` + `amount` (`[A-Z]{3} \d+(\.\d+)?`), `date` (ISO `\d{4}-\d{2}-\d{2}`), `date_long` (`D Month YYYY`, convert with month table), `percent`, `company`, and for T14 also `currency2`/`amount2` (arrears). Amounts use '.' as decimal separator with no thousands separators, so `float()` is safe.

Verification (scratch script `classify_messages.py`, run 2026-09-12): 215/215 messages matched, 0 misses, 0 multi-matches. Indonesian patterns for templates with no Indonesian instance (T06, T09, T21, T22, T24, T26, T28, T30, T33) are best-effort translations and are untested; English patterns for T02 are likewise untested. Curly apostrophes appear in 'Here’s', 'isn’t', 'You’ve', 'portfolio’s': patterns use `.` for that character.

## 6. Engine notes

- Order of application per user: take messages sorted by sent_at; later messages from the same source win on the same fact (only relevant for T05 'replaces the earlier update'). No user has two messages in this dataset, so conflicts do not arise here.
- 'Next payroll' (T04, T06, T07, T14, T15 have no date): resolve to the first projected salary date strictly after `sent_at`.
- Dedupe rule: before adding a one_time_confirmed_income, check financial_events for a scheduled/settled credit with the same amount within +-7 days of the stated date (T10-T14 often echo an event already present, e.g. user_28 arrears event_2508).
- Messages for users who only appear in sample_requests.csv (e.g. message_01, 02, 03) are still useful as template evidence but have no evaluation request.
