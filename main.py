#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    Copyright (C) 2026 FrenchCommando
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.


""""
====================================================================================================================
        This is a tool to generate 1040 and related forms for Federal Tax filling
        Author : FrenchCommando
====================================================================================================================
"""

import utils.logger  # configure root logger
from pipeline import fill_taxes
from pipeline import make_pdf_output

all_years = [
    # "2018", "2019", "2020", "2021", "2022",
    "2023",
    "2024",
    "2025",
]
# dev_mode = True
dev_mode = False


def dev():
    import os
    import glob
    import shutil
    from pipeline import key_matcher
    from pipeline import fill_keys
    for form_filing_year in all_years:
        key_matcher.year_folder = form_filing_year
        key_matcher.main()
        fill_keys.year_folder = form_filing_year
        fill_keys.main()
    from utils.forms_constants import key_mapping_folder, fields_mapping_folder
    shutil.rmtree(key_mapping_folder)
    for pdf_file_name in glob.glob(os.path.join(fields_mapping_folder, "**", "*.pdf"), recursive=True):
        os.remove(pdf_file_name)


def main():
    if dev_mode:
        dev()
    fill_taxes.main(all_years)
    make_pdf_output.main(all_years)


if __name__ == '__main__':
    main()
