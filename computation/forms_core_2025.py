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
    # 1040 ShouldFill6251 worksheet line 12: screening threshold, intentionally lower than amt_28pct_threshold
    should_fill_6251_28pct=232_600,
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
    field_maps={
        k_1040: {
            '11': '11_a',
            '12': '12_e',
            '13': '13_a',
            '7_n': None,  # removed in 2025
            '7_value': '7_a',
            '26': '26_value',
            '28': '28_value',
        },
        k_6251: {
            '1_value': '1_a',
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
