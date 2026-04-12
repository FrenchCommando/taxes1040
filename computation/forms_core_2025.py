from computation.forms_functions import (
    computation_2025,
    computation_2025_ny,
    computation_2025_ny_recapture,
    computation_2025_nyc,
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
