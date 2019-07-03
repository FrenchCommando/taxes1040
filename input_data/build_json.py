import os
import logging
import json
import glob
from collections import defaultdict
import xml.etree.ElementTree as etree
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from io import StringIO


# builds the json data file from the input folder

# create logger with 'spam_application'
logger = logging.getLogger('input_data')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('json_build.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)


build_w2 = False  # set to True to display field names and change code
build_1099 = False
data = defaultdict(list)


def parse_w2(path):
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
    if build_w2:  # print line numbers
        it = iter(u)
        i = 0
        try:
            while True:
                print(i, next(it))
                i += 1
        except StopIteration:
            pass

    company_index = 25
    name_index = 32
    ssn_index = 39
    wages_index = 41
    federal_index = 47
    state_index = 65
    locality_index = 85

    def city_state_zip(line, name):
        ll = line.split(" ")
        return {
            name + "_city": " ".join(ll[:-2]),
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

    d = {
        "Company": " ".join(u[company_index:company_index + 2]),
        "Company_address": u[company_index + 2],
        **city_state_zip(u[company_index + 3], "Company"),
        **first_mid_last(u[name_index]),
        "Address": u[name_index + 1],
        "Address_apt": u[name_index + 2],
        **city_state_zip(u[name_index + 3], "Address"),
        "SSN": u[ssn_index],
        "Wages": u[wages_index],
        "SocialSecurity_wages": u[wages_index + 2],
        "Medicare_wages": u[wages_index + 4],
        "Federal_tax": u[federal_index],
        "SocialSecurity_tax": u[federal_index + 2],
        "Medicare_tax": u[federal_index + 4],
        "State": u[state_index],
        "State_tax": u[state_index + 4],
        "Local_tax": u[state_index + 6],
        "Locality": u[locality_index]
    }
    for u, v in d.copy().items():
        if 'tax' in u or 'wages' in u.lower():
            d[u] = float(v)
    data['W2'].append(d)
    logger.info("Parsed W2 %s", path)


def parse_1099(path):
    # parsing xml file
    tree = etree.parse(path)
    root = tree.getroot()

    def get_tax_root():
        for node in root:
            for node1 in node:
                for node2 in node1:
                    if node2.tag == "TAX1099RS":
                        return node2
    tax_root = get_tax_root()

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
                "LongShort": "LONGSHORT"
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

    d = {}
    for u in tax_root:
        for t, v in tag_map.items():
            if t in u.tag:
                d.update(parse_dict(u, v))
        if build_1099:
            print(u)
            for t in u:
                print(t.tag, t.text)

    data['1099'].append(d)
    logger.info("Parsed 1099 %s", path)


def read_data_pdf(folder):
    for f in glob.glob(os.path.join(folder, "*")):
        if 'W2' in f:
            parse_w2(f)  # there may be several w2
        if '1099' in f and 'xml' in f:
            parse_1099(f)  # there may be several 1099
    # print(data)


def build_json(folder):
    logger.debug("Folder Name is %s", folder)
    with open('{}.json'.format(folder), 'w+') as f:
        json.dump(data, f, indent=4)
        logger.debug("json dumped %s", f.name)


if __name__ == "__main__":
    my_folder = "toto"
    read_data_pdf(my_folder)
    build_json(my_folder)
