import json
from itertools import islice
from utils.forms_utils import *
from pdfrw import PdfReader, PdfWriter


override_keyword = "override"

k_1040 = 'Federal/f1040'
k_1040s1 = 'Federal/f1040s1'
k_1040s3 = 'Federal/f1040s3'
k_1040sb = 'Federal/f1040sb'
k_1040sd = 'Federal/f1040sd'
k_6251 = 'Federal/f6251'
k_8949 = 'Federal/f8949'


logger = logging.getLogger('fill_taxes')
process_logger(logger, file_name='fill_taxes')


def get_main_info(d):
    # gets name ssn address etc from w2

    # check that info matches between several W2
    keys_to_compare = {
        'FullName', 'FirstName', 'LastName',
        'Address', 'Address_apt',
        'Address_city', 'Address_state', 'Address_zip', 'SSN',
    }
    one_map = {}
    for w in d['W2']:
        for k in keys_to_compare:
            if k in w:
                val = w[k]
                if k in one_map:
                    vm = one_map[k]
                    if val != vm:
                        logger.error("Mismatch info between W2 - for key %s found %s and %s", k, val, vm)
                else:
                    one_map[k] = val
    for k in keys_to_compare:
        if k not in one_map:
            logger.error("Missing info from W2 %s", k)

    def split_name(full, first, last):
        s = full.split(" ")
        if len(s) == 2:
            i = ""
        else:
            i = s[1][0]
        return {'first_name': first, 'initial': i, 'last_name': last}

    info = {
        **split_name(one_map['FullName'], one_map['FirstName'], one_map['LastName']),
        'ssn': one_map['SSN'],
        'address_street_and_number': one_map['Address'],
        'address_apt': one_map['Address_apt'],
        'address_city_state_zip': " ".join([one_map['Address_city'], one_map['Address_state'], one_map['Address_zip']]),
    }

    if override_keyword in d:
        info.update(d[override_keyword])
    return info


def fill_taxes(d):
    main_info = get_main_info(d)
    wages = sum(w['Wages'] for w in d['W2'])
    federal_tax = sum(w['Federal_tax'] for w in d['W2'])
    taxable_interest = sum(i['Interest'] for i in d['1099'])
    dividends_qualified = sum(i['Qualified Dividends'] for i in d['1099'])
    dividends_ordinary = sum(i['Ordinary Dividends'] for i in d['1099'])

    n_trades = sum(len(i['Trades']) for i in d['1099'])
    sum_trades = {"SHORT": {"Proceeds": 0, "Cost": 0, "Adjustment": 0, "Gain": 0},
                  "LONG": {"Proceeds": 0, "Cost": 0, "Adjustment": 0, "Gain": 0}}  # from 8949 to fill 1040sd

    forms_state = {}  # mapping name of forms with content
    worksheets = {}  # worksheets need not be printed

    class Form:
        def __init__(self, key):
            self.key = key
            self.d = {}
            forms_state[self.key] = self.d

        def push_to_dict(self, key, value, round_i=0):
            if value != 0:
                self.d[key] = round(value, round_i)

        def push_name_ssn(self, prefix="", suffix=""):
            self.d[prefix + 'name' + suffix] = forms_state[k_1040]['self_first_name_initial'] \
                             + " " + forms_state[k_1040]['self_last_name']
            self.d[prefix + 'ssn' + suffix] = main_info['ssn']

        def push_sum(self, key, it):
            self.d[key] = sum(self.d.get(k, 0) for k in it)

        def build(self):
            raise NotImplementedError()

    class Form1040(Form):
        def __init__(self):
            Form.__init__(self, k_1040)

        def build(self):
            print("Called")
            first_name_and_initial = main_info['first_name']
            if main_info['initial'] != "":
                first_name_and_initial += " " + main_info['initial']
            self.d.update({
                'single': True,
                'self_first_name_initial': first_name_and_initial,
                'self_last_name': main_info['last_name'],
                'self_ssn': main_info['ssn'],
                'address': main_info['address_street_and_number'],
                'apt': main_info['address_apt'],
                'city_state_zip': main_info['address_city_state_zip'],
                'full_year_health_coverage_or_exempt': d['full_year_health_coverage_or_exempt'],
                'presidential_election_self': d['presidential_election_self'],
                'self_occupation': d['occupation']
            })

            self.push_to_dict('1_dollar', wages)
            self.push_to_dict('2b_dollar', taxable_interest)
            self.push_to_dict('3a_dollar', dividends_qualified)
            self.push_to_dict('3b_dollar', dividends_ordinary)

            if n_trades > 0:
                # need line 22 from schedule 1
                if k_1040s1 not in forms_state:
                    Form1040s1().build()
                self.push_to_dict('6_from_s1_22', forms_state[k_1040s1]['22_dollar'])

            self.push_sum('6_dollar', ['1_dollar',
                                       '2a_dollar', '2b_dollar',
                                       '3a_dollar', '3b_dollar',
                                       '4a_dollar', '4b_dollar',
                                       '5a_dollar', '5b_dollar',
                                       '6_from_s1_22'
                                       ])

            if k_1040s1 in forms_state:
                self.push_to_dict('7_dollar', self.d['6_dollar'] - forms_state[k_1040s1].get('36_dollar', 0))
            else:
                self.push_to_dict('7_dollar', self.d['6_dollar'])

            self.push_to_dict('8_dollar', 12000)

            # 9 is qbi

            self.push_to_dict('10_dollar', max(0, self.d.get('7_dollar', 0)
                                               - self.d.get('8_dollar', 0) - self.d.get('9_dollar', 0)))

            tax_computed = self.d['10_dollar']
            self.push_to_dict('11a_tax', tax_computed)

            self.push_to_dict('13_dollar', max(0, self.d.get('11_dollar', 0) - self.d.get('12_dollar', 0)))
            self.push_sum('15_dollar', ['13_dollar', '14_dollar'])

            self.push_to_dict('16_dollar', federal_tax)
            self.push_sum('18_dollar', ['16_dollar', '17_dollar'])

            # refund
            overpaid = self.d['18_dollar'] - self.d['15_dollar']
            if overpaid > 0:
                self.push_to_dict('19_dollar', overpaid)
                # all refunded
                self.push_to_dict('20a_dollar', overpaid)
                self.d['20b_dollar'] = d['routing_number']
                if d['checking']:
                    self.d['20c_checking'] = True
                else:
                    self.d['20c_savings'] = True
                self.d['20d_dollar'] = d['account_number']
                self.push_to_dict('21_dollar', 0)
            else:
                self.push_to_dict('22_dollar', -overpaid)
                self.push_to_dict('23_dollar', 0)

    class Form1040s1(Form):
        def __init__(self):
            Form.__init__(self, k_1040s1)

        def build(self):
            self.push_name_ssn()
            # capital gains
            if n_trades > 0:
                if not d['scheduleD']:
                    self.push_to_dict('13_not_d', False)
                if k_1040sd not in forms_state:
                    Form8949().build()  # build 8949 first
                    Form1040sd().build()

            gains = forms_state[k_1040sd]['16']
            if gains >= 0:
                self.push_to_dict('13_dollar', gains)
            else:
                self.push_to_dict('13_dollar', -forms_state[k_1040sd]['21'])
            self.push_sum('22_dollar',
                          ['1_9b_dollar',
                           *[str(i) + "_dollar"
                             for i in range(10, 22)]
                           ])

    class Form1040s3(Form):
        def __init__(self):
            Form.__init__(self, k_1040s3)

        def build(self):
            self.push_name_ssn()

    class Form1040sb(Form):
        def __init__(self):
            Form.__init__(self, k_1040sb)

        def build(self):
            self.push_name_ssn()

    class Form1040sd(Form):
        def __init__(self):
            Form.__init__(self, k_1040sd)

        def build(self):
            self.push_name_ssn()

            # short / long term gains
            def fill_gains(ls_key, index):
                self.push_to_dict('{}b_proceeds'.format(index), sum_trades[ls_key]['Proceeds'], 2)
                self.push_to_dict('{}b_cost'.format(index), sum_trades[ls_key]['Cost'], 2)
                self.push_to_dict('{}b_adjustments'.format(index), sum_trades[ls_key]['Adjustment'], 2)
                self.push_to_dict('{}b_gain'.format(index), sum_trades[ls_key]['Gain'], 2)
            fill_gains("SHORT", "1")
            fill_gains("LONG", "8")

            # fill capital loss carryover worksheet

            self.push_sum('7', ['1a_gain', '1b_gain', '2_gain', '3_gain', '4', '5', '6'])
            self.push_sum('15', ['8a_gain', '8b_gain', '9_gain', '10_gain', '11', '12', '13', '14'])
            self.push_sum('16', ['7', '15'])
            if self.d['16'] < 0:
                capital_loss_limit = 3000 if d['single'] else 1500
                self.push_to_dict('21', min(capital_loss_limit, -self.d['16']))

            if dividends_qualified > 0:
                self.d['22_y'] = True
            else:
                self.d['22_n'] = True

    class Form6251(Form):
        def __init__(self):
            Form.__init__(self, k_6251)

        def build(self):
            self.push_name_ssn()

    class Form8949(Form):  # may need several of them when many transactions
        def __init__(self):
            Form.__init__(self, k_8949)

        def build(self):
            def yield_trades(long_short):
                for uu in d['1099']:
                    for tt in uu['Trades']:
                        if tt['LongShort'] == long_short:
                            yield tt

            trades_short = yield_trades('SHORT')
            trades_long = yield_trades('LONG')
            trades_per_page_limit = 14

            trades_subsets = []
            while True:
                trades = {
                    'SHORT': list(islice(trades_short, trades_per_page_limit)),
                    'LONG': list(islice(trades_long, trades_per_page_limit))
                }
                if len(trades['SHORT']) == 0 and len(trades['LONG']) == 0:
                    break
                trades_subsets.append(trades)

            # accumulate the proceeds/cost/adjustment/gain for 1040sd

            if len(trades_subsets) == 1:
                # if few enough trades
                forms_state[k_8949] = self.build_one(trades)
            else:
                # if many -> use a list of content dictionaries
                ll = [self.build_one(l) for l in trades_subsets]
                forms_state[k_8949] = ll

        def build_one(self, trades):
            self.push_name_ssn(prefix="I_")
            self.push_name_ssn(prefix="II_")

            def fill_trades(ls_key, check_key, index):
                if len(trades[ls_key]) > 0:
                    self.d[check_key] = True
                    s_proceeds, s_cost, s_adj, s_gain = 0, 0, 0, 0
                    for i, t in enumerate(trades[ls_key], 1):
                        self.d['{}_1_{}_description'.format(index, str(i))] = t['SalesDescription']
                        self.d['{}_1_{}_date_acq'.format(index, str(i))] = t['DateAcquired']
                        self.d['{}_1_{}_date_sold'.format(index, str(i))] = t['DateSold']

                        proceeds = t['Proceeds']
                        self.push_to_dict('{}_1_{}_proceeds'.format(index, str(i)), proceeds, 2)
                        cost = t['Cost']
                        self.push_to_dict('{}_1_{}_cost'.format(index, str(i)), cost, 2)

                        if 'WashSaleValue' in t:
                            adj = t['WashSaleValue']
                            self.push_to_dict('{}_1_{}_adjustment'.format(index, str(i)), adj, 2)
                            self.d['{}_1_{}_code'.format(index, str(i))] = t['WashSaleCode']
                        else:
                            adj = 0

                        gain = proceeds - cost + adj
                        self.push_to_dict('{}_1_{}_gain'.format(index, str(i)), gain, 2)

                        s_proceeds += proceeds
                        s_cost += cost
                        s_adj += adj
                        s_gain += gain

                    self.push_to_dict('{}_2_proceeds'.format(index), s_proceeds, 2)
                    self.push_to_dict('{}_2_cost'.format(index), s_cost, 2)
                    self.push_to_dict('{}_2_adjustment'.format(index), s_adj, 2)
                    self.push_to_dict('{}_2_gain'.format(index), s_gain, 2)

                    sum_trades[ls_key]['Proceeds'] += s_proceeds
                    sum_trades[ls_key]['Cost'] += s_cost
                    sum_trades[ls_key]['Adjustment'] += s_adj
                    sum_trades[ls_key]['Gain'] += s_gain

            fill_trades('SHORT', 'short_a', 'I')
            fill_trades('LONG', 'long_d', 'II')
            return self.d.copy()

    Form1040().build()  # one other version for NR
    # Form1040NR().build()  # one other version for NR
    print(forms_state)
    print(sum_trades)
    return forms_state, worksheets


def fill_pdfs(forms_state):
    map_folders(output_pdf_folder)
    all_out_files = []
    for f, d_contents in forms_state.items():
        d_mapping = load_keys(os.path.join(forms_folder, f + keys_extension))

        def fill_one_pdf(contents, suffix=""):
            ddd = {k: contents[val[0]] for k, val in d_mapping.items() if val[0] in contents}
            outfile = os.path.join(output_pdf_folder, f + suffix + pdf_extension)
            all_out_files.append(outfile)
            fill_pdf_from_keys(file=os.path.join(forms_folder, f + pdf_extension),
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


def main():
    name = "toto"
    j = json.load(open("{}.json".format(name), 'rb'))

    additional_info = {
        "single": True,
        "dependents": False,
        'occupation': 'Analyst',
        'full_year_health_coverage_or_exempt': True,
        'presidential_election_self': True,
        'standard_deduction': True,  # not a key
        'scheduleD': True,
        'checking': True,
        'routing_number': '11111111',
        'account_number': '444444444',
    }

    override_stuff = {
    }

    data = {}
    data.update(j)
    data.update(additional_info)
    data[override_keyword] = override_stuff

    for u, v in data.items():
        print(u, v)

    states, worksheets_all = fill_taxes(data)
    pdf_files = fill_pdfs(states)
    outfile = name + pdf_extension
    merge_pdfs(pdf_files, outfile)


if __name__ == "__main__":
    main()
