from itertools import islice
from utils.forms_functions import get_main_info, computation_2018 as computation
from utils.form_worksheet_names import *
from utils.forms_constants import logger


def fill_taxes_2018(d):
    main_info = get_main_info(d)
    wages = sum(w['Wages'] for w in d['W2'])
    federal_tax = sum(w['Federal_tax'] for w in d['W2'])

    has_1099 = '1099' in d
    dividends_qualified = None
    additional_income = None

    if has_1099:
        n_trades = sum(len(i['Trades']) for i in d['1099'] if 'Trades' in i)
        additional_income = n_trades > 0
        sum_trades = {"SHORT": {"Proceeds": 0, "Cost": 0, "Adjustment": 0, "Gain": 0},
                      "LONG": {"Proceeds": 0, "Cost": 0, "Adjustment": 0, "Gain": 0}}  # from 8949 to fill 1040sd

    standard_deduction = 12000  # if single
    qualified_business_deduction = 0

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

            if has_1099:
                Form1040sb().build()
                self.push_to_dict('2b_dollar', forms_state[k_1040sb]['4_dollar'])
                self.push_to_dict('3b_dollar', forms_state[k_1040sb]['6_dollar'])

                if forms_state[k_1040sb]['4_dollar'] == 0 \
                        and forms_state[k_1040sb]['6_dollar'] == 0 \
                        and 'foreign_account' not in d:
                    del forms_state[k_1040sb]

                nonlocal dividends_qualified
                dividends_qualified = sum(i.get('Qualified Dividends', 0) for i in d['1099'])
                self.push_to_dict('3a_dollar', dividends_qualified)

            if additional_income:
                # need line 22 from schedule 1
                Form1040s1().build()
                self.push_to_dict('6_from_s1_22', forms_state[k_1040s1]['22_dollar'])

            self.push_sum('6_dollar', ['1_dollar',
                                       '2b_dollar',
                                       '3b_dollar',
                                       '4b_dollar',
                                       '5b_dollar',
                                       '6_from_s1_22'
                                       ])

            if additional_income:
                self.push_to_dict('7_dollar', self.d['6_dollar'] - forms_state[k_1040s1].get('36_dollar', 0))
            else:
                self.push_to_dict('7_dollar', self.d['6_dollar'])

            self.push_to_dict('8_dollar', standard_deduction)

            self.push_to_dict('9_dollar', qualified_business_deduction)

            self.push_to_dict('10_dollar', max(0, self.d.get('7_dollar', 0)
                                               - self.d.get('8_dollar', 0) - self.d.get('9_dollar', 0)))

            if dividends_qualified:
                qualified_dividend_worksheet = QualifiedDividendsCapitalGainTaxWorksheet()
                qualified_dividend_worksheet.build()
                self.push_to_dict('11a_tax', worksheets[w_qualified_dividends_and_capital_gains][27])
            else:
                self.push_to_dict('11a_tax', computation(self.d['10_dollar']))

            # add from 11b
            should_fill = ShouldFill6251Worksheet()
            should_fill.build()
            awt = 0
            if should_fill.fill6251:
                Form1040s2().build()
                Form6251().build()
                awt = forms_state[k_6251]['11_dollar']
            if awt > 0:
                self.d['11b'] = True
                self.push_to_dict('11_dollar', self.d['11a_tax'] + awt)
            else:
                self.push_sum('11_dollar', ['11a_tax'])
            if has_1099:
                Form1040s3().build()
                foreign_tax = forms_state[k_1040s3]['55_dollar']
                if foreign_tax != 0:
                    self.d['12b'] = True
                    self.push_to_dict('12_dollar', forms_state[k_1040s3]['55_dollar'])
                else:
                    del forms_state[k_1040s3]

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
                self.d['20b'] = d['routing_number']
                if d['checking']:
                    self.d['20c_checking'] = True
                else:
                    self.d['20c_savings'] = True
                self.d['20d'] = d['account_number']
                self.d['21_dollar'] = "-0-"
            else:
                self.push_to_dict('22_dollar', -overpaid)
                self.push_to_dict('23_dollar', 0)

    class Form1040NR(Form):
        def __init__(self):
            Form.__init__(self, k_1040nr)

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

    class Form1040s2(Form):
        def __init__(self):
            Form.__init__(self, k_1040s2)

        def build(self):
            self.push_name_ssn()

    class Form1040s3(Form):
        def __init__(self):
            Form.__init__(self, k_1040s3)

        def build(self):
            self.push_name_ssn()
            # I don't need the 1116
            # https://turbotax.intuit.com/tax-tips/military/filing-irs-form-1116-to-claim-the-foreign-tax-credit/L2ODfqp89
            foreign_tax = sum(i.get('Foreign Tax', 0) for i in d['1099'])
            self.push_to_dict('48_dollar', foreign_tax)
            self.push_sum('55_dollar', [str(i) + "_dollar" for i in range(48, 55)])

    class Form1040sb(Form):
        def __init__(self):
            Form.__init__(self, k_1040sb)

        def build(self):
            self.push_name_ssn()

            if len(d['1099']) > 14:
                logger.error("1040sb - too many brokers")

            def fill_value(index, key):
                i = 1
                for f in d['1099']:
                    if key in f and f[key] != 0:
                        self.d["{}_{}_payer".format(index, str(i))] = f['Institution']
                        self.push_to_dict("{}_{}_dollar".format(index, str(i)), f[key])
                        i += 1
            fill_value("1", "Interest")
            fill_value("5", "Ordinary Dividends")

            self.push_sum('2_dollar', ['1_{}_dollar'.format(str(i)) for i in range(1, 15)])
            self.push_to_dict('4_dollar', self.d.get('2_dollar', 0) - self.d.get('3_dollar', 0))
            self.push_sum('6_dollar', ['5_{}_dollar'.format(str(i)) for i in range(1, 17)])

            if 'foreign_account' in d:
                self.d['7a_y'] = True
                self.d['7a_yes_y'] = True
                self.d['7b'] = d['foreign_account']
                self.d['8_n'] = True

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
            capital_loss = CapitalLossCarryoverWorksheet()
            capital_loss.build()
            self.push_to_dict('6', worksheets[w_capital_loss_carryover][8])
            self.push_to_dict('14', worksheets[w_capital_loss_carryover][13])

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
            def yield_trades(long_short, form_code):
                for uu in d['1099']:
                    if 'Trades' in uu:
                        for tt in uu['Trades']:
                            if long_short in tt['LongShort'] and form_code == tt['FormCode']:
                                yield tt

            # need a-b-c granularity here
            # a means "Covered/Uncovered" == 'COVERED' --  "FormCode" == "A"
            # b means "Covered/Uncovered" == 'UNCOVERED' --  "FormCode" == "B"

            trades_subsets = []
            trades_per_page_limit = 14
            for code in ["A", "B", "C", "D", "E", "F"]:
                trades_short = yield_trades(long_short='SHORT', form_code=code)
                trades_long = yield_trades(long_short='LONG', form_code=code)
                while True:
                    trades = {
                        'SHORT': list(islice(trades_short, trades_per_page_limit)),
                        'LONG': list(islice(trades_long, trades_per_page_limit))
                    }
                    if len(trades['SHORT']) == 0 and len(trades['LONG']) == 0:
                        break
                    trades_subsets.append((code, trades))

            # accumulate the proceeds/cost/adjustment/gain for 1040sd

            if len(trades_subsets) == 1:
                # if few enough trades
                forms_state[k_8949] = self.build_one(trades_subsets[0])
            else:
                # if many -> use a list of content dictionaries
                ll = [self.build_one(l) for l in trades_subsets]
                forms_state[k_8949] = ll

        def build_one(self, code_trades):
            code, trades = code_trades
            self.d = {}
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

            # code is A, B, or C

            fill_trades('SHORT', f'short_{code.lower()}', 'I')
            fill_trades('LONG', f'long_{code.lower()}', 'II')
            return self.d.copy()

    class Worksheet:
        def __init__(self, key, n):
            self.key = key
            self.d = [0 for i in range(n + 1)]
            worksheets[self.key] = self.d

        def build(self):
            raise NotImplementedError()

    class CapitalLossCarryoverWorksheet(Worksheet):
        def __init__(self):
            Worksheet.__init__(self, w_capital_loss_carryover, 13)

        def build(self):
            ddd = d
            fff = forms_state
            www = worksheets
            self.d[1] = 0  # Taxes[2017][k_1040]['41']
            self.d[2] = 0  # max(0, -Taxes[2017][k_1040sd]['21'])
            self.d[3] = max(0, self.d[1] + self.d[2])
            self.d[4] = min(self.d[2], self.d[3])
            self.d[5] = 0  # max(0, -Taxes[2017][k_1040sd]['7'])
            self.d[6] = 0  # max(0, Taxes[2017][k_1040sd]['15'])
            self.d[7] = self.d[4] + self.d[6]
            self.d[8] = max(0, self.d[5] - self.d[7])
            if self.d[6] == 0:
                self.d[9] = 0  # max(0, -Taxes[2017][k_1040sd]['15'])
                self.d[10] = 0  # max(0, Taxes[2017][k_1040sd]['7'])
                self.d[11] = max(0, self.d[4] - self.d[5])
                self.d[12] = self.d[10] + self.d[11]
                self.d[13] = max(0, self.d[9] - self.d[12])

    class QualifiedDividendsCapitalGainTaxWorksheet(Worksheet):
        def __init__(self):
            Worksheet.__init__(self, w_qualified_dividends_and_capital_gains, 27)

        def build(self):
            self.d[1] = forms_state[k_1040]['10_dollar']
            self.d[2] = forms_state[k_1040]['3a_dollar']
            if d['scheduleD']:
                self.d[3] = max(0, min(forms_state[k_1040sd]['15'], forms_state[k_1040sd]['16']))
            else:
                self.d[3] = forms_state[k_1040s1]['13_dollar']
            self.d[4] = self.d[2] + self.d[3]
            self.d[5] = 0  # form 4952
            self.d[6] = max(0, self.d[4] - self.d[5])
            self.d[7] = max(0, self.d[1] - self.d[6])
            self.d[8] = 38600 if d['single'] else 77200
            self.d[9] = min(self.d[1], self.d[8])
            self.d[10] = min(self.d[7], self.d[9])
            self.d[11] = self.d[9] - self.d[10]  # taxed at 0%
            self.d[12] = min(self.d[1], self.d[6])
            self.d[13] = self.d[11]
            self.d[14] = self.d[12] - self.d[13]
            self.d[15] = 425800  # for single
            self.d[16] = min(self.d[1], self.d[15])
            self.d[17] = self.d[7] + self.d[11]
            self.d[18] = max(0, self.d[16] - self.d[17])
            self.d[19] = min(self.d[14], self.d[18])
            self.d[20] = self.d[19] * 0.15
            self.d[21] = self.d[11] + self.d[19]
            self.d[22] = self.d[12] - self.d[21]
            self.d[23] = self.d[22] * 0.2
            self.d[24] = computation(self.d[7])
            self.d[25] = self.d[20] + self.d[23] + self.d[24]
            self.d[26] = computation(self.d[1])
            self.d[27] = min(self.d[25], self.d[26])

    class ShouldFill6251Worksheet(Worksheet):
        def __init__(self):
            Worksheet.__init__(self, w_should_fill_6251, 13)
            self.fill6251 = None

        def build(self):
            if k_1040sa in forms_state:
                self.d[1] = forms_state[k_1040]['10_dollar']
                self.d[2] = forms_state[k_1040sa]['7']
                self.d[3] = self.d[1] + self.d[2]
            self.d[4] = forms_state[k_1040s1].get('10_dollar', 0) \
                + forms_state[k_1040s1].get('21_dollar', 0) \
                if k_1040s1 in forms_state else 0
            self.d[5] = self.d[3] - self.d[4]
            self.d[6] = 70300  # single
            if self.d[5] <= self.d[6]:
                self.fill6251 = False
                return
            self.d[7] = self.d[5] - self.d[6]
            self.d[8] = 500000  # single
            if self.d[5] <= self.d[8]:
                self.d[9] = 0
                self.d[11] = self.d[7]
            else:
                self.d[9] = self.d[5] - self.d[8]
                self.d[10] = min(self.d[9] * 0.25, self.d[6])
                self.d[11] = self.d[7] + self.d[10]
            if self.d[11] >= 191100:  # single
                self.fill6251 = True
                return
            self.d[12] = self.d[11] * 0.26
            self.d[13] = forms_state[k_1040]['11a'] \
                + forms_state[k_1040s2]['46']
            self.fill6251 = (self.d[13] < self.d[12])

    if d['resident']:
        Form1040().build()  # one other version for NR
    else:
        logger.error("Non-resident not yet implemented")
        # Form1040NR().build()  # one other version for NR
    return forms_state, worksheets
