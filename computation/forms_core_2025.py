from computation.forms_functions import (
    computation_2025,
    computation_2025_ny,
    computation_2025_ny_recapture,
    computation_2025_nyc,
    computation_2025_mfj,
    computation_2025_ny_mfj,
    computation_2025_ny_recapture_mfj,
    computation_2025_nyc_mfj,
)
from computation.forms_core_impl import fill_taxes
from computation.form_worksheet_names import k_1040, k_1116, k_6251

CONFIG_2025 = dict(
    year='2025',
    computation=computation_2025,
    computation_ny=computation_2025_ny,
    computation_ny_recapture=computation_2025_ny_recapture,
    computation_nyc=computation_2025_nyc,
    standard_deduction=15_750,
    amt_exemption=88_100,
    # Form 6251 line 7: 26% up to $239,100, 28% above (i6251 instructions)
    amt_28pct_threshold=239_100,
    amt_28pct_excess=4_782,
    qualified_div_0pct=48_350,
    qualified_div_20pct=533_400,
    should_fill_6251_exemption=88_100,
    should_fill_6251_phaseout=626_350,
    salt_limit=40_000,
    salt_phaseout_start=500_000,
    salt_phaseout_rate=0.30,
    salt_floor=10_000,
    ny_standard_deduction=8_000,
    ny_itemized_deduction_threshold=340_700,
    mortgage_limit=750_000,
    ny_mortgage_limit=1_000_000,
    hsa_max_contribution=4_300,  # self-only
    hsa_max_contribution_family=8_550,
    capital_loss_limit=3_000,
    social_security_max_withholding=10_918.20,  # 6.2% of the $176,100 wage base, per person
    additional_medicare_threshold=200_000,
    niit_threshold=200_000,
    ny_itemized_adjustment_start=100_000,  # IT-196 line 46 worksheet 3 line 2
    nyc_school_fixed_credit=63,  # IT-201 line 69
    nyc_school_rate_reduction_threshold=12_000,  # IT-201 line 69a
    nyc_school_rate_reduction_base=21,
    # bracket boundaries, used by marginal_rates.py knots
    fed_brackets=[11_925, 48_475, 103_350, 197_300, 250_525, 626_350],
    ny_brackets=[8_500, 11_700, 13_900, 80_650, 215_400, 1_077_550, 5_000_000, 25_000_000],
    nyc_brackets=[12_000, 25_000, 50_000],
    ny_recapture_brackets=[215_400, 1_077_550, 5_000_000, 25_000_000],
    # filing-status-specific values; anything not listed falls back to the single value above
    # (SALT cap/phaseout/floor, AMT 28% threshold, mortgage limits are the same for single and MFJ)
    filing_status_overrides=dict(
        married_filing_jointly=dict(
            computation=computation_2025_mfj,
            computation_ny=computation_2025_ny_mfj,
            computation_ny_recapture=computation_2025_ny_recapture_mfj,
            computation_nyc=computation_2025_nyc_mfj,
            standard_deduction=31_500,
            amt_exemption=137_000,
            should_fill_6251_exemption=137_000,
            should_fill_6251_phaseout=1_252_700,
            qualified_div_0pct=96_700,
            qualified_div_20pct=600_050,
            additional_medicare_threshold=250_000,
            niit_threshold=250_000,
            overtime_deduction_max=25_000,
            tips_overtime_phaseout_start=300_000,
            car_loan_phaseout_start=200_000,
            senior_phaseout_start=150_000,
            ny_standard_deduction=16_050,
            ny_itemized_deduction_threshold=408_850,
            ny_itemized_adjustment_start=200_000,
            nyc_school_fixed_credit=125,
            nyc_school_rate_reduction_threshold=21_600,
            nyc_school_rate_reduction_base=37,
            fed_brackets=[23_850, 96_950, 206_700, 394_600, 501_050, 751_600],
            ny_brackets=[17_150, 23_600, 27_900, 161_550, 323_200, 2_155_350, 5_000_000, 25_000_000],
            nyc_brackets=[21_600, 45_000, 90_000],
            ny_recapture_brackets=[161_550, 323_200, 2_155_350, 5_000_000, 25_000_000],
        ),
    ),
    trades_per_page_limit=11,
    form_6251_line_1_split=True,
    # Schedule 1-A (2025-2028, OBBBA): amounts are fixed in the law, not inflation-adjusted
    schedule_1a=True,
    tips_deduction_max=25_000,
    overtime_deduction_max=12_500,  # $25,000 MFJ
    tips_overtime_phaseout_start=150_000,  # $300,000 MFJ, $100 per $1,000 over
    car_loan_interest_max=10_000,
    car_loan_phaseout_start=100_000,  # $200,000 MFJ, $200 per $1,000 (rounded up) over
    senior_deduction=6_000,  # per person
    senior_phaseout_start=75_000,  # $150,000 MFJ
    senior_phaseout_rate=0.06,
    senior_birth_cutoff='1961-01-02',  # born before this date (age 65 by year end)
    field_maps={
        k_1040: {
            '11': ('11_a', '11_b'),  # AGI is repeated as 11b at the top of page 2
            '12': '12_e',
            '13': '13_a',
            '7_n': None,  # removed in 2025
            '7_value': '7_a',
            '26': '26_value',
            '28': '28_value',
        },
        k_6251: {
            '1a_value': '1_a',  # 2025 split line 1 into 1a (line 14 - senior deduction) and 1b
            '1_value': '1_b',
            **{f'2{c}_value': f'2_{c}' for c in 'abcdefghijklmnopqrst'},
            **{f'{n}_value': str(n) for n in range(3, 12)},
        },
        k_1116: {
            'i_1a_source1': 'i_1a_source',  # 2024 has 3 source fields, 2025 merged to 1
        },
    },
)


def fill_taxes_2025(d):
    return fill_taxes(d, config=CONFIG_2025)
