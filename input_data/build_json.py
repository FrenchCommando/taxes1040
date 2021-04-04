# builds the json data file from the input folder
# One file per person
# Select file using different values in the main

import os
import logging
import json
import glob
from collections import defaultdict
import pandas as pd
import xml.etree.ElementTree as eTree
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from io import StringIO
from utils.logger import process_logger


# create logger with 'spam_application'
logger = logging.getLogger('input_data')
process_logger(logger, file_name="json_data")


def parse_pdf(path, print_lines=False):
    rsrcmgr = PDFResourceManager()
    retstr = StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)
    with open(path, 'rb') as fp:
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        password = ""
        maxpages = 0
        caching = True
        pagenos = set()

        for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages, password=password, caching=caching,
                                      check_extractable=True):
            interpreter.process_page(page)
        text = retstr.getvalue()

    device.close()
    retstr.close()

    u = text.split("\n")
    if print_lines:  # print line numbers
        it = iter(u)
        i = 0
        try:
            while True:
                print(i, next(it))
                i += 1
        except StopIteration:
            pass

    return u


def parse_xml(path, print_tag=False):
    # parsing xml file
    tree = eTree.parse(path)
    root = tree.getroot()

    def get_tax_root():
        for node in root:
            for node1 in node:
                for node2 in node1:
                    if node2.tag == "TAX1099RS":
                        return node2

    tax_root = get_tax_root()

    for u in tax_root:
        if print_tag:
            print(u)
            for t in u:
                print(t.tag, t.text)

    return tax_root


def parse_w2(path):
    u = parse_pdf(path=path, print_lines=False)

    if "SG-W2-2018" in path:
        name_overflow = True
        company_index = 216
        name_index = 223
        ssn_index = 230
        wages_index = 232
        federal_index = 238
        state_index = 256
        state_index_end = 276
        # of course it depends on the version you use
        # company_index = 25
        # name_index = 32
        # ssn_index = 39
        # wages_index = 41
        # federal_index = 47
        # state_index = 65
        # state_index_end = 85
        state_row_first = False

    if "SG-W2-2019" in path:
        name_overflow = True
        company_index = 43
        name_index = 50
        ssn_index = 57
        wages_index = 59
        federal_index = 65
        state_index = 71
        state_index_end = 91
        state_row_first = False

    if "GS-W2-2019" in path:
        name_overflow = False
        company_index = 44
        name_index = 84
        ssn_index = 91
        wages_index = 93
        federal_index = 99
        state_index = 294
        state_index_end = 308
        state_row_first = True

    if "GS-W2-2020" in path:
        name_overflow = False
        company_index = 44
        name_index = 84
        ssn_index = 91
        wages_index = 93
        federal_index = 99
        state_index = 297
        state_tax_index = 303
        local_tax_index = 307
        locality_index = 309

    if "MS-W2-2020" in path:
        name_overflow = False
        company_index = 86
        company_title_length = 2
        name_index = 90
        ssn_index = 97
        wages_index = 99
        federal_index = 105
        state_index = 290
        state_tax_index = 296
        local_tax_index = 302
        locality_index = 304

    def city_state_zip(line, name):
        ll = line.split(" ")
        return {
            name + "_city": " ".join(ll[:-2]).strip(","),
            name + "_state": ll[-2],
            name + "_zip": ll[-1]
        }

    def first_mid_last(name):
        ll = name.split(" ")
        dd = {
            "FullName": name,
            "FirstName": ll[0],
            "LastName": ll[-1]
        }
        if len(ll) > 2:
            dd.update({
                "MiddleName": " ".join(ll[1:-1])
            })
        return dd

    def company_name_address(lines):
        if name_overflow:
            return dict(
                Company=" ".join(lines[:2]),
                Company_address=lines[-1],
            )
        else:
            return dict(
                Company=lines[0],
                Company_address=" ".join(lines[1:]),
            )

    def state_and_local(lines):
        if state_row_first:
            return dict(
                State=lines[0],
                State_tax=lines[6],
                Local_tax=lines[12],
                Locality=lines[-1],
            )
        else:
            return dict(
                State=lines[0],
                State_tax=lines[4],
                Local_tax=lines[6],
                Locality=lines[-1],
            )
    if 'company_title_length' not in locals():
        company_title_length = 3

    d = {
        **company_name_address(lines=u[company_index:company_index + company_title_length]),
        **city_state_zip(u[company_index + company_title_length], "Company"),
        **first_mid_last(u[name_index]),
        "Address": u[name_index + 1],
        "Address_apt": u[name_index + 2].split(" ")[-1],
        **city_state_zip(u[name_index + 3], "Address"),
        "SSN": u[ssn_index].replace("-", ""),
        "Wages": u[wages_index],
        "SocialSecurity_wages": u[wages_index + 2],
        "Medicare_wages": u[wages_index + 4],
        "Federal_tax": u[federal_index],
        "SocialSecurity_tax": u[federal_index + 2],
        "Medicare_tax": u[federal_index + 4],
    }
    if 'state_row_first' in locals():
        d.update(state_and_local(lines=u[state_index:state_index_end + 1]))
    else:
        d.update(dict(
            State=u[state_index],
            State_tax=u[state_tax_index],
            Local_tax=u[local_tax_index],
            Locality=u[locality_index],
        ))

    for u, v in d.copy().items():
        if 'tax' in u or 'wages' in u.lower():
            d[u] = float(v)

    logger.info("Parsed W2 %s", path)

    return d


def parse_1099(path):
    if 'xml' in path:
        return parse_1099_xml(path=path)
    elif 'pdf' in path:
        return parse_1099_pdf(path=path)
    elif 'csv' in path:
        return parse_1099_csv(path=path)
    else:
        logger.error(f"Input not parsed parse_1099\t{path}")


def parse_1099_pdf(path):
    u = parse_pdf(path=path, print_lines=False)

    def try_float(x):
        try:
            return float(x)
        except ValueError:
            return x.strip()

    def try_float_dollar(x):
        if x.strip()[0] == "$":
            return try_float(x=x.strip()[1:])

    if "etrade" in path:
        # didn't get 1099-INT that year

        # 1099-DIV

        d = dict()
        d["Qualified Dividends"] = try_float_dollar(x=u[133])
        d["Ordinary Dividends"] = try_float_dollar(x=u[134])
        d["Institution"] = u[87]

        # 1099-B
        # only covered / short-term
        d_trades = [
            {
                "SalesDescription": " ".join(u[610:613]),
                "Shares": try_float(x=u[533]),
                "DateAcquired": u[535],
                "DateSold": u[537],
                "Proceeds": try_float_dollar(x=u[542]),
                "Cost": try_float_dollar(x=u[548]),
                "WashSaleCode": "",
                "WashSaleValue": try_float_dollar(x=u[567]),
                "LongShort": "SHORT",
                "FormCode": "A",
            },
            {
                "SalesDescription": " ".join(u[614:617]),
                "Shares": try_float(x=u[573]),
                "DateAcquired": u[575],
                "DateSold": u[577],
                "Proceeds": try_float_dollar(x=u[579]),
                "Cost": try_float_dollar(x=u[581]),
                "WashSaleCode": "",
                "WashSaleValue": try_float_dollar(x=u[585]),
                "LongShort": "SHORT",
                "FormCode": "A",
            },
        ]

        d["Trades"] = d_trades

    elif "Marcus" in path:
        d = {
            "Interest": try_float(x=u[81]),
            "Institution": u[0],
        }
    else:
        logger.error(f"Input not parsed parse_1099_pdf\t{path}")

    logger.info("Parsed 1099 %s", path)

    return d


def parse_1099_csv(path):
    table = pd.read_csv(path, header=None)

    # interest
    t_interest = table.loc[table[0] == "1099 Summary          "]. \
        drop([0], axis=1).dropna(axis=1).T.set_index(0).T
    d_interest = t_interest.to_dict('records')[0]

    def try_float(x):
        try:
            return float(x)
        except ValueError:
            return x.strip()

    interest_mapping = {
        "1099-DIV-1A Total Ordinary Dividends": "Ordinary Dividends",
        "1099-DIV-1B Qualified Dividends": "Qualified Dividends",
        "1099-DIV-7 Foreign Tax Paid": "Foreign Tax",
        "1099-INT-1 Interest Income": "Interest",
        "1099-B-Total Proceeds": "Proceeds",
        "1099-B-Total Cost Basis": "Cost Basis",
        "1099-B-Total Market Discount": "Market Discount",
        "1099-B-Total Wash Sales": "Wash Sales",
        "1099-B-Realized Gain/Loss": "Realized Gain/Loss",
        "1099-B-Federal Income Tax Withheld": "Federal Income Tax Withheld",
    }

    d_interest = dict((interest_mapping.get(k, k), try_float(v)) for k, v in d_interest.items())

    if "Fidelity" in path:
        d_interest['Institution'] = """NATIONAL FINANCIAL SERVICES LLC"""
    # """499 WASHINGTON BLVD
    # JERSEY CITY, NJ 07310"""

    # trades
    t_trades = table.loc[table[0] == "1099-B-Detail                           "]. \
        drop([0], axis=1).dropna(axis=1).T.set_index(1).T
    d_trades = t_trades.to_dict('records')

    trades_mapping = {
        "1099-B-1a Description of property Stock or Other symbol CUSIP ": "SalesDescription",
        "Quantity": "Shares",
        "1099-B-1b Date Acquired": "DateAcquired",
        "1099-B-1c Date Sold or Disposed": "DateSold",
        "1099-B-1d Proceeds": "Proceeds",
        "1099-B-1e Cost or Other Basis": "Cost",
        "1099-B-1f Accrued Market Discount": "WashSaleCode",
        "1099-B-1g-Wash sale loss Disallowed": "WashSaleValue",
        "Term": "LongShort",
    }

    d_trades_clean = []
    for t in d_trades:
        trade_d = dict((trades_mapping.get(k, k), try_float(v)) for k, v in t.items())
        form_code = trade_d['Covered/Uncovered']
        long_short = trade_d['LongShort']
        trade_d["FormCode"] = ("A" if form_code == "COVERED" else "B") if long_short == "SHORT TERM" \
            else ("D" if form_code == "COVERED" else "E")
        d_trades_clean.append(trade_d)

    d_interest["Trades"] = d_trades_clean

    logger.info("Parsed 1099 %s", path)

    return d_interest


def parse_1099_xml(path):

    def parse_dict(dd, name_map):
        def parse_element(name):
            uu = dd.find(name)
            if uu.text.strip() != "":
                if "INFO" in dd.tag:
                    return uu.text
                return float(uu.text)
            trades = []

            trade_info_map = {
                "SalesDescription": "SALEDESCRIPTION",
                "DateAcquired": "DTAQD",
                "DateSold": "DTSALE",
                "Proceeds": "SALESPR",
                "Cost": "COSTBASIS",
                "Shares": "NUMSHRS",
                "Name": "SECNAME",
                "LongShort": "LONGSHORT",
                "FormCode": "FORM8949CODE",
            }
            for ttt in uu:
                ddd = {k: ttt.find(desc).text for k, desc in trade_info_map.items()}
                wash = ttt.find("WASHSALELOSSDISALLOWED")
                if wash is not None:
                    ddd.update({
                        "WashSaleValue": float(wash.text),
                        "WashSaleCode": "W"
                    })
                for f in ["Proceeds", "Cost", "Shares"]:
                    ddd[f] = float(ddd[f])
                for f in ["DateAcquired", "DateSold"]:
                    date = ddd[f]
                    ddd[f] = date[4:6] + "," + date[6:8] + "," + date[:4]
                trades.append(ddd)
            logger.info("Number of trades %i", len(trades))
            logger.info("Total capital gain %.2f", sum(i["Proceeds"] - i["Cost"] + i.get("WashSaleValue", 0.)
                                                       for i in trades))
            return trades

        return {clean_name: parse_element(name)
                for name, clean_name in name_map.items()}

    tag_map = {
        "INFO": {"FINAME_DIRECTDEPOSIT": "Institution"},
        "DIV": {"ORDDIV": "Ordinary Dividends",
                "QUALIFIEDDIV": "Qualified Dividends",
                "FORTAXPD": "Foreign Tax"},
        "INT": {"INTINCOME": "Interest"},
        "B_V100": {"EXTDBINFO_V100": "Trades"},
    }

    tax_root = parse_xml(path=path, print_tag=False)

    d = {}
    for u in tax_root:
        for t, v in tag_map.items():
            if t in u.tag:
                d.update(parse_dict(u, v))

    logger.info("Parsed 1099 %s", path)
    return d


def read_data_pdf(folder):
    data = defaultdict(list)

    for f in glob.glob(os.path.join(folder, "*")):
        name = os.path.basename(f)
        name_sub, extension = name.split(".")
        if extension == 'json':
            continue
        company, form, year = name_sub.split("-")
        if form == "W2":
            w2_data = parse_w2(f)
            data['W2'].append(w2_data)
        elif form == '1099':
            data_1099 = parse_1099(f)  # there may be several 1099
            data['1099'].append(data_1099)
        else:
            logger.error(f"Input not parsed read_data_pdf\t{name}")
    return data


def build_json(folder):
    data = read_data_pdf(folder=folder)
    with open(os.path.join(folder, 'input.json'), 'w+') as f:
        json.dump(data, f, indent=4)
        logger.debug("json dumped %s", f.name)


def get_input_path(year_folder):
    input_path = ("input_data", year_folder)
    return os.path.join(os.getcwd(), *input_path)


def build_input(year_folder):
    input_full_folder = get_input_path(year_folder)
    build_json(input_full_folder)


def main():
    build_input(year_folder="2020")


if __name__ == "__main__":
    main()
