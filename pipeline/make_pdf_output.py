import os
import json
import logging

from computation.form_worksheet_names import k_it201
from utils.forms_constants import forms_folder, keys_extension, pdf_extension, json_extension
from utils.forms_utils import fill_pdf_from_keys, load_keys, map_folders, output_pdf_folder
from pdfrw import PdfReader, PdfWriter


def fill_pdfs(year):
    data_file = os.path.join("output", year, "data" + json_extension)
    with open(data_file, 'r') as f:
        forms_state = json.load(f)

    map_folders(output_pdf_folder, year)
    form_year_folder = os.path.join(forms_folder, year)
    output_year_folder = os.path.join(output_pdf_folder, year)

    all_out_files = []
    for f, d_contents in forms_state.items():
        if f in [k_it201]:
            continue
        d_mapping = load_keys(os.path.join(form_year_folder, f + keys_extension))

        def fill_one_pdf(contents, suffix=""):
            logger = logging.getLogger('output_pdf')
            keys_expected = {val[0] for val in d_mapping.values()}
            unmatched = set(contents.keys()) - keys_expected
            if unmatched:
                logger.error("%s%s - computation keys not in .keys: %s", f, suffix, sorted(unmatched))
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


def main(years):
    for year in years:
        pdf_files = fill_pdfs(year)
        merge_pdfs(pdf_files, os.path.join("output", year, "forms" + pdf_extension))
