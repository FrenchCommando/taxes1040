"""Generate 2024 test scenario input files and their expected outputs.

Reuses the scenario inputs from generate_scenarios_2025.py (dates inside inputs are cosmetic)
and runs them through the 2024 computation. Covers single vs married filing jointly.

Scenarios:
    w2_only          - single filer, W2 wages only
    itemized_wins    - single filer, itemized deductions beat standard deduction
    mfj_two_w2       - married filing jointly, one W2 each, standard deduction
    mfj_high_income  - MFJ: Additional Medicare Tax, NIIT, itemized, NY recapture
    mfj_hsa_family   - MFJ HSA family coverage limit ($8,300 in 2024)
    mfj_capital_loss - MFJ capital loss limited to $3,000

Run: python tests/generate_scenarios_2024.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.test_computation import load_scenario_input
from tests.generate_scenarios_2025 import SCENARIOS as SCENARIOS_2025
from computation.forms_core_2024 import fill_taxes_2024

SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), 'scenarios', '2024')

SCENARIO_NAMES = [
    'w2_only',
    'itemized_wins',
    'mfj_two_w2',
    'mfj_high_income',
    'mfj_capital_loss',
]

SCENARIOS = {name: SCENARIOS_2025[name] for name in SCENARIO_NAMES}
SCENARIOS['mfj_hsa_family'] = {
    **SCENARIOS_2025['mfj_hsa_family'],
    'health_savings_account_contributions': 7300,  # $8,300 family limit - $1,000 employer
}


def generate_all():
    for name, input_data in SCENARIOS.items():
        scenario_dir = os.path.join(SCENARIOS_DIR, name)
        os.makedirs(scenario_dir, exist_ok=True)

        with open(os.path.join(scenario_dir, 'input.json'), 'w') as f:
            json.dump(input_data, f, indent=4)

        data = load_scenario_input(scenario_dir)
        states, worksheets, summary, carryover = fill_taxes_2024(d=data)
        for out_name, out_data in [('data', states), ('worksheets', worksheets),
                                   ('summary', summary), ('carryover', carryover)]:
            with open(os.path.join(scenario_dir, f'{out_name}.json'), 'w') as f:
                json.dump(out_data, f, indent=4)

        print(f'Generated: {name}')


if __name__ == '__main__':
    generate_all()
