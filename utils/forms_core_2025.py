from utils.forms_functions import (
    computation_2025,
    computation_2025_ny,
    computation_2025_ny_recapture,
    computation_2025_nyc,
)
from utils.forms_core_impl import fill_taxes

CONFIG_2025 = dict(
    year='2025',
    computation=computation_2025,
    computation_ny=computation_2025_ny,
    computation_ny_recapture=computation_2025_ny_recapture,
    computation_nyc=computation_2025_nyc,
    standard_deduction=15_000,
    amt_exemption=88_100,
    amt_28pct_threshold=232_600,
    amt_28pct_excess=4_652,
    qualified_div_0pct=48_350,
    qualified_div_20pct=533_400,
    should_fill_6251_exemption=88_100,
    should_fill_6251_phaseout=626_350,
    should_fill_6251_28pct=232_600,
)


def fill_taxes_2025(d, output_2024=None):
    return fill_taxes(d, output_prev=output_2024, config=CONFIG_2025)
