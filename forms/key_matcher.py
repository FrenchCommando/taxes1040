# for each of the pdf file
# design a routine to build the .keys file
# first run to retrieve the names of the annotation fields
# then generate a pdf file with fields filled with increasing integers
# .keys is generated automatically
# just need to replace integer values with names

import os
import glob
import re
import pdfrw
import logging
from utils.logger import process_logger


logger = logging.getLogger('key_matching')
process_logger(logger, file_name='key_matching')


key_mapping_folder = 'key_mapping'


ANNOT_KEY = '/Annots'
ANNOT_FIELD_KEY = '/T'
ANNOT_VAL_KEY = '/V'
ANNOT_RECT_KEY = '/Rect'
SUBTYPE_KEY = '/Subtype'
WIDGET_SUBTYPE_KEY = '/Widget'


def create_folders():
    if not os.path.isdir(key_mapping_folder):
        os.mkdir(key_mapping_folder)

    for u in glob.glob(os.path.join("*", "")):
        if key_mapping_folder not in u:
            u_path = os.path.join(key_mapping_folder, u)
            if not os.path.isdir(u_path):
                os.mkdir(u_path)
                logger.info("Folders created %s", u_path)
    logger.info("Folders created - Done")


def process_pdf(file):
    template_pdf = pdfrw.PdfReader(file)
    d = {}
    i = 0
    for annotations in template_pdf.pages:
        for annotation in annotations[ANNOT_KEY]:
            if annotation[SUBTYPE_KEY] == WIDGET_SUBTYPE_KEY:
                if annotation[ANNOT_FIELD_KEY]:
                    key = annotation[ANNOT_FIELD_KEY][1:-1]
                    # print(key)
                    d[key] = str(i)
                    i += 1

    k_file = file[:-4] + ".keys"
    k_file_map = os.path.join(key_mapping_folder, file[:-4] + ".keys")
    if not os.path.isfile(k_file):
        with open(k_file_map, 'w+') as f:
            logger.info("File created %s", k_file_map)
            for k, i in d.items():
                f.write(str(i) + "\t\t" + k + "\n")
    else:
        d = {}
        with open(k_file, 'r') as f:
            logger.info("Loading keys from %s", k_file)
            for l in f:
                if l[0] == '#':
                    continue
                s = re.split(r'\W+', l)
                d[s[1]] = s[0]
    for annotations in template_pdf.pages:
        for annotation in annotations[ANNOT_KEY]:
            if annotation[SUBTYPE_KEY] == WIDGET_SUBTYPE_KEY:
                if annotation[ANNOT_FIELD_KEY]:
                    key = annotation[ANNOT_FIELD_KEY][1:-1]
                    if key in d.keys():
                        annotation.update(
                            pdfrw.PdfDict(V='{}'.format(d[key]))
                        )
    out_file = os.path.join(key_mapping_folder, file)
    logger.info("Exporting PDF file %s", out_file)
    pdfrw.PdfWriter().write(out_file, template_pdf)


def process_all():
    for u in glob.glob(os.path.join("*", "", "*")):
        if u.endswith("pdf"):
            logger.info("Processing file %s", u)
            process_pdf(u)
        else:
            logger.info("File ignored %s", u)
    for u in glob.glob(os.path.join(key_mapping_folder, "*", "")):
        logger.info("File exists %s", u)


if __name__ == "__main__":
    create_folders()
    process_all()
