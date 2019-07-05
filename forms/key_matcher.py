# for each of the pdf file
# design a routine to build the .keys file
# first run to retrieve the names of the annotation fields
# then generate a pdf file with fields filled with increasing integers
# .keys is generated automatically
# next: just need to replace integer values with names
# (using the fill_keys.py script)
from forms.forms_utils import *


def process_pdf(file):
    k_file = os.path.splitext(file)[0] + keys_extension
    if not os.path.isfile(k_file):
        d = {}
        d_type = {}  # /Tx for text /Btn for button
        i = 0
        template_pdf = pdfrw.PdfReader(file)
        for annotations in template_pdf.pages:
            for annotation in annotations[ANNOT_KEY]:
                if annotation[SUBTYPE_KEY] == WIDGET_SUBTYPE_KEY:
                    if annotation[ANNOT_FIELD_KEY]:
                        key = annotation[ANNOT_FIELD_KEY][1:-1]
                        fields_type = annotation[ANNOT_FIELD_TYPE_KEY]
                        d[key] = str(i)
                        d_type[key] = fields_type
                        i += 1

        k_file_map = os.path.join(key_mapping_folder, k_file)
        with open(k_file_map, 'w+') as f:
            logger.info("File created %s", k_file_map)
            for k, i in d.items():
                f.write(str(i) + "\t\t" + k + "\t\t" + d_type[k] + "\n")
    else:
        d = load_keys(k_file)
    out_file = os.path.join(key_mapping_folder, file)
    fill_pdf_from_keys(file=file, out_file=out_file, d=d)


def process_all():
    for u in glob.glob(os.path.join("*", "", "*")):
        if os.path.splitext(u)[1] == pdf_extension:
            logger.info("Processing file %s", u)
            try:
                process_pdf(u)
            except Exception as e:
                logger.error(e)
        else:
            logger.info("File ignored %s", u)
    # for u in glob.glob(os.path.join(key_mapping_folder, "*", "")):
    #     logger.info("File exists %s", u)


if __name__ == "__main__":
    map_folders(key_mapping_folder)
    process_all()
