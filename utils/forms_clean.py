import os
import shutil
from utils.forms_constants import keys_extension, key_mapping_folder, \
    fields_mapping_folder, log_extension, json_extension, output_pdf_folder


def remove_by_extension(extension):
    for root, dirs, files in os.walk(os.getcwd()):
        for file in files:
            if file.endswith(extension):
                try:
                    os.remove(os.path.join(root, file))
                except PermissionError as e:
                    print(e)


def remove_folder(folder):
    shutil.rmtree(folder)


def clean(filing_year):
    # remove log files
    remove_by_extension(log_extension)  # log files are in use, haha
    # remove json files
    remove_by_extension(json_extension)
    # remove keys files
    remove_by_extension(keys_extension)

    # remove key_mapping folder
    year_keys_name = os.path.join(key_mapping_folder, filing_year)
    remove_folder(year_keys_name)
    # remove fields_mapping folder
    year_fields_name = os.path.join(fields_mapping_folder, filing_year)
    remove_folder(year_fields_name)
    # remove output folder
    output_year_folder = os.path.join(output_pdf_folder, filing_year)
    # remove_folder(output_year_folder)
    pass
