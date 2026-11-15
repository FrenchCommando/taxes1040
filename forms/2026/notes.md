# 2026 Key Numbers (PROVISIONAL year)

Status as of 2026-11-15: the federal computation is done from the final IRS numbers. The forms, field
mapping and NY are not final. There are no blank PDFs or `.keys` here yet, `2026` is not in
`main.py` `all_years`, and `marginal_rates.py` does not model the 2026 rules.

## Federal (final)

Sources: Rev. Proc. 2025-32 (2026 inflation adjustments, incl. OBBBA amendments),
Rev. Proc. 2025-19 (HSA), IRC 164(b)(7) (SALT), 170(p), 170(b)(1)(I), 68 as amended by OBBBA.

| Item | Single | MFJ |
|------|--------|-----|
| Standard deduction | $16,100 | $32,200 |
| 37% bracket starts | $640,600 | $768,700 |
| 0% cap gains ceiling | $49,450 | $98,900 |
| 15%/20% boundary | $545,500 | $613,700 |
| AMT exemption | $90,100 | $140,200 |
| AMT phaseout start (50% rate) | $500,000 | $1,000,000 |
| AMT 28% threshold | $244,500 | $244,500 |
| SALT cap / phaseout start | $40,400 / $505,000 | same |
| Non-itemizer charitable cap | $1,000 | $2,000 |
| HSA limit | $4,400 self-only | $8,750 family |

New rules in `forms_core_impl.py`, gated by config keys, so 2024/2025 are unchanged:
- `amt_phaseout_rate`: 0.50 (0.25 before 2026), on Form 6251 line 5 and the ShouldFill6251 worksheet.
- `charitable_nonitemizer_limit`: cash gifts deducted on top of the standard deduction.
  `Charitable` entries flagged `"DonorAdvisedFund": true` are excluded.
- `charitable_agi_floor_rate`: Schedule A line 14 reduced by 0.5% of AGI.
- `itemized_limitation_rate`: IRC 68 2/37 reduction of Schedule A line 17 (`ItemizedDeductionLimitation`
  worksheet). It does not apply for AMT, so Form 6251 subtracts it back.

## Provisional, revisit when published (usually December or January)

- **Field names.** `charitable_nonitemizer` (f1040) and `itemized_limitation_adjustment` (f6251) are
  placeholder keys, and `field_maps` is copied from 2025. Map them once the final 2026 PDFs are in
  `forms/2026/` and the `.fields` files exist. `trades_per_page_limit` is also the 2025 value.
- **ShouldFill6251 line 12** uses $244,500 (the Rev. Proc. 28% threshold). Check the 2026 1040 instructions.
- **NY / NYC.** All NY values and the rate/recapture/NYC schedules are 2025 copies
  (`computation_2026_ny* = computation_2025_ny*` in `forms_functions.py`). NY's FY2026 budget cut the
  lower brackets for 2026, so NY tax will be overstated for lower brackets until the real IT-201-I
  tables are in. NY treatment of the new federal charitable floor / IRC 68 is not known yet; IT-196
  keeps the 2025 logic.
