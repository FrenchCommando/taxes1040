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
    amt_exemption=81_300,
    amt_28pct_threshold=220_700,
    amt_28pct_excess=4_414,
    qualified_div_0pct=47_025,
    qualified_div_20pct=518_900,
    should_fill_6251_exemption=81_300,
    should_fill_6251_phaseout=578_150,
    should_fill_6251_28pct=220_700,
)


def fill_taxes_2024(d):
    return fill_taxes(d, config=CONFIG_2024)
