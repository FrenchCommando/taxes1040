import os
import glob
import re
import pdfrw
from utils.forms_constants import *


def map_folders(name):
    if not os.path.isdir(name):
        os.mkdir(name)
    for u in glob.glob(os.path.join(forms_folder, "*", "")):
        rel = os.path.relpath(u, forms_folder)
        u_path = os.path.join(name, rel)
        if not os.path.isdir(u_path):
            os.mkdir(u_path)
            logger.info("Folders created %s", u_path)
    logger.info("Folders created for %s - Done", name)


def load_keys(file, out_dict=True):
    if out_dict:
        d = {}
    else:
        d = []
    with open(file, 'r') as f:
        logger.info("Loading keys from %s", file)
        for l in f:
            if l[0] == '#':  # ignore comments
                continue
            s = re.split(r'[ \t\n]+', l)
            if out_dict:
                d[s[1]] = s[0], s[2]  # some random stuff at the end
            else:
                d.append((s[0], s[1], s[2]))
    return d


def fill_pdf_from_keys(file, out_file, d):
    # file is the pdf file
    # d is the dictionary mapping the annotation fields to values
    template_pdf = pdfrw.PdfReader(file)

    for annotations in template_pdf.pages:
        for annotation in annotations[ANNOT_KEY]:
            if annotation[SUBTYPE_KEY] == WIDGET_SUBTYPE_KEY:
                if annotation[ANNOT_FIELD_KEY]:
                    key = annotation[ANNOT_FIELD_KEY][1:-1]
                    if key in d.keys():
                        if annotation[ANNOT_FIELD_TYPE_KEY] == ANNOT_FIELD_TYPE_BTN:
                            # it's a button
                            annotation.update(
                                pdfrw.PdfDict(AS=pdfrw.PdfName('Yes' if d[key] else 'Off'))
                            )
                        elif annotation[ANNOT_FIELD_TYPE_KEY] == ANNOT_FIELD_TYPE_TXT:
                            r = d[key]
                            if isinstance(r, float) and r == round(r):
                                r = int(r)
                            annotation.update(
                                pdfrw.PdfDict(V='{}'.format(r))
                            )
    try:
        pdfrw.PdfWriter().write(out_file, template_pdf)
        logger.info("Exporting PDF file %s succeeded", out_file)
    except OSError as e:
        logger.error("File must be open %s -- %s", out_file, e)
