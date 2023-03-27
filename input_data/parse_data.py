import os
import glob
from collections import defaultdict
import numpy as np
import pandas as pd
import xml.etree.ElementTree as eTree
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from io import StringIO
import logging


logger = logging.getLogger('input_data')


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
        print(f"File to be printed {path}")
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

    if "MS-W2-2021" in path:
        name_overflow = False
        company_index = 28
        company_title_length = 2
        name_index = 32
        ssn_index = 44
        wages_index = 50
        federal_index = 56
        state_index = 67
        state_tax_index = 73
        local_tax_index = 96
        locality_index = 98

    if "MS-W2-2022" in path:
        name_overflow = False
        company_index = 28
        company_title_length = 2
        name_index = 32
        ssn_index = 39
        wages_index = 41
        federal_index = 47
        state_index = 53
        state_tax_index = 59
        local_tax_index = 98
        locality_index = 100

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
            no_comma = x.replace(",", "").strip()
            if (no_comma[0], no_comma[-1]) == ("(", ")"):
                return -1 * float(no_comma[1:-1])
            return float(no_comma)
        except ValueError:
            return x.strip()

    def try_float_dollar(x):
        if x.strip()[0] == "$" or x.strip()[1] == "$":
            return try_float(x=x.replace("$", "").strip())

    if "etrade" in path:
        if "etrade-1099-2020.pdf" in path:
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
        elif "etrade-1099-2021.pdf" in path:
            # corrected didn't have corrections
            # didn't get 1099-INT that year

            # 1099-DIV

            d = dict()
            d["Qualified Dividends"] = try_float_dollar(x=u[1609])
            d["Ordinary Dividends"] = try_float_dollar(x=u[1593])
            d["Capital Gain Distributions"] = try_float_dollar(x=u[142])
            d["Foreign Tax Paid"] = try_float_dollar(x=u[152])
            d["Foreign Country"] = u[153]
            d["Institution"] = u[91]

            # 1099-B
            d_trades = []

            # covered / short-term
            covered_short_gross = [
                {
                    "SalesDescription": " ".join(u[558:561]),
                    "Shares": try_float(x=u[540]),
                    "DateAcquired": u[542],
                    "DateSold": u[544],
                    "Proceeds": try_float_dollar(x=u[546]),
                    "Cost": try_float_dollar(x=u[533]),
                },
                {
                    "SalesDescription": " ".join(u[562:564]),
                    "Shares": try_float(x=u[576]),
                    "DateAcquired": u[578],
                    "DateSold": u[580],
                    "Proceeds": try_float_dollar(x=u[582]),
                    "Cost": try_float_dollar(x=u[584]),
                },
                {
                    "SalesDescription": " ".join(u[565:567]),
                    "Shares": try_float(x=u[592]),
                    "DateAcquired": u[595],
                    "DateSold": u[598],
                    "Proceeds": try_float_dollar(x=u[601]),
                    "Cost": try_float_dollar(x=u[616]),
                },
                {
                    "SalesDescription": " ".join(u[565:567]),
                    "Shares": try_float(x=u[593]),
                    "DateAcquired": u[596],
                    "DateSold": u[599],
                    "Proceeds": try_float_dollar(x=u[602]),
                    "Cost": try_float_dollar(x=u[617]),
                },
                {
                    "SalesDescription": " ".join(u[568:571]),
                    "Shares": try_float(x=u[607]),
                    "DateAcquired": u[609],
                    "DateSold": u[611],
                    "Proceeds": try_float_dollar(x=u[614]),
                    "Cost": try_float_dollar(x=u[620]),
                },
                {
                    "SalesDescription": " ".join(u[572:575]),
                    "Shares": try_float(x=u[640]),
                    "DateAcquired": u[642],
                    "DateSold": u[644],
                    "Proceeds": try_float_dollar(x=u[646]),
                    "Cost": try_float_dollar(x=u[648]),
                },
                {  # new page
                    "SalesDescription": " ".join(u[757:761]),
                    "Shares": try_float(x=u[703]),
                    "DateAcquired": u[709],
                    "DateSold": u[715],
                    "Proceeds": try_float_dollar(x=u[720]),
                    "Cost": try_float_dollar(x=u[726]),
                },
                {
                    "SalesDescription": " ".join(u[757:761]),
                    "Shares": try_float(x=u[704]),
                    "DateAcquired": u[710],
                    "DateSold": u[716],
                    "Proceeds": try_float_dollar(x=u[721]),
                    "Cost": try_float_dollar(x=u[727]),
                },
                {
                    "SalesDescription": " ".join(u[762:764]),
                    "Shares": try_float(x=u[787]),
                    "DateAcquired": u[789],
                    "DateSold": u[791],
                    "Proceeds": try_float_dollar(x=u[794]),
                    "Cost": try_float_dollar(x=u[797]),
                },
                {  # 1/3
                    "SalesDescription": " ".join(u[765:767]),
                    "Shares": try_float(x=u[799]),
                    "DateAcquired": u[803],
                    "DateSold": u[807],
                    "Proceeds": try_float_dollar(x=u[818]),
                    "Cost": try_float_dollar(x=u[851]),
                },
                {  # 2/3
                    "SalesDescription": " ".join(u[765:767]),
                    "Shares": try_float(x=u[800]),
                    "DateAcquired": u[804],
                    "DateSold": u[808],
                    "Proceeds": try_float_dollar(x=u[819]),
                    "Cost": try_float_dollar(x=u[852]),
                },
                {  # 3/3
                    "SalesDescription": " ".join(u[765:767]),
                    "Shares": try_float(x=u[801]),
                    "DateAcquired": u[805],
                    "DateSold": u[809],
                    "Proceeds": try_float_dollar(x=u[820]),
                    "Cost": try_float_dollar(x=u[853]),
                },
                {
                    "SalesDescription": " ".join(u[770:772]),
                    "Shares": try_float(x=u[812]),
                    "DateAcquired": u[814],
                    "DateSold": u[816],
                    "Proceeds": try_float_dollar(x=u[823]),
                    "Cost": try_float_dollar(x=u[856]),
                },
                {  # 1/3
                    "SalesDescription": " ".join(u[773:775]),
                    "Shares": try_float(x=u[825]),
                    "DateAcquired": u[829],
                    "DateSold": u[833],
                    "Proceeds": try_float_dollar(x=u[844]),
                    "Cost": try_float_dollar(x=u[858]),
                },
                {  # 2/3
                    "SalesDescription": " ".join(u[773:775]),
                    "Shares": try_float(x=u[826]),
                    "DateAcquired": u[830],
                    "DateSold": u[834],
                    "Proceeds": try_float_dollar(x=u[845]),
                    "Cost": try_float_dollar(x=u[859]),
                },
                {  # 3/3
                    "SalesDescription": " ".join(u[773:775]),
                    "Shares": try_float(x=u[827]),
                    "DateAcquired": u[831],
                    "DateSold": u[835],
                    "Proceeds": try_float_dollar(x=u[846]),
                    "Cost": try_float_dollar(x=u[860]),
                },
                {
                    "SalesDescription": " ".join(u[778:780]),
                    "Shares": try_float(x=u[838]),
                    "DateAcquired": u[840],
                    "DateSold": u[842],
                    "Proceeds": try_float_dollar(x=u[849]),
                    "Cost": try_float_dollar(x=u[863]),
                },
                {
                    "SalesDescription": " ".join(u[781:783]),
                    "Shares": try_float(x=u[930]),
                    "DateAcquired": u[932],
                    "DateSold": u[934],
                    "Proceeds": try_float_dollar(x=u[936]),
                    "Cost": try_float_dollar(x=u[938]),
                },
            ]
            for dd in covered_short_gross:
                dd.update({
                    "WashSaleCode": "",
                    "WashSaleValue": 0,
                    "LongShort": "SHORT",
                    "FormCode": "A",
                })
            d_trades.extend(covered_short_gross)

            # non-covered / short-term
            non_covered_short_gross = [
                {
                    "SalesDescription": " ".join(u[1058:1062]),
                    "Shares": try_float(x=u[1008]),
                    "DateAcquired": u[1011],
                    "DateSold": u[1017],
                    "Proceeds": try_float_dollar(x=u[1023]),
                    "Cost": try_float_dollar(x=u[1029]),
                },
                {
                    "SalesDescription": " ".join(u[1058:1062]),
                    "Shares": try_float(x=u[1009]),
                    "DateAcquired": u[1012],
                    "DateSold": u[1018],
                    "Proceeds": try_float_dollar(x=u[1024]),
                    "Cost": try_float_dollar(x=u[1030]),
                },
            ]
            for dd in non_covered_short_gross:
                dd.update({
                    "WashSaleCode": "",
                    "WashSaleValue": 0,
                    "LongShort": "SHORT",
                    "FormCode": "B",
                })
            d_trades.extend(non_covered_short_gross)

            # unknown
            unknown_gross = [
                {
                    "SalesDescription": " ".join(u[1182:1186]),
                    "Shares": try_float(x=u[1166]),
                    "DateAcquired": "03/11/2021",  # u[1168],  # replace with real value
                    "DateSold": u[1170],
                    "Proceeds": try_float_dollar(x=u[1189]),
                    "Cost": 7890,  # try_float_dollar(x=u[1191]),  # replace
                },
            ]
            for dd in unknown_gross:
                dd.update({
                    "WashSaleCode": "",
                    "WashSaleValue": 0,
                    "LongShort": "SHORT",
                    "FormCode": "B",
                })
            d_trades.extend(unknown_gross)

            # covered short term on net
            covered_short_net = [
                {
                    "SalesDescription": " ".join(u[1292:1295]),
                    "Shares": try_float(x=u[1244]),
                    "DateAcquired": u[1249],
                    "DateSold": u[1254],
                    "Proceeds": try_float_dollar(x=u[1258]),
                    "Cost": try_float_dollar(x=u[1263]),
                },
            ]
            for dd in covered_short_net:
                dd.update({
                    "WashSaleCode": "",
                    "WashSaleValue": 0,
                    "LongShort": "SHORT",
                    "FormCode": "A",
                })
            d_trades.extend(covered_short_net)

            d["Trades"] = d_trades

            # futures - foreign - 1256
            d_contract = []
            futures_foreign = [
                {
                    "SalesDescription": u[1354],
                    "ProfitOrLoss": try_float_dollar(x=u[1380]),
                },
            ]
            d_contract.extend(futures_foreign)
            d["Contract1256"] = d_contract
        elif "etrade8" in path and "-1099-2022.pdf" in path:
            # didn't get 1099-INT that year

            # 1099-DIV

            d = dict()
            d["Qualified Dividends"] = try_float_dollar(x=u[140])
            d["Ordinary Dividends"] = try_float_dollar(x=u[139])
            d["Foreign Tax Paid"] = try_float_dollar(x=u[151])
            d["Foreign Country"] = u[152]
            d["Institution"] = u[88]

            # 1099-B
            # covered / short-term
            d_trades = [
                {
                    "Proceeds": try_float_dollar(x=u[303]),
                    "Cost": try_float_dollar(x=u[305]),
                    "WashSaleValue": try_float_dollar(x=u[307]),
                    "LongShort": "SHORT",
                    "FormCode": "A",
                }
            ]
            # uncovered / short-term - Box B, code X
            # unknown
            unknown_gross = [
                {
                    "SalesDescription": " ".join(u[1547:1550]),
                    "Shares": try_float(x=u[1557]),
                    "DateAcquired": "01/26/2022",  # u[1168],  # replace with real value
                    "DateSold": u[1567],
                    "Proceeds": try_float_dollar(x=u[1574]),
                    "Cost": 10500 + 5310,  # try_float_dollar(x=u[1191]),  # replace
                },
                {
                    "SalesDescription": " ".join(u[1547:1550]),
                    "Shares": try_float(x=u[1558]),
                    "DateAcquired": "04/29/2022",  # u[1168],  # replace with real value
                    "DateSold": u[1568],
                    "Proceeds": try_float_dollar(x=u[1575]),
                    "Cost": 49000 + 52994.7,  # try_float_dollar(x=u[1191]),  # replace
                },
            ]
            for dd in unknown_gross:
                dd.update({
                    "WashSaleCode": "",
                    "WashSaleValue": 0,
                    "LongShort": "SHORT",
                    "FormCode": "B",
                })
            d_trades.extend(unknown_gross)

            d["Trades"] = d_trades
        elif "etrade9" in path and "-1099-2022.pdf" in path:
            # ESPP Morgan
            # didn't get 1099-INT
            # 1099-DIV
            d = dict()
            d["Qualified Dividends"] = try_float_dollar(x=u[137])
            d["Ordinary Dividends"] = try_float_dollar(x=u[136])
            d["Institution"] = u[85]
        else:
            d = dict()
            logger.error(f"Input not parsed parse_1099_pdf\t{path}")
    elif "Marcus" in path:
        if "2020" in path:
            d = {
                "Interest": try_float(x=u[81]),
                "Institution": u[0],
            }
        else:
            d = {
                "Interest": try_float(x=u[82]),
                "Institution": u[0],
            }
    elif "MS-" in path:
        d = {
            "Interest": try_float_dollar(x=u[321]),
            "Institution": u[189],
            "Other Income": try_float_dollar(x=u[348]),
            "Other Other Description": u[523],
        }
    else:
        d = dict()
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


def parse_transaction(path, year):
    table = pd.read_excel(path, engine='openpyxl')
    table = table.loc[table["Date"] < np.datetime64(f"{year+1}-01-01")]
    table = table.loc[np.datetime64(f"{year}-01-01") <= table["Date"]]
    table = table.loc[table["Type"].isin(["Buy", "Sell"])]

    proceeds_table = table.loc[table["Type"] == "Sell"].groupby(["Symbol"]).sum()
    cost_table = table.loc[table["Type"] == "Buy"].groupby(["Symbol"]).sum()

    currency_to_pair = defaultdict(list)
    for pair in proceeds_table.index:
        currency = pair.replace("GUSD", "").replace("USD", "")
        # print(pair, "  \t", currency)
        currency_to_pair[currency].append(pair)

    # print(currency_to_pair)
    d_transactions = []
    for currency, pair_list in currency_to_pair.items():
        shares_value = 0
        proceed_value = 0
        cost_value = 0
        for pair in pair_list:
            # print(pair)
            shares_value -= proceeds_table.loc[pair, f"{currency} Amount {currency}"]

            proceed_value += proceeds_table.loc[pair, "USD Amount USD"]
            proceed_value += proceeds_table.loc[pair, "GUSD Amount GUSD"]
            proceed_value += proceeds_table.loc[pair, "Fee (USD) USD"]

            cost_value -= cost_table.loc[pair, "USD Amount USD"]
            cost_value -= cost_table.loc[pair, "GUSD Amount GUSD"]
            cost_value -= cost_table.loc[pair, "Fee (USD) USD"]
        d_currency = dict(
            SalesDescription=currency,
            Shares=shares_value,
            Proceeds=proceed_value,
            Cost=cost_value,
        )
        d_transactions.append(d_currency)

    # print(pd.concat([proceeds_table.iloc[0], cost_table.iloc[0]], axis=1))
    # print(pd.concat([proceeds_table.iloc[3], cost_table.iloc[3]], axis=1))
    # print(pd.concat([proceeds_table.iloc[4], cost_table.iloc[4]], axis=1))

    for dd in d_transactions:
        dd.update({
            "DateAcquired": "Various",
            "DateSold": "Various",
            "WashSaleCode": "",
            "WashSaleValue": 0,
            "LongShort": "SHORT",
            "FormCode": "C",
        })
    d = dict(Trades=d_transactions)
    logger.info("Parsed transaction %s", path)

    return d


def read_data(folder):
    data = defaultdict(list)

    for f in glob.glob(os.path.join(folder, "*")):
        if os.path.isdir(f):
            continue
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
        elif form == "transaction_history":
            data_transaction = parse_transaction(f, int(year))
            data['transaction'].append(data_transaction)
        else:
            logger.error(f"Input not parsed read_data\t{name}")
    return data
