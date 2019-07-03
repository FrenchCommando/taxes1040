# creates fields files to map values from unprocessed keys files
# the fields file then contains the names of the fields to be mapped
# with a clear syntax to describe tables and dollar/cents splits

from forms.forms_utils import *


def create_empty_fields():
    for u in glob.glob(os.path.join(key_mapping_folder, "*", "*")):
        if u.endswith(keys_extension):
            rel = os.path.relpath(u, key_mapping_folder)
            rel_fields = os.path.join(fields_mapping_folder, rel)
            fields_name = os.path.splitext(rel_fields)[0] + fields_extension
            try:
                open(fields_name, 'x')
                logger.info("Created fields file for %s", fields_name)
            except FileExistsError as e:
                logger.debug("Creating fields file for %s -- %s", fields_name, e)
        else:
            logger.info("File ignored %s", u)


def fill_fields_files():
    yes_no = " y n"
    proceeds_columns = " proceeds cost adjustments gain"
    dollar_cents = " dollar cents"
    trade = " proceeds cost code adjustment gain"
    full_trade = " description date_acq date_sold" + trade
    for u in glob.glob(os.path.join(fields_mapping_folder, "*", "*" + fields_extension)):
        logger.info("Filling fields %s", u)
        with open(u, 'w') as f:
            if "f1040sd" in u:
                f.write("name\n")
                f.write("ssn\n")
                for i in ['1a', '1b', '2', '3']:
                    f.write(i + proceeds_columns + "\n")
                for i in range(4, 8):
                    f.write(str(i) + "\n")
                for i in ['8a', '8b', '9', '10']:
                    f.write(i + proceeds_columns + "\n")
                for i in range(11, 17):
                    f.write(str(i) + "\n")
                f.write("17" + yes_no + "\n")
                for i in range(18, 20):
                    f.write(str(i) + "\n")
                f.write("20" + yes_no + "\n")
                f.write("21\n")
                f.write("22" + yes_no + "\n")
            elif "f6251" in u:
                f.write("name\n")
                f.write("ssn\n")
                lines = ['1']
                for i in range(20):
                    lines.append("2" + chr(ord('a') + i))
                for i in range(3, 41):
                    lines.append(str(i))
                for l in lines:
                    f.write(l + dollar_cents + "\n")
            elif "f8949" in u:
                f.write("I_name\n")
                f.write("I_ssn\n")
                f.write("short" + " a b c" + "\n")
                for i in range(14):
                    f.write("I_1_" + str(i + 1) + full_trade + "\n")
                f.write("I_2" + trade + "\n")
                f.write("II_name\n")
                f.write("II_ssn\n")
                f.write("short" + " d e f" + "\n")
                for i in range(14):
                    f.write("II_1_" + str(i + 1) + full_trade + "\n")
                f.write("II_2" + trade + "\n")
            else:
                logger.error("Fields File not defined %s", u)


def build_keys(file, keys_name, keys_orig):
    # file is the "fields" file
    # keys_orig contains the original keys
    # key_name is the new keys file to be created and overridden
    with open(keys_name, "w+") as out:
        with open(file, 'r') as f:
            d = load_keys(keys_orig, out_dict=False)
            it = iter(d)
            for command in f:
                if " " not in command:
                    u = next(it)
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


def process_fields(file):
    keys_name = os.path.splitext(file)[0] + keys_extension
    keys_orig = os.path.join(key_mapping_folder, os.path.relpath(keys_name, fields_mapping_folder))

    build_keys(file, keys_name, keys_orig)

    pdf_name = os.path.splitext(file)[0] + pdf_extension
    d = load_keys(keys_orig)
    try:
        d.update(load_keys(keys_name))
        logger.info("Loaded fields names from %s", keys_name)
    except FileNotFoundError as e:
        logger.error(e)
    pdf_orig = os.path.join(key_mapping_folder, os.path.relpath(pdf_name, fields_mapping_folder))
    fill_pdf_from_keys(file=pdf_orig, out_file=pdf_name, d=d)


def generate_keys_pdf():
    for u in glob.glob(os.path.join(fields_mapping_folder, "*", "*")):
        if u.endswith(fields_extension):
            logger.info("Processing fields file %s", u)
            process_fields(u)


def move_keys_to_parent():
    for u in glob.glob(os.path.join(fields_mapping_folder, "*", "*")):
        if u.endswith(keys_extension):
            logger.info("Moving keys file %s", u)
            rel = os.path.relpath(u, fields_mapping_folder)
            try:
                os.rename(u, rel)
                logger.info("Moved  %s to %s", u, rel)
            except FileExistsError as e:
                logger.error("Already Exists - Not Moved  %s to %s", u, rel)


if __name__ == "__main__":
    map_folders(fields_mapping_folder)
    create_empty_fields()
    fill_fields_files()  # run after defining the fields files
    generate_keys_pdf()
    move_keys_to_parent()  # moves the keys files when done
