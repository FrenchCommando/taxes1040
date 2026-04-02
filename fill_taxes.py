import os
import json

from utils.forms_constants import override_keyword, json_extension
from utils.forms_core_impl import extract_carryover
from utils.forms_core_2023 import fill_taxes_2023
from utils.forms_core_2024 import fill_taxes_2024
from utils.forms_core_2025 import fill_taxes_2025


def gather_inputs(input_year_folder):
    input_folder = os.path.join("input_data", input_year_folder)
    with open(os.path.join(input_folder, 'input.json'), 'rb') as file_reader:
        j = json.load(file_reader)

    additional_info = {
        'single': True,  # if you're not single too bad for you
        'dependents': False,  # same if you have dependents
        'occupation': "Analyst",
        'full_year_health_coverage_or_exempt': True,  # ignored starting 2019
        'presidential_election_self': False,
        'resident': True,  # if you're not it's not done yet
        'scheduleD': True,
        'checking': True,
        'routing_number': "11111111",
        'account_number': "444444444",
        # 'foreign_account': 'FRANCE',
        'phone': '6465555555',
        'email': 'martialren@gmail.com',
        'health_savings_account': False,
        'health_savings_account_contributions': 0,
        'health_savings_account_employer_contributions': 0,
        'health_savings_account_distributions': 0,
        'medical_expenses': 0,
        'virtual_currency': False,
    }

    override_stuff = {
        'address_street_and_number': next(iter(j['W2']))['Address'],
        'address_apt': next(iter(j['W2']))['Address_apt'],
        'address_city': next(iter(j['W2']))['Address_city'],
        'address_state': next(iter(j['W2']))['Address_state'],
        'address_zip': next(iter(j['W2']))['Address_zip'],
        'ssn': '200112222'
    }

    data = {}
    data.update(j)
    data.update(additional_info)
    data[override_keyword] = override_stuff

    if '1099' not in data:
        data['1099'] = []
    data['1099'].extend(
        [
            # for banks that give you a 1099-INT (but you didn't bother include the file)
            # {"Institution": "JPMORGAN CHASE BANK NA", "Interest": 3.11},
            # {"Institution": "JPMORGAN CHASE BANK NA", "Interest": 10.29},
        ]
    )

    return data


def save_json(data, out):
    with open(out, 'w+') as f:
        json.dump(data, f, indent=4)


def process_year(year, states, worksheets, summary):
    save_json(data=states, out="data" + year + json_extension)
    save_json(data=worksheets, out="worksheet" + year + json_extension)
    save_json(data=summary, out="summary" + year + json_extension)


def main():
    # 2023 — frozen legacy interface
    data2023 = gather_inputs(input_year_folder="2023")
    states2023, worksheets_2023, summary_2023 = fill_taxes_2023(d=data2023, output_2022=None)
    process_year("2023", states2023, worksheets_2023, summary_2023)

    # 2024+ — Markovian interface (carryover passed via d['prior_year'])
    data2024 = gather_inputs(input_year_folder="2024")
    data2024['prior_year'] = extract_carryover(states2023)
    states2024, worksheets_2024, summary_2024, carryover_2024 = fill_taxes_2024(d=data2024)
    process_year("2024", states2024, worksheets_2024, summary_2024)

    data2025 = gather_inputs(input_year_folder="2025")
    data2025['prior_year'] = carryover_2024
    states2025, worksheets_2025, summary_2025, carryover_2025 = fill_taxes_2025(d=data2025)
    process_year("2025", states2025, worksheets_2025, summary_2025)


if __name__ == "__main__":
    main()
