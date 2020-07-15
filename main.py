#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    Copyright (C) 2019 FrenchCommando
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

import os
import key_matcher
import fill_keys
import fill_taxes
import input_data.build_json
import shutil
from utils.forms_constants import keys_extension, key_mapping_folder, \
    fields_mapping_folder, log_extension, json_extension, output_pdf_folder


filing_year = "2019"


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


def clean():
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
    # output_year_folder = os.path.join(output_pdf_folder, filing_year)
    # remove_folder(output_year_folder)
    pass


if __name__ == '__main__':
    input_filing_year = "2019"
    form_filing_year = "2018"

    input_data.build_json.year_folder = str(input_filing_year)
    input_data.build_json.main()

    key_matcher.year_folder = str(form_filing_year)
    key_matcher.main()

    fill_keys.year_folder = str(form_filing_year)
    fill_keys.main()

    fill_taxes.input_year_folder = str(input_filing_year)
    fill_taxes.forms_year_folder = str(form_filing_year)
    fill_taxes.main()

    # clean()
