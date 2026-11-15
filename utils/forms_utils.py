import os
import glob
import re
import logging
import pdfrw
from utils.forms_constants import *


def map_folders(name, year_folder):
    logger = logging.getLogger('map_folders')
    if not os.path.isdir(name):
        os.mkdir(name)
    year_name = os.path.join(name, year_folder)
    if not os.path.isdir(year_name):
        os.mkdir(year_name)
    forms_year_folder = os.path.join(forms_folder, year_folder)
    for u in glob.glob(os.path.join(forms_year_folder, "*", "")):
        rel = os.path.relpath(u, forms_year_folder)
        u_path = os.path.join(year_name, rel)
        if not os.path.isdir(u_path):
            os.mkdir(u_path)
            logger.info("Folders created %s", u_path)
    logger.info("Folders created for %s - Done", name)


def load_keys(file, out_dict=True):
    logger = logging.getLogger('load_keys')
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


def iter_widgets(template_pdf):
    """Yield (annotation, key) for every named widget, in page order.
    The key is the annotation name; widgets sharing a name (e.g. checkbox groups in different columns)
    get a '#2', '#3', ... suffix on the repeats so each one can be addressed in .keys files."""
    seen = {}
    for annotations in template_pdf.pages:
        if ANNOT_KEY in annotations:
            for annotation in annotations[ANNOT_KEY]:
                if annotation[SUBTYPE_KEY] == WIDGET_SUBTYPE_KEY and annotation[ANNOT_FIELD_KEY]:
                    name = annotation[ANNOT_FIELD_KEY][1:-1]
                    seen[name] = seen.get(name, 0) + 1
                    yield annotation, name if seen[name] == 1 else f"{name}#{seen[name]}"


def fill_pdf_from_keys(file, out_file, d):
    logger = logging.getLogger('fill_pdf')
    # file is the pdf file
    # d is the dictionary mapping the annotation fields to values
    template_pdf = pdfrw.PdfReader(file)

    for annotation, key in iter_widgets(template_pdf):
        if key not in d:
            continue
        if annotation[ANNOT_FIELD_TYPE_KEY] == ANNOT_FIELD_TYPE_BTN:
            if d[key]:
                annotation.update(pdfrw.PdfDict(AS=next(iter(annotation['/AP']['/N']))))
            else:
                annotation.update(pdfrw.PdfDict(AS='Off'))
        elif annotation[ANNOT_FIELD_TYPE_KEY] == ANNOT_FIELD_TYPE_TXT:
            value = d[key]
            if isinstance(value, float) and value == round(value):
                value = int(value)
            elif isinstance(value, float) and value != round(value, 2):
                value = f'{value:.2f}'
            annotation.update(pdfrw.PdfDict(V=f'{value}'))
    try:
        pdfrw.PdfWriter().write(out_file, template_pdf)
        logger.info("Exporting PDF file %s succeeded", out_file)
    except OSError as e:
        logger.error("File must be open %s -- %s", out_file, e)
