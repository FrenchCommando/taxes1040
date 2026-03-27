# creates fields files to map values from unprocessed keys files
# the fields file then contains the names of the fields to be mapped
# with a clear syntax to describe tables and dollar/cents splits

import shutil
from utils.forms_utils import *

year_folder = "2019"


def build_keys(file, keys_name, keys_orig):
    # file is the "fields" file
    # keys_orig contains the original keys
    # key_name is the new keys file to be created and overridden
    with open(keys_name, "w+") as out:
        with open(file, 'r') as f:
            d = load_keys(keys_orig, out_dict=False)
            it = iter(d)
            try:
                for command in f:
                    if " " not in command:
                        # logger.error(command)
                        u = next(it)
                        # logger.error(u)
                        u = command.strip(), u[1], u[2]
                        out.write("\t\t".join(u) + "\n")
                    else:
                        c = command.strip().split(" ")
                        columns = c[1:]
                        for j in columns:
                            u = next(it)
                            n = c[0] + "_" + j
                            u = n, u[1], u[2]
                            out.write("\t\t".join(u) + "\n")
            except StopIteration as e:
                logger.error("Key iteration stopped %s %s %s", e, keys_name, file)


def process_fields(file):
    year_keys_name = os.path.join(key_mapping_folder, year_folder)
    year_fields_name = os.path.join(fields_mapping_folder, year_folder)

    keys_name = os.path.splitext(file)[0] + keys_extension
    keys_orig = os.path.join(year_keys_name, os.path.relpath(keys_name, year_fields_name))

    build_keys(file, keys_name, keys_orig)

    pdf_name = os.path.splitext(file)[0] + pdf_extension
    d = load_keys(keys_orig)
    try:
        d.update(load_keys(keys_name))
        logger.info("Loaded fields names from %s", keys_name)
    except FileNotFoundError as e:
        logger.error(e)
    for k, (v0, v1) in d.items():
        # if v1 == '/Tx':
        #     d[k] = ('yytt', v1)
        if v1 == '/Btn':
            d[k] = (True, v1)
    pdf_orig = os.path.join(year_keys_name, os.path.relpath(pdf_name, year_fields_name))
    fill_pdf_from_keys(file=pdf_orig, out_file=pdf_name, d={k: v[0] for k, v in d.items()})


def generate_keys_pdf():
    year_fields_name = os.path.join(fields_mapping_folder, year_folder)
    for u in glob.glob(os.path.join(year_fields_name, "*", "*")):
        if u.endswith(fields_extension):
            logger.info("Processing fields file %s", u)
            process_fields(u)


def move_keys_to_parent():
    year_fields_name = os.path.join(fields_mapping_folder, year_folder)
    forms_year_folder = os.path.join(forms_folder, year_folder)
    for u in glob.glob(os.path.join(year_fields_name, "*", "*")):
        if u.endswith(keys_extension):
            logger.info("Moving keys file %s", u)
            rel = os.path.relpath(u, year_fields_name)
            folder_path = os.path.join(forms_year_folder, rel)
            shutil.move(u, folder_path)
            logger.info("Moved  %s to %s", u, folder_path)


def main():
    map_folders(fields_mapping_folder, year_folder)
    generate_keys_pdf()
    move_keys_to_parent()  # moves the keys files when done


if __name__ == "__main__":
    year_folder = "2024"
    main()
