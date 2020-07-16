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

import key_matcher
import fill_keys
import fill_taxes
import input_data.build_json
import utils.forms_clean


if __name__ == '__main__':

    for form_filing_year in ["2018", "2019"]:
        key_matcher.year_folder = form_filing_year
        key_matcher.main()
        fill_keys.year_folder = form_filing_year
        fill_keys.main()

    for input_filing_year in ["2018", "2019"]:
        input_data.build_json.build_input(year_folder=input_filing_year)

    fill_taxes.main()

    for form_filing_year in ["2018", "2019"]:
        utils.forms_clean.clean(form_filing_year)
