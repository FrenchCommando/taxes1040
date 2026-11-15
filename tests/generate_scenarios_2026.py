"""Generate 2026 test scenario input files and their expected outputs.

PROVISIONAL year: federal amounts are final (Rev. Proc. 2025-32 / 2025-19), but NY/NYC values are
2025 placeholders and field names follow the 2025 forms. See forms/2026/notes.md.

Reuses scenario inputs from generate_scenarios_2025.py (dates inside inputs are cosmetic) and adds
scenarios for the 2026 law changes.

Scenarios:
    w2_only                     - single filer, W2 wages only
    itemized_wins               - single filer, itemized deductions beat standard deduction
    amt_exemption_phaseout      - AMT exemption phased out at 50% above $500k (was 25% above $626k)
    high_income_ny              - AGI > $640,600: IRC 68 limitation, 0.5% charitable floor, AMT add-back
    hsa_contribution            - HSA self-only ($4,400 limit in 2026)
    mfj_two_w2                  - married filing jointly, one W2 each, standard deduction
    mfj_high_income             - MFJ: Additional Medicare Tax, NIIT, itemized, 0.5% charitable floor
    mfj_hsa_family              - MFJ HSA family coverage limit ($8,750 in 2026)
    mfj_capital_loss            - MFJ capital loss limited to $3,000
    excess_social_security / mfj_excess_social_security - Schedule 3 line 11 at this year's max
    hsa_nonmedical_distribution - HSA income + 20% additional tax (Schedule 2 line 17c)
    amt_owed / amt_foreign_tax_credit - AMT owed, with and without foreign tax credit
    schedule_1a_* / mfj_schedule_1a_seniors - Schedule 1-A deductions (2026 senior cutoff 1962-01-02)
    charitable_nonitemizer      - single, standard deduction + cash gifts ($1,000 cap, DAF excluded)
    mfj_charitable_nonitemizer  - MFJ, standard deduction + cash gifts ($2,000 cap)

Run: python tests/generate_scenarios_2026.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.test_computation import load_scenario_input
from tests.generate_scenarios_2025 import SCENARIOS as SCENARIOS_2025, BASE_W2, MFJ, SPOUSE_W2
from computation.forms_core_2026 import fill_taxes_2026

SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), 'scenarios', '2026')

SCENARIO_NAMES = [
    'w2_only',
    'itemized_wins',
    'amt_exemption_phaseout',
    'high_income_ny',
    'mfj_two_w2',
    'mfj_high_income',
    'excess_social_security',
    'mfj_excess_social_security',
    'hsa_nonmedical_distribution',
    'amt_owed',
    'amt_foreign_tax_credit',
    'schedule_1a_tips_overtime',
    'schedule_1a_phaseout',
    'mfj_schedule_1a_seniors',
    'mfj_capital_loss',
]

SCENARIOS = {name: SCENARIOS_2025[name] for name in SCENARIO_NAMES}
SCENARIOS['hsa_contribution'] = {
    **SCENARIOS_2025['hsa_contribution'],
    'health_savings_account_contributions': 4400,  # 2026 self-only limit (2025 scenario uses its $4,300)
}
SCENARIOS['mfj_hsa_family'] = {
    **SCENARIOS_2025['mfj_hsa_family'],
    'health_savings_account_contributions': 7750,  # $8,750 family limit - $1,000 employer
}
SCENARIOS['charitable_nonitemizer'] = {
    # $1,500 of cash gifts, $600 of it to a donor-advised fund: deduction is min($900, $1,000)
    "W2": [BASE_W2],
    "Charitable": [
        {"Entity": "Red Cross", "Amount": 900},
        {"Entity": "Brokerage Charitable Fund", "Amount": 600, "DonorAdvisedFund": True},
    ],
}
SCENARIOS['mfj_charitable_nonitemizer'] = {
    # $3,000 of cash gifts, capped at $2,000 for MFJ
    **MFJ,
    "W2": [BASE_W2, SPOUSE_W2],
    "Charitable": [{"Entity": "Red Cross", "Amount": 3000}],
}


def generate_all():
    for name, input_data in SCENARIOS.items():
        scenario_dir = os.path.join(SCENARIOS_DIR, name)
        os.makedirs(scenario_dir, exist_ok=True)

        with open(os.path.join(scenario_dir, 'input.json'), 'w') as f:
            json.dump(input_data, f, indent=4)

        data = load_scenario_input(scenario_dir)
        states, worksheets, summary, carryover = fill_taxes_2026(d=data)
        for out_name, out_data in [('data', states), ('worksheets', worksheets),
                                   ('summary', summary), ('carryover', carryover)]:
            with open(os.path.join(scenario_dir, f'{out_name}.json'), 'w') as f:
                json.dump(out_data, f, indent=4)

        print(f'Generated: {name}')


if __name__ == '__main__':
    generate_all()
