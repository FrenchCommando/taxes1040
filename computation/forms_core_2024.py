from computation.forms_functions import (
    computation_2024,
    computation_2024_ny,
    computation_2024_ny_recapture,
    computation_2024_nyc,
    computation_2024_mfj,
    computation_2024_ny_mfj,
    computation_2024_ny_recapture_mfj,
    computation_2024_nyc_mfj,
)
from computation.forms_core_impl import fill_taxes

CONFIG_2024 = dict(
    year='2024',
    computation=computation_2024,
    computation_ny=computation_2024_ny,
    computation_ny_recapture=computation_2024_ny_recapture,
    computation_nyc=computation_2024_nyc,
    standard_deduction=14_600,
    amt_exemption=85_700,
    amt_28pct_threshold=232_600,
    amt_28pct_excess=4_652,
    qualified_div_0pct=47_025,
    qualified_div_20pct=518_900,
    should_fill_6251_exemption=85_700,
    should_fill_6251_phaseout=609_350,
    should_fill_6251_28pct=232_600,
    trades_per_page_limit=14,
    salt_limit=10_000,
    salt_phaseout_start=500_000,
    salt_phaseout_rate=0.30,
    salt_floor=10_000,
    ny_standard_deduction=8_000,
    ny_itemized_deduction_threshold=330_200,
    mortgage_limit=750_000,
    ny_mortgage_limit=1_000_000,
    hsa_max_contribution=4_150,  # self-only
    hsa_max_contribution_family=8_300,
    capital_loss_limit=3_000,
    additional_medicare_threshold=200_000,
    niit_threshold=200_000,
    ny_itemized_adjustment_start=100_000,  # IT-196 line 46 worksheet 3 line 2
    nyc_school_fixed_credit=63,  # IT-201 line 69
    nyc_school_rate_reduction_threshold=12_000,  # IT-201 line 69a
    nyc_school_rate_reduction_base=21,
    # bracket boundaries, used by marginal_rates.py knots
    fed_brackets=[11_600, 47_150, 100_525, 191_950, 243_725, 609_350],
    ny_brackets=[8_500, 11_700, 13_900, 80_650, 215_400, 1_077_550, 5_000_000, 25_000_000],
    nyc_brackets=[12_000, 25_000, 50_000],
    ny_recapture_brackets=[215_400, 1_077_550, 5_000_000, 25_000_000],
    # filing-status-specific values; anything not listed falls back to the single value above
    # (SALT cap/phaseout/floor, AMT 28% threshold, mortgage limits are the same for single and MFJ)
    filing_status_overrides=dict(
        married_filing_jointly=dict(
            computation=computation_2024_mfj,
            computation_ny=computation_2024_ny_mfj,
            computation_ny_recapture=computation_2024_ny_recapture_mfj,
            computation_nyc=computation_2024_nyc_mfj,
            standard_deduction=29_200,
            amt_exemption=133_300,
            should_fill_6251_exemption=133_300,
            should_fill_6251_phaseout=1_218_700,
            qualified_div_0pct=94_050,
            qualified_div_20pct=583_750,
            additional_medicare_threshold=250_000,
            niit_threshold=250_000,
            ny_standard_deduction=16_050,
            ny_itemized_deduction_threshold=396_250,
            ny_itemized_adjustment_start=200_000,
            nyc_school_fixed_credit=125,
            nyc_school_rate_reduction_threshold=21_600,
            nyc_school_rate_reduction_base=37,
            fed_brackets=[23_200, 94_300, 201_050, 383_900, 487_450, 731_200],
            ny_brackets=[17_150, 23_600, 27_900, 161_550, 323_200, 2_155_350, 5_000_000, 25_000_000],
            nyc_brackets=[21_600, 45_000, 90_000],
            ny_recapture_brackets=[161_550, 323_200, 2_155_350, 5_000_000, 25_000_000],
        ),
    ),
)


def fill_taxes_2024(d):
    return fill_taxes(d, config=CONFIG_2024)
