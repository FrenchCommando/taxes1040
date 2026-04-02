import os
import json

from utils.form_worksheet_names import k_it201
from utils.forms_constants import *
from utils.forms_utils import fill_pdf_from_keys, logging, process_logger, map_folders, load_keys, output_pdf_folder
from pdfrw import PdfReader, PdfWriter
from utils.forms_core_2023 import fill_taxes_2023
from utils.forms_core_2024 import fill_taxes_2024
from utils.forms_core_2025 import fill_taxes_2025


logger = logging.getLogger('fill_taxes')
process_logger(logger, file_name='fill_taxes')


def fill_pdfs(forms_state, forms_year_folder):
    map_folders(output_pdf_folder, forms_year_folder)
    form_year_folder = os.path.join(forms_folder, forms_year_folder)
    output_year_folder = os.path.join(output_pdf_folder, forms_year_folder)

    all_out_files = []
    for f, d_contents in forms_state.items():
        if f in [k_it201]:
            continue
        d_mapping = load_keys(os.path.join(form_year_folder, f + keys_extension))

        def fill_one_pdf(contents, suffix=""):
            ddd = {k: contents[val[0]] for k, val in d_mapping.items() if val[0] in contents}
            outfile = os.path.join(output_year_folder, f + suffix + pdf_extension)
            all_out_files.append(outfile)
            fill_pdf_from_keys(file=os.path.join(form_year_folder, f + pdf_extension),
                               out_file=outfile, d=ddd)
        if isinstance(d_contents, list):
            for i, one_content in enumerate(d_contents):
                fill_one_pdf(one_content, "_" + str(i))
        elif isinstance(d_contents, dict):
            fill_one_pdf(d_contents)
    return all_out_files


def merge_pdfs(files, out):
    writer = PdfWriter()
    for inpfn in files:
        writer.addpages(PdfReader(inpfn).pages)
    writer.write(out)


def save_json(data, out):
    with open(out, 'w+') as f:
        json.dump(data, f, indent=4)


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


def extract_carryover(forms_state):
    """Extract carryover values from a year's forms_state (for bridging legacy years)."""
    from utils.form_worksheet_names import k_1040, k_1040sd
    return {
        'taxable_income': forms_state[k_1040].get('15', 0),
        'schedule_d_net_short_term': forms_state.get(k_1040sd, {}).get('7', 0),
        'schedule_d_net_long_term': forms_state.get(k_1040sd, {}).get('15', 0),
        'schedule_d_loss_deduction': forms_state.get(k_1040sd, {}).get('21', 0),
    }


def process_year(year, states, worksheets, summary):
    save_json(data=states, out="data" + year + json_extension)
    save_json(data=worksheets, out="worksheet" + year + json_extension)
    save_json(data=summary, out="summary" + year + json_extension)
    pdf_files = fill_pdfs(states, year)
    merge_pdfs(pdf_files, "forms" + year + pdf_extension)


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
