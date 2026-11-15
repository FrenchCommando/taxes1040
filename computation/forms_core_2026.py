"""2026 tax year config.

Federal amounts: Rev. Proc. 2025-32 (2026 inflation adjustments, incl. OBBBA amendments),
HSA limits: Rev. Proc. 2025-19, SALT cap/threshold: IRC 164(b)(7) as amended by OBBBA.
New 2026 law (OBBBA): AMT exemption phaseout at 50% from $500k/$1M, non-itemizer charitable
deduction (IRC 170(p)), 0.5% AGI floor on itemized charitable gifts (IRC 170(b)(1)(I)),
itemized deduction limitation for the 37% bracket (IRC 68, 2/37 reduction).

PROVISIONAL: the 2026 forms and instructions are not final, so field names and field_maps are
the 2025 ones, and NY/NYC values are 2025 placeholders. See forms/2026/notes.md.
"""
from computation.forms_functions import (
    computation_2026,
    computation_2026_ny,
    computation_2026_ny_recapture,
    computation_2026_nyc,
    computation_2026_mfj,
    computation_2026_ny_mfj,
    computation_2026_ny_recapture_mfj,
    computation_2026_nyc_mfj,
)
from computation.forms_core_impl import fill_taxes
from computation.forms_core_2025 import CONFIG_2025

CONFIG_2026 = dict(
    year='2026',
    computation=computation_2026,
    computation_ny=computation_2026_ny,
    computation_ny_recapture=computation_2026_ny_recapture,
    computation_nyc=computation_2026_nyc,
    standard_deduction=16_100,
    amt_exemption=90_100,
    # Form 6251 line 7: 26% up to $244,500, 28% above (Rev. Proc. 2025-32 4.10)
    amt_28pct_threshold=244_500,
    amt_28pct_excess=4_890,  # 2% of 244,500
    # OBBBA: exemption reduced by 50% (was 25%) of AMTI over the phaseout start
    amt_phaseout_rate=0.50,
    qualified_div_0pct=49_450,
    qualified_div_20pct=545_500,
    should_fill_6251_exemption=90_100,
    should_fill_6251_phaseout=500_000,  # not inflation-adjusted before 2027 for MFJ ($1M)
    # 1040 ShouldFill6251 worksheet line 12: 2026 instructions not out, using the 28% threshold
    should_fill_6251_28pct=244_500,
    salt_limit=40_400,  # 101% of 2025
    salt_phaseout_start=505_000,  # 101% of 2025
    salt_phaseout_rate=0.30,
    salt_floor=10_000,
    # non-itemizer cash charitable deduction (not to donor-advised funds), $2,000 MFJ
    charitable_nonitemizer_limit=1_000,
    # itemized cash charitable gifts are reduced by 0.5% of AGI
    charitable_agi_floor_rate=0.005,
    # itemized deductions reduced by 2/37 of the lesser of itemized deductions
    # or (taxable income + itemized deductions) above the 37% bracket start (fed_brackets[-1])
    itemized_limitation_rate=2 / 37,
    mortgage_limit=750_000,
    ny_mortgage_limit=1_000_000,
    hsa_max_contribution=4_400,  # self-only
    hsa_max_contribution_family=8_750,
    capital_loss_limit=3_000,
    social_security_max_withholding=11_439.00,  # 6.2% of the $184,500 wage base (Pub 15 2026), per person
    additional_medicare_threshold=200_000,
    niit_threshold=200_000,
    # NY / NYC: PROVISIONAL 2025 values until the 2026 IT-201-I / IT-196-I are published
    ny_standard_deduction=8_000,
    ny_itemized_deduction_threshold=340_700,
    ny_itemized_adjustment_start=100_000,
    nyc_school_fixed_credit=63,
    nyc_school_rate_reduction_threshold=12_000,
    nyc_school_rate_reduction_base=21,
    # bracket boundaries, used by marginal_rates.py knots and the IRC 68 limitation
    fed_brackets=[12_400, 50_400, 105_700, 201_775, 256_225, 640_600],
    ny_brackets=[8_500, 11_700, 13_900, 80_650, 215_400, 1_077_550, 5_000_000, 25_000_000],
    nyc_brackets=[12_000, 25_000, 50_000],
    ny_recapture_brackets=[215_400, 1_077_550, 5_000_000, 25_000_000],
    filing_status_overrides=dict(
        married_filing_jointly=dict(
            computation=computation_2026_mfj,
            computation_ny=computation_2026_ny_mfj,
            computation_ny_recapture=computation_2026_ny_recapture_mfj,
            computation_nyc=computation_2026_nyc_mfj,
            standard_deduction=32_200,
            amt_exemption=140_200,
            should_fill_6251_exemption=140_200,
            should_fill_6251_phaseout=1_000_000,
            qualified_div_0pct=98_900,
            qualified_div_20pct=613_700,
            charitable_nonitemizer_limit=2_000,
            additional_medicare_threshold=250_000,
            niit_threshold=250_000,
            # NY / NYC: PROVISIONAL 2025 values
            ny_standard_deduction=16_050,
            ny_itemized_deduction_threshold=408_850,
            ny_itemized_adjustment_start=200_000,
            nyc_school_fixed_credit=125,
            nyc_school_rate_reduction_threshold=21_600,
            nyc_school_rate_reduction_base=37,
            fed_brackets=[24_800, 100_800, 211_400, 403_550, 512_450, 768_700],
            ny_brackets=[17_150, 23_600, 27_900, 161_550, 323_200, 2_155_350, 5_000_000, 25_000_000],
            nyc_brackets=[21_600, 45_000, 90_000],
            ny_recapture_brackets=[161_550, 323_200, 2_155_350, 5_000_000, 25_000_000],
        ),
    ),
    trades_per_page_limit=11,  # 2025 value, recheck on the final 2026 f8949
    # PROVISIONAL: 2025 layout until the final 2026 PDFs are mapped
    field_maps=CONFIG_2025['field_maps'],
)


def fill_taxes_2026(d):
    return fill_taxes(d, config=CONFIG_2026)
