# creates fields files to map values from unprocessed keys files
# the fields file then contains the names of the fields to be mapped
# with a clear syntax to describe tables and dollar/cents splits

from utils.forms_utils import *


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
    first_last_ssn = " first_name_initial last_name ssn"
    standard_deduction = " can_be_claimed_as_dependent_y" \
                         " born_before_19540102_y" \
                         " blind"
    dependents = " first_last" \
                 " ssn" \
                 " relationship" \
                 " child_tax_credit" \
                 " credit_for_other_dependent"
    occupation_pin = " occupation identity_protection_pin"
    yes_no = " y n"
    proceeds_columns = " proceeds cost adjustments gain"
    dollar_cents = " dollar cents"
    payer_dollar_cents = " payer" + dollar_cents
    trade = " proceeds cost code adjustment gain"
    full_trade = " description date_acq date_sold" + trade
    for u in glob.glob(os.path.join(fields_mapping_folder, "*", "*" + fields_extension)):
        logger.info("Filling fields %s", u)
        with open(u, 'w') as f:
            if "f1040." in u:
                f.write("single\n")
                f.write("married_filling_jointly\n")
                f.write("married_filling_separately\n")
                f.write("head_of_household\n")
                f.write("qualifying_widower\n")
                f.write("qualifying_widower_name\n")
                f.write("self" + first_last_ssn + "\n")
                f.write("self" + standard_deduction + "\n")
                f.write("spouse" + first_last_ssn + "\n")
                f.write("spouse" + standard_deduction + "\n")  # check order for accuracy
                f.write("spouse_itemizes_on_separate_or_dual_status_alien\n")
                f.write("address\n")
                f.write("apt\n")
                f.write("city_state_zip\n")
                f.write("full_year_health_coverage_or_exempt\n")
                f.write("presidential_election self spouse\n")
                f.write("more_than_four_dependents\n")
                for i in range(1, 5):
                    f.write("dependent_" + str(i) + dependents + "\n")
                f.write("self" + occupation_pin + "\n")
                f.write("spouse" + occupation_pin + "\n")
                f.write("preparer_name\n")
                f.write("ptin\n")
                f.write("firm_ein\n")
                f.write("firm_name\n")
                f.write("firm_phone\n")
                f.write("third_party_designee\n")
                f.write("self_employed\n")
                f.write("firm_address\n")

                lines = ['1']
                for i in range(2, 6):
                    for j in range(2):
                        lines.append(str(i) + chr(ord('a') + j))
                for l in lines:
                    f.write(l + dollar_cents + "\n")
                f.write("6_from_s1_22\n")
                for i in range(6, 11):
                    f.write(str(i) + dollar_cents + "\n")
                f.write("11a tax 1 2 3 3_value\n")
                f.write("11b\n")
                f.write("11" + dollar_cents + "\n")
                f.write("12a\n")
                f.write("12b\n")
                for i in range(12, 17):
                    f.write(str(i) + dollar_cents + "\n")
                f.write("17a\n")
                f.write("17b\n")
                f.write("17c\n")
                f.write("17_from_5\n")
                for i in range(17, 20):
                    f.write(str(i) + dollar_cents + "\n")
                f.write("20a 8888" + dollar_cents + "\n")
                f.write("20b\n")
                f.write("20c checking savings\n")
                f.write("20d\n")
                for i in range(21, 24):
                    f.write(str(i) + dollar_cents + "\n")
            elif "f1040s1" in u:
                f.write("name\n")
                f.write("ssn\n")

                f.write("1_9b" + dollar_cents + "\n")
                for i in range(10, 13):
                    f.write(str(i) + dollar_cents + "\n")
                f.write("13_not_d\n")
                for i in range(13, 21):
                    f.write(str(i) + dollar_cents + "\n")
                f.write("21_type\n")
                for i in range(21, 31):
                    f.write(str(i) + dollar_cents + "\n")
                f.write("31b\n")
                f.write("31a" + dollar_cents + "\n")
                for i in range(32, 37):
                    f.write(str(i) + dollar_cents + "\n")
            elif "f1040s3" in u:
                f.write("name\n")
                f.write("ssn\n")
                for i in range(48, 54):
                    f.write(str(i) + dollar_cents + "\n")
                f.write("54 a b c c_value\n")
                for i in range(54, 56):
                    f.write(str(i) + dollar_cents + "\n")
            elif "f1040sb" in u:
                f.write("name\n")
                f.write("ssn\n")
                for i in range(1, 15):
                    f.write("1_" + str(i) + payer_dollar_cents + "\n")
                for i in range(2, 5):
                    f.write(str(i) + dollar_cents + "\n")
                for i in range(1, 17):
                    f.write("5_" + str(i) + payer_dollar_cents + "\n")
                f.write("6" + dollar_cents + "\n")
                for i in ["7a", "7a_yes"]:
                    f.write(i + yes_no + "\n")
                f.write("7b\n")
                f.write("8" + yes_no + "\n")
            elif "f1040sd" in u:
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
                f.write("long" + " d e f" + "\n")
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
    fill_pdf_from_keys(file=pdf_orig, out_file=pdf_name, d={k: v[0] for k, v in d.items()})


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
            folder_path = os.path.join(forms_folder, rel)
            try:
                os.rename(u, folder_path)
                logger.info("Moved  %s to %s", u, folder_path)
            except FileExistsError as e:
                logger.error("Already Exists - Not Moved  %s to %s", u, folder_path)


def main():
    map_folders(fields_mapping_folder)
    create_empty_fields()
    fill_fields_files()  # run after defining the fields files
    generate_keys_pdf()
    move_keys_to_parent()  # moves the keys files when done


if __name__ == "__main__":
    main()
