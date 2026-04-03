from computation.forms_functions import (
    computation_2024,
    computation_2024_ny,
    computation_2024_ny_recapture,
    computation_2024_nyc,
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
)


def fill_taxes_2024(d):
    return fill_taxes(d, config=CONFIG_2024)
