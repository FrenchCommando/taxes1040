from itertools import islice
from utils.forms_functions import (
    get_main_info,
    computation_2024 as computation,
    computation_2024_ny as computation_ny,
    computation_2024_ny_recapture as computation_ny_recapture,
    computation_2024_nyc as computation_nyc,
)
from utils.form_worksheet_names import *
from utils.forms_constants import logger


def fill_taxes_2024(d, output_2023=None):
    if output_2023 is not None:
        states_2023, worksheets_all_2023 = output_2023
    else:
        states_2023, worksheets_all_2023 = None, None

    main_info = get_main_info(d)
    wages = sum(w['Wages'] for w in d['W2'])
    federal_tax = sum(w['Federal_tax'] for w in d['W2'])
    social_security_tax = sum(w['SocialSecurity_tax'] for w in d['W2'])
    medicare_tax = sum(w['Medicare_tax'] for w in d['W2'])
    medicare_wages = sum(w['Medicare_wages'] for w in d['W2'])
    state_tax = sum(w['State_tax'] for w in d['W2'])
    local_tax = sum(w['Local_tax'] for w in d['W2'])

    has_1099 = '1099' in d
    dividends_qualified = None
    additional_income = None
    health_savings_account = d.get('health_savings_account', False)
    capital_gains = None
    contract1256 = None

    if has_1099:
        sum_trades = dict(
            SHORT=dict(
                A=dict(Proceeds=0, Cost=0, Adjustment=0, Gain=0),
                B=dict(Proceeds=0, Cost=0, Adjustment=0, Gain=0),
                C=dict(Proceeds=0, Cost=0, Adjustment=0, Gain=0),
            ),
            LONG=dict(
                D=dict(Proceeds=0, Cost=0, Adjustment=0, Gain=0),
                E=dict(Proceeds=0, Cost=0, Adjustment=0, Gain=0),
                F=dict(Proceeds=0, Cost=0, Adjustment=0, Gain=0),
            ),
        )  # from 8949 to fill 1040sd
        foreign_tax = sum(i.get('Foreign Tax', 0) for i in d['1099'])

    standard_deduction = 14_600  # if single or married filing separately
    qualified_business_deduction = 0
    health_savings_account_max_contribution = 0

    forms_state = {}  # mapping name of forms with content
    worksheets = {}  # worksheets need not be printed
    summary_info = {}  # fields with custom labels

    class Form:
        def __init__(self, key, get_existing=False):
            self.key = key
            if not get_existing:
                self.d = {}
                forms_state[self.key] = self.d
            else:
                self.d = forms_state[self.key]

        def push_to_dict(self, key, value, round_i=0):
            if value != 0:
                self.d[key] = round(value, round_i)

        def push_name_ssn(self, prefix="", suffix=""):
            self.d[prefix + 'name' + suffix] = forms_state[k_1040]['self_first_name_initial'] \
                             + " " + forms_state[k_1040]['self_last_name']
            self.d[prefix + 'ssn' + suffix] = main_info['ssn']

        def push_sum(self, key, it):
            self.d[key] = sum(self.d.get(k, 0) for k in it)

        def revert_sign(self, key):
            if key in self.d:
                self.d[key] = -self.d[key]

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
                'city': main_info['address_city'],
                'state': main_info['address_state'],
                'zip': main_info['address_zip'],
                # 'full_year_health_coverage_or_exempt': d['full_year_health_coverage_or_exempt'],
                'presidential_election_self': d['presidential_election_self'],
                'self_occupation': d['occupation'],
                'phone': d['phone'],
                'email': d['email'],
            })

            if d.get('virtual_currency', False):
                self.push_to_dict('virtual_currency_y', True)
                self.push_to_dict('virtual_currency_n', False)
            else:
                self.push_to_dict('virtual_currency_y', False)
                self.push_to_dict('virtual_currency_n', True)

            self.push_to_dict('1_a', wages)
            self.push_sum('1_z', [
                '1_a', '1_b', '1_c', '1_d', '1_e', '1_f', '1_g', '1_h',
                # '1_i' not i
            ])

            if has_1099:
                Form1040sb().build()

                if forms_state[k_1040sb]['4_value'] == 0 \
                        and forms_state[k_1040sb]['6_value'] == 0 \
                        and 'foreign_account' not in d:
                    del forms_state[k_1040sb]

                nonlocal dividends_qualified
                dividends_qualified = sum(i.get('Qualified Dividends', 0) for i in d['1099'])
                self.push_to_dict('3_a', dividends_qualified)

                nonlocal capital_gains
                capital_gains = sum(i.get('Capital Gain Distributions', 0) for i in d['1099'])

                nonlocal contract1256
                contract1256 = any(i.get('Contract1256', False) for i in d['1099'])

                # for Box A, without corrections skip 8949
                if contract1256:
                    Form6781().build()
                Form8949().build()  # build 8949 first
                Form1040sd().build()

            self.d["7_n"] = not d['scheduleD']

            if health_savings_account or additional_income:
                # fill 8889 and schedule 1
                Form8889().build()
                Form1040s1().build()
                self.push_to_dict('8', forms_state[k_1040s1].get('10', 0))
                self.push_to_dict('10', forms_state[k_1040s1].get('26', 0))
                if forms_state[k_1040s1].get('10', 0) == 0 \
                        and forms_state[k_1040s1].get('26', 0) == 0:
                    del forms_state[k_1040s1]

            self.push_sum('9', ['1_z', '2_b', '3_b', '4_b', '5_b', '6_b', '7_value', '8'])  # total income
            summary_info[f"{self.key} 9 Total income"] = self.d['9']

            self.push_to_dict('11', self.d['9'] - self.d.get('10', 0))  # Adjusted Gross Income
            summary_info[f"{self.key} 11 adjusted gross income"] = self.d['11']

            Form1040sa().build()
            itemized_deduction = forms_state[k_1040sa].get('17', 0)
            # itemized_deduction = 0
            if itemized_deduction > standard_deduction:
                self.push_to_dict('12', itemized_deduction)
            else:
                self.push_to_dict('12', standard_deduction)
            summary_info[f"{self.key} 12 Standard deduction or itemized deductions"] = self.d['12']

            self.push_to_dict('13', qualified_business_deduction)
            self.push_sum('14', ['12', '13'])
            self.push_to_dict('15', max(0, self.d.get('11', 0) - self.d.get('14', 0)))  # Taxable income
            summary_info[f"{self.key} 15 Taxable income"] = self.d['15']

            if dividends_qualified:
                qualified_dividend_worksheet = QualifiedDividendsCapitalGainTaxWorksheet()
                qualified_dividend_worksheet.build()  # enters value in 16
            else:
                self.push_to_dict('16', computation(self.d['15']))
            summary_info[f"{self.key} 16 Tax"] = self.d['16']

            Form1040s2().build()
            if forms_state[k_1040s2].get('3', 0) == 0 \
                    and forms_state[k_1040s2].get('21', 0) == 0:
                del forms_state[k_1040s2]
                del forms_state[k_6251]

            # self.push_to_dict('17', 0)  # schedule 2 line 3
            self.push_sum('18', ['16', '17'])
            self.push_to_dict('19', 0)  # child tax credit

            if foreign_tax > 0:
                Form1040s3().build()  # fills 20
            self.push_sum('21', ['19', '20'])
            self.push_to_dict('22', max(0, self.d.get('18', 0) - self.d.get('21', 0)))

            # self.push_to_dict('23', medicare_tax_stuff)  # other taxes from Schedule 2 line 21
            self.push_sum('24', ['22', '23'])  # total tax
            summary_info[f"{self.key} 24 Total Tax"] = self.d['24']

            self.push_to_dict('25_a', federal_tax)  # from W2
            self.push_to_dict('25_b', 0)  # from 1099
            # self.push_to_dict('25_c', medicare_tax_stuff)  # from other
            self.push_sum('25_d', ['25_a', '25_b', '25_c'])

            estimated_payments = 0
            if "EstimatedIncomeTax" in d:
                if "Federal" in d["EstimatedIncomeTax"]:
                    for line in d["EstimatedIncomeTax"]["Federal"]:
                        estimated_payments += line["Amount"]
            self.push_to_dict('26', estimated_payments)

            self.push_to_dict('27_a', 0)  # Earned Income Credit
            self.push_to_dict('27_b', 0)  # Nontaxable combat pay election
            self.push_to_dict('27_c', 0)  # Prior year Earned Income
            self.push_to_dict('28', 0)  # Additional child tax Credit
            self.push_to_dict('29', 0)  # American opportunity credit Form 8863, line 8
            self.push_to_dict('30', 0)  # Recovery rebate credit
            self.push_to_dict('31', 0)  # Schedule 3, line 15
            self.push_sum('32', ['27_a', '27_b', '27_c', '28', '29', '30', '31'])
            # total other payments and refundable credit

            self.push_sum('33', ['25_d', '26', '32'])  # total payments
            summary_info[f"{self.key} 33 Total Payments"] = self.d['33']

            # refund
            overpaid = self.d['33'] - self.d['24']
            if overpaid > 0:
                self.push_to_dict('34', overpaid)
                summary_info[f"{self.key} 34 Overpaid"] = self.d['34']
                # all refunded
                self.push_to_dict('35a_value', overpaid)
                self.d['35b'] = d['routing_number']
                if d['checking']:
                    self.d['35c_checking'] = True
                else:
                    self.d['35c_savings'] = True
                self.d['35d'] = d['account_number']
                self.d['36'] = "-0-"
            else:
                self.push_to_dict('37', -overpaid)
                self.push_to_dict('38', 0)
                summary_info[f"{self.key} 37 amount you owe"] = self.d['37']

            self.push_to_dict('other_designee_n', True)

    class Form1040s1(Form):
        def __init__(self):
            Form.__init__(self, k_1040s1)

        def build(self):
            self.push_name_ssn()
            if k_8889 in forms_state:
                hsa_deduction = forms_state[k_8889].get('13', 0)
                if hsa_deduction > 0:
                    self.push_to_dict('13', hsa_deduction)
                hsa_taxable_distribution = forms_state[k_8889].get('16', 0)
                if hsa_taxable_distribution > 0:
                    self.push_to_dict('8_e', hsa_taxable_distribution)
                if forms_state[k_8889].get('13', 0) == 0 and forms_state[k_8889].get('13', 0) == 0:
                    del forms_state[k_8889]
            self.push_to_dict('9',
                              - self.d.get('8_a', 0)
                              + self.d.get('8_b', 0)
                              + self.d.get('8_c', 0)
                              - self.d.get('8_d', 0)
                              + self.d.get('8_e', 0)
                              + self.d.get('8_f', 0)
                              + self.d.get('8_g', 0)
                              + self.d.get('8_h', 0)
                              + self.d.get('8_i', 0)
                              + self.d.get('8_j', 0)
                              + self.d.get('8_k', 0)
                              + self.d.get('8_l', 0)
                              + self.d.get('8_m', 0)
                              + self.d.get('8_n', 0)
                              + self.d.get('8_o', 0)
                              + self.d.get('8_p', 0)
                              + self.d.get('8_z', 0)
                              )
            self.push_sum('10', ['1', '2_a', '3', '4', '5', '6', '7', '9'])
            # to 1040 line 8

            self.push_sum('25', ['24_a', '24_b', '24_c', '24_d', '24_e', '24_f',
                                 '24_g', '24_h', '24_i', '24_j', '24_k', '24_z', ])
            self.push_sum('26', ['11', '12', '13', '14', '15',
                                 '16', '17', '18', '19_a', '20', '21', '23', '25'])
            # to 1040 line 10a

    class Form1040s2(Form):
        def __init__(self):
            Form.__init__(self, k_1040s2)

        def build(self):
            self.push_name_ssn()
            # Additional Taxes

            # Part I - Tax
            Form6251().build()  # AMT fills 1
            # Form8962().build()  # Excess advance premium tax credit repayment - fills 2
            self.push_sum(key='3', it=['1', '2'])
            Form(k_1040, get_existing=True).push_to_dict('17', self.d['3'])

            # Part II - Other Taxes
            self.push_sum(key='7', it=['5', '6'])
            Form8959().build()  # Additional Medicare Tax - fills 11
            if forms_state[k_8959]['18'] == 0 \
                    and forms_state[k_8959]['24'] == 0:
                del forms_state[k_8959]

            self.push_sum(key='18', it=[
                f'17_{letter}' for letter in [
                    'a_value',
                    'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q',
                    'z_amount',
                ]
            ])

            self.push_sum(key='21', it=[
                '4',
                '7', '8', '9', '10', '11', '12', '13', '14', '15', '16',
                '18',
            ])
            summary_info[f"{self.key} 21 Total Other Taxes"] = self.d['21']
            Form(k_1040, get_existing=True).push_to_dict('23', self.d['21'])

    class Form1040s3(Form):
        def __init__(self):
            Form.__init__(self, k_1040s3)

        def build(self):
            self.push_name_ssn()
            # I don't need the 1116
            # https://turbotax.intuit.com/tax-tips/military/filing-irs-form-1116-to-claim-the-foreign-tax-credit/L2ODfqp89
            self.push_to_dict('1', foreign_tax)
            self.push_sum('8', ['1', '2', '3', '4', '5', '7'])  # 1040 line 20
            Form(k_1040, get_existing=True).push_to_dict('20', self.d.get('8', 0))

    class Form1040sa(Form):
        def __init__(self):
            Form.__init__(self, k_1040sa)

        def build(self):
            self.push_name_ssn()

            self.push_to_dict('1', d.get('medical_expenses', 0))
            self.push_to_dict('2', forms_state[k_1040]['11'])
            self.push_to_dict('3', self.d['2'] * 0.075)
            self.push_to_dict('4', max(0, self.d.get('1', 0) - self.d['3']))

            if d.get('deduct_sales_tax', False):
                self.push_to_dict('5_a_y', True)
                self.push_to_dict('5_a', d.get('deduct_sales_tax_amount', 0))
            else:
                self.push_to_dict('5_a', state_tax + local_tax)

            # property tax
            property_tax = 0
            if "Other" in d:
                for line in d["Other"]:
                    property_tax += line.get("PropertyTax", 0)
            self.push_to_dict('5_c', property_tax)


            self.push_sum('5_d', ['5_a', '5_b', '5_c'])
            self.push_to_dict('5_e', min(self.d.get('5_d', 0), 10000))
            # 6 is other
            self.push_sum('7', ['5_e', '6'])

            # mortgage interest - 8a
            mortgage_intest_deduction_worksheet = MortgageInterestDeductionWorksheet()
            mortgage_intest_deduction_worksheet.build()

            self.push_sum('8_e', ['8_a', '8_b', '8_c'])
            self.push_sum('10', ['8_e', '9'])

            # charity
            # theft
            # other

            self.push_sum('17', ['4', '7', '10', '14', '15', '16'])
            # to 1040 line 12

            # tick 18 if you want to lose money

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
                        if "Institution" in f and f['Institution'] == "Department of the Treasury":
                            summary_info[f"{self.key} Treasury Interest Exempt from Local Tax"] = f[key]
                            Form(k_it201, get_existing=True).push_to_dict('28', f[key])
                            # still counted
                            # continue
                        self.d["{}_{}_payer".format(index, str(i))] = f['Institution']
                        self.push_to_dict("{}_{}_value".format(index, str(i)), f[key])
                        i += 1
                    other_key = "Other Income"
                    if key == "Interest" and other_key in f and f[other_key] != 0:
                        self.d["{}_{}_payer".format(index, str(i))] = \
                            " ".join((f['Institution'], f['Other Description']))
                        self.push_to_dict("{}_{}_value".format(index, str(i)), f[other_key])
                        i += 1
            fill_value("1", "Interest")
            fill_value("5", "Ordinary Dividends")

            self.push_sum('2_value', ['1_{}_value'.format(str(i)) for i in range(1, 15)])
            self.push_to_dict('4_value', self.d.get('2_value', 0) - self.d.get('3_value', 0))
            self.push_sum('6_value', ['5_{}_value'.format(str(i)) for i in range(1, 17)])

            Form(k_1040, get_existing=True).push_to_dict('2_b', self.d['4_value'])
            Form(k_1040, get_existing=True).push_to_dict('3_b', self.d['6_value'])

            if 'foreign_account' in d:
                self.d['7a_y'] = True
                self.d['7a_yes_y'] = True
                self.d['7b'] = d['foreign_account']
                self.d['8_n'] = True
            else:
                self.d['7a_n'] = True
                self.d['8_n'] = True

    class Form1040sd(Form):
        def __init__(self):
            Form.__init__(self, k_1040sd)

        def build(self):
            self.push_name_ssn()

            self.d['dispose_opportunity_n'] = True

            # short / long term gains
            def fill_gains(ls_key, box_index, number_index):
                self.push_to_dict(f'{number_index}_proceeds', sum_trades[ls_key][box_index]['Proceeds'])
                self.push_to_dict(f'{number_index}_cost', sum_trades[ls_key][box_index]['Cost'])
                if not('a' in number_index or 'b' in number_index):
                    self.push_to_dict(f'{number_index}_adjustments', sum_trades[ls_key][box_index]['Adjustment'])
                self.push_to_dict(f'{number_index}_gain', sum_trades[ls_key][box_index]['Gain'])
            fill_gains("SHORT", "A", "1a")  # b if need adjustments
            fill_gains("SHORT", "B", "2")
            fill_gains("SHORT", "C", "3")
            fill_gains("LONG", "D", "8a")
            fill_gains("LONG", "E", "9")
            fill_gains("LONG", "F", "10")

            # fill capital loss carryover worksheet
            capital_loss = CapitalLossCarryoverWorksheet()
            capital_loss.build()

            # '6' and '14' are filled by CapitalLossCarryoverWorksheet
            # loss as positive number, flip sign for the sum
            self.revert_sign('6')
            self.push_sum('7', ['1a_gain', '1b_gain', '2_gain', '3_gain', '4', '5', '6'])
            self.revert_sign('6')
            summary_info[f"{self.key} 7 Net short-term capital gain or (loss)"] = self.d['7']

            if capital_gains:
                self.push_to_dict('13', capital_gains)
            # '6' and '14' are filled by CapitalLossCarryoverWorksheet
            # loss as positive number, flip sign for the sum
            self.revert_sign('14')
            self.push_sum('15', ['8a_gain', '8b_gain', '9_gain', '10_gain', '11', '12', '13', '14'])
            self.revert_sign('14')
            summary_info[f"{self.key} 15 Net long-term capital gain or (loss)"] = self.d['15']

            self.push_sum('16', ['7', '15'])
            if self.d['16'] > 0:
                Form(k_1040, get_existing=True).push_to_dict('7_value', self.d['16'])
                if self.d['15'] < 0 or self.d['16'] < 0:
                    self.d['17_n'] = True
                else:
                    self.d['17_y'] = True

                    # 18 is '28% Rate Gain Worksheet'
                    # 19 is `Unrecaptured Section 1250 Gain Worksheet`
                    # 20 more worksheet and 4952
                    form_4952 = False
                    if self.d.get('18', 0) == 0 and self.d.get('19', 0) == 0 and not form_4952:
                        self.d['20_y'] = True
                    else:
                        self.d['20_n'] = True
                    return  # don't fill 22

            elif self.d['16'] < 0:
                capital_loss_limit = 3000 if d['single'] else 1500
                self.push_to_dict('21', - min(capital_loss_limit, -self.d['16']))
                Form(k_1040, get_existing=True).push_to_dict('7_value', self.d['21'])
                self.revert_sign(key='21')  # show amount as positive

            if dividends_qualified is not None and dividends_qualified > 0:
                self.d['22_y'] = True
            else:
                self.d['22_n'] = True

    class Form6251(Form):
        def __init__(self):
            Form.__init__(self, k_6251)

        def build(self):
            self.push_name_ssn()

            # Part I
            self.push_to_dict('1_value', forms_state[k_1040]['15'])
            # 2a if itemized
            self.push_sum(key='4_value', it=[
                '1_value',
                '2a_value', '2b_value', '2c_value', '2d_value',
                '2e_value', '2f_value', '2g_value', '2h_value',
                '2i_value', '2j_value', '2k_value', '2l_value',
                '2m_value', '2n_value', '2o_value', '2p_value',
                '2q_value', '2r_value', '2s_value', '2t_value',
                '3_value',
            ])
            if '4_value' in self.d:
                summary_info[f"{self.key} 4 Alternative minimum taxable income"] = self.d['4_value']

            # Part II
            self.push_to_dict('5_value', 81_300)  # see exceptions
            self.push_to_dict('6_value', max(0, self.d.get('4_value', 0) - self.d.get('5_value', 0)))
            if self.d.get('6_value') > 0:
                # line 7
                self.push_to_dict(
                    '7_value',
                    self.d['6_value'] * 0.26 if self.d['6_value'] < 220_700 else
                    self.d['6_value'] * 0.28 - 4_414
                )

                # alternative minimum tax foreign tax credit
                self.push_to_dict('8_value', 0)
                # tentative minimum tax
                self.push_to_dict('9_value', self.d.get('7_value', 0) - self.d.get('8_value', 0))

                self.push_to_dict(
                    '10_value',
                    max(0, forms_state[k_1040]['16'] + forms_state[k_1040s2].get('2', 0))
                    # minus 4972
                    # subtract S3 line 1
                    # form 8978 line 14 positive
                )
            else:
                self.push_to_dict('7_value', 0)
                self.push_to_dict('9_value', 0)
                self.push_to_dict('11_value', 0)

            self.push_to_dict('11_value', max(0, self.d.get('9_value', 0) - self.d.get('10_value', 0)))
            if '11_value' in self.d:
                summary_info[f"{self.key} 11 AMT"] = self.d['11_value']
                Form(k_1040s2, get_existing=True).push_to_dict('1', self.d['11_value'])

    class Form6781(Form):
        def __init__(self):
            Form.__init__(self, k_6781)

        def build(self):
            def yield_contracts():
                for u in d["1099"]:
                    if "Institution" in u:
                        institution = u["Institution"]
                        if "Contract1256" in u:
                            for contract_item in u["Contract1256"]:
                                yield contract_item | dict(Institution=institution)
            for i, item in enumerate(yield_contracts(), 1):
                if i > 3:
                    raise ValueError("Form6781 more than 3 contracts need a new page")
                self.d[f"1_{i}_a"] = f"Form 1099-B {item['Institution']}"
                if item["ProfitOrLoss"] < 0:
                    self.push_to_dict(f"1_{i}_b", - item["ProfitOrLoss"])
                else:
                    self.push_to_dict(f"1_{i}_c", item["ProfitOrLoss"])

            self.push_name_ssn()
            self.push_sum('2_b', ['1_1_b', '1_2_b', '1_3_b'])
            self.push_sum('2_c', ['1_1_c', '1_2_c', '1_3_c'])
            self.push_to_dict('3', self.d.get('2_c', 0) - self.d.get('2_b', 0))
            self.push_sum('5', ['3', '4'])
            self.push_sum('7', ['5', '6'])
            self.push_to_dict('8', self.d.get('7', 0) * 0.4)
            self.push_to_dict('9', self.d.get('7', 0) * 0.6)

    class Form8889(Form):
        def __init__(self):
            Form.__init__(self, k_8889)

        def build(self):
            self.push_name_ssn()

            self.d['1_self'] = True

            self.push_to_dict('2', d.get('health_savings_account_contributions', 0))
            self.push_to_dict('3', health_savings_account_max_contribution)
            self.push_to_dict('4', 0)
            self.push_to_dict('5', self.d['3'] - self.d.get('4', 0))
            self.push_to_dict('6', self.d['5'])  # except if you have separate for spouse
            self.push_to_dict('7', 0)
            self.push_sum('8', ['6', '7'])
            self.push_to_dict('9', d.get('health_savings_account_employer_contributions', 0))
            self.push_to_dict('10', 0)
            self.push_sum('11', ['9', '10'])
            self.push_to_dict('12', max(0, self.d['8'] - self.d['11']))
            self.push_to_dict('13', min(self.d.get('2', 0), self.d['12']))  # to Schedule 1-II-12

            self.push_to_dict('14_a', d.get('health_savings_account_distributions', 0))
            self.push_to_dict('14_b', 0)  # distribution rolled over
            self.push_to_dict('14_c', self.d['14_a'] - self.d.get('14_b', 0))
            self.push_to_dict('15', self.d['14_c'])  # I don't assume it to be different

            self.push_to_dict('16', self.d['14_c'] - self.d['15'])
            # if positive, Schedule 1-I-8 HSA

            # Then is part III, not implemented

    class Form8949(Form):  # may need several of them when many transactions
        def __init__(self):
            Form.__init__(self, k_8949)

        def build(self):
            def yield_trades(long_short, form_code):
                for uu in d['1099']:  # remove crypto transactions
                    if 'Trades' in uu:
                        for tt in uu['Trades']:
                            if long_short in tt['LongShort'] and form_code == tt['FormCode']:
                                yield tt
                if contract1256:
                    if (long_short == "SHORT") and (form_code == "B") and ('8' in forms_state[k_6781]):
                        yield dict(a="Form 6781, Part I", h=forms_state[k_6781]["8"])
                    if (long_short == "LONG") and (form_code == "E") and ('9' in forms_state[k_6781]):
                        yield dict(a="Form 6781, Part I", h=forms_state[k_6781]["9"])

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
                ll = [self.build_one(lll) for lll in trades_subsets]
                forms_state[k_8949] = [lll for lll in ll if lll is not None]

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
                        if "a" in t:  # form 6781 stuff
                            self.d['{}_1_{}_description'.format(index, str(i))] = t["a"]
                            proceeds, cost, adj = 0, 0, 0
                            gain = t["h"]
                            self.push_to_dict('{}_1_{}_gain'.format(index, str(i)), gain)
                        else:
                            self.d['{}_1_{}_description'.format(index, str(i))] = \
                                f"{t['Shares']} {t['SalesDescription']}"
                            self.d['{}_1_{}_date_acq'.format(index, str(i))] = t['DateAcquired']
                            self.d['{}_1_{}_date_sold'.format(index, str(i))] = t['DateSold']

                            proceeds = t['Proceeds']
                            self.push_to_dict('{}_1_{}_proceeds'.format(index, str(i)), proceeds)
                            cost = t['Cost']
                            self.push_to_dict('{}_1_{}_cost'.format(index, str(i)), cost)

                            if 'WashSaleValue' in t:
                                adj = t['WashSaleValue']
                                self.push_to_dict('{}_1_{}_adjustment'.format(index, str(i)), adj)
                                self.d['{}_1_{}_code'.format(index, str(i))] = t['WashSaleCode']
                            else:
                                adj = 0

                            gain = round(proceeds) - round(cost) + round(adj)
                            self.push_to_dict('{}_1_{}_gain'.format(index, str(i)), gain)

                        s_proceeds += round(proceeds)
                        s_cost += round(cost)
                        s_adj += round(adj)
                        s_gain += round(gain)

                    self.push_to_dict('{}_2_proceeds'.format(index), s_proceeds)
                    self.push_to_dict('{}_2_cost'.format(index), s_cost)
                    self.push_to_dict('{}_2_adjustment'.format(index), s_adj)
                    self.push_to_dict('{}_2_gain'.format(index), s_gain)

                    sum_trades[ls_key][code]['Proceeds'] += round(s_proceeds)
                    sum_trades[ls_key][code]['Cost'] += round(s_cost)
                    sum_trades[ls_key][code]['Adjustment'] += round(s_adj)
                    sum_trades[ls_key][code]['Gain'] += round(s_gain)

            # code is A, B, or C

            fill_trades('SHORT', f'short_{code.lower()}', 'I')
            fill_trades('LONG', f'long_{code.lower()}', 'II')
            return self.d.copy() if not (code in ["A", "D"]) else None

    class Form8959(Form):
        def __init__(self):
            Form.__init__(self, k_8959)

        def build(self):
            self.push_name_ssn()

            # Part I
            self.push_to_dict('1', medicare_wages)
            self.push_sum('4', ['1', '2', '3'])
            self.push_to_dict('5', 200_000)  # single
            self.push_to_dict('6', max(0, self.d['4'] - self.d['5']))
            self.push_to_dict('7', self.d.get('6', 0) * 0.009)
            if '7' in self.d:
                summary_info[f"{self.key} 7 Additional Medicare Tax on Medicare wages"] = self.d['7']

            # Part II
            # 8 self-employment income
            self.push_to_dict('9', 200_000)  # single
            self.push_sum('10', ['4'])
            self.push_to_dict('11', max(0, self.d['9'] - self.d['10']))
            self.push_to_dict('12', max(0, self.d.get('8', 0) - self.d.get('11', 0)))
            self.push_to_dict('13', self.d.get('12', 0) * 0.009)
            if '13' in self.d:
                summary_info[f"{self.key} 13 Additional Medicare Tax on self-employment income"] = self.d['13']

            # Part III - Railroad Retirement Tax Act

            # Part IV
            self.push_sum('18', ['7', '13', '17'])
            summary_info[f"{self.key} 18 Total Additional Medicare Tax"] = self.d['18']
            Form(k_1040s2, get_existing=True).push_to_dict('11', self.d['18'])

            # Part V
            self.push_to_dict('19', medicare_tax)
            self.push_sum('20', ['1'])
            self.push_to_dict('21', self.d['20'] * 0.0145)
            if '21' in self.d:
                summary_info[f"{self.key} 21 Regular Medicare Tax withholding on Medicare wages"] = self.d['21']
            self.push_to_dict('22', max(0, self.d['19'] - self.d['21']))
            if '22' in self.d:
                summary_info[f"{self.key} Additional Medicare Tax withholding on Medicare wages"] = self.d['22']

            self.push_sum('24', ['22', '23'])
            if '24' in self.d:
                summary_info[f"{self.key} 24 Total Additional Medicare Tax withholding"] = self.d['24']
            Form(k_1040, get_existing=True).push_to_dict('25_c', self.d['24'])

    class Worksheet:
        def __init__(self, key, n):
            self.key = key
            self.d = [0. for i in range(n + 1)]
            worksheets[self.key] = self.d

        def build(self):
            raise NotImplementedError()

    class MortgageInterestDeductionWorksheet(Worksheet):
        def __init__(self):
            Worksheet.__init__(self, w_mortgage_interest_deduction, 16)

        def build(self):
            interest_paid = 0
            balance_start = 0
            principal_payments = 0
            if "1098" in d:
                for item in d["1098"]:
                    balance_start += item.get("PrincipalBalance", 0)
                    for payment in item.get("Payments", []):
                        interest_paid += payment.get("InterestAmount", 0)
                        principal_payments += payment.get("PrincipalAmount", 0)
            # Part I - Qualified Loan Limit
            self.d[1] = 0  # grandfathered
            self.d[2] = 0  # old
            self.d[3] = 1_000_000
            self.d[4] = max(self.d[1], self.d[3])
            self.d[5] = self.d[1] + self.d[2]
            self.d[6] = min(self.d[4], self.d[5])
            self.d[7] = balance_start - 0.5 * principal_payments  # average balance
            self.d[8] = 750_000
            self.d[9] = max(self.d[6], self.d[8])
            self.d[10] = self.d[6] + self.d[7]
            self.d[11] = min(self.d[9], self.d[10])
            summary_info[f"{self.key} 11 Qualified loan limit for 2024"] = self.d[11]

            # Part II - Deductible Home Mortgage Interest
            self.d[12] = self.d[1] + self.d[2] + self.d[7]

            self.d[13] = interest_paid
            if self.d[11] >= self.d[12]:
                # All interest deductible
                summary_info[f"{self.key} 13 All Interest Deductible for 2024"] = self.d[13]
                return

            self.d[14] = round(self.d[11] / self.d[12], 3)
            self.d[15] = self.d[13] * self.d[14]
            summary_info[f"{self.key} 15 Deductible Home Mortgage Interest for 2024"] = self.d[15]
            self.d[16] = self.d[13] - self.d[15]
            summary_info[f"{self.key} 16 Personal (not Deductible) Interest for 2024"] = self.d[16]
            Form(k_1040sa, get_existing=True).push_to_dict('8_a', self.d[15])

    class CapitalLossCarryoverWorksheet(Worksheet):
        def __init__(self):
            Worksheet.__init__(self, w_capital_loss_carryover, 13)

        def build(self):
            if states_2023 is None:
                return
            self.d[1] = states_2023[k_1040]['15']  # this has been different for many years, fix if
            self.d[2] = max(0., states_2023[k_1040sd]['21'])  # sign flip
            self.d[3] = max(0., self.d[1] + self.d[2])
            self.d[4] = min(self.d[2], self.d[3])
            if states_2023[k_1040sd]['7'] < 0:
                self.d[5] = max(0, -states_2023[k_1040sd]['7'])
                self.d[6] = max(0, states_2023[k_1040sd]['15'])
                self.d[7] = self.d[4] + self.d[6]
                self.d[8] = max(0., self.d[5] - self.d[7])  # enter this in D 6
                # loss as positive number
                summary_info[f"{self.key} 8 Short-term capital loss carryover for 2024"] = self.d[8]
            if states_2023[k_1040sd]['15'] < 0:  # it's ok to repeat
                self.d[9] = max(0., -states_2023[k_1040sd]['15'])
                self.d[10] = max(0., states_2023[k_1040sd]['7'])
                self.d[11] = max(0., self.d[4] - self.d[5])
                self.d[12] = self.d[10] + self.d[11]
                self.d[13] = max(0., self.d[9] - self.d[12])  # enter in D 14
                # loss as positive number
                summary_info[f"{self.key} 13 Long-term capital loss carryover for 2024"] = self.d[13]
            Form(k_1040sd, get_existing=True).push_to_dict('6', self.d[8])
            Form(k_1040sd, get_existing=True).push_to_dict('14', self.d[13])

    class QualifiedDividendsCapitalGainTaxWorksheet(Worksheet):
        def __init__(self):
            Worksheet.__init__(self, w_qualified_dividends_and_capital_gains, 25)

        def build(self):
            self.d[1] = forms_state[k_1040]['15']  # except if foreign earned income
            self.d[2] = forms_state[k_1040]['3_a']
            if d['scheduleD']:
                self.d[3] = max(0, min(forms_state[k_1040sd]['15'], forms_state[k_1040sd]['16']))
            else:
                self.d[3] = forms_state[k_1040]['7']
            self.d[4] = self.d[2] + self.d[3]
            self.d[5] = max(0., self.d[1] - self.d[4])
            self.d[6] = 47_025  # single
            self.d[7] = min(self.d[1], self.d[6])
            self.d[8] = min(self.d[5], self.d[7])
            self.d[9] = self.d[7] - self.d[8]  # taxed 0%
            self.d[10] = min(self.d[1], self.d[4])
            self.d[11] = self.d[9]
            self.d[12] = self.d[11] - self.d[10]
            self.d[13] = 518_900  # single
            self.d[14] = min(self.d[1], self.d[13])
            self.d[15] = self.d[5] + self.d[9]
            self.d[16] = max(0., self.d[14] - self.d[15])
            self.d[17] = min(self.d[12], self.d[16])
            self.d[18] = self.d[17] * 0.15
            self.d[19] = self.d[9] + self.d[17]
            self.d[20] = self.d[10] - self.d[19]
            self.d[21] = self.d[20] * 0.20
            self.d[22] = computation(amount=self.d[5])
            self.d[23] = self.d[18] + self.d[21] + self.d[22]
            self.d[24] = computation(self.d[1])
            self.d[25] = min(self.d[23], self.d[24])
            summary_info[f"{self.key} 25 Tax on all taxable income"] = self.d[25]
            Form(k_1040, get_existing=True).push_to_dict('16', self.d[25])
            # also 2555 if foreign earned income

    class ShouldFill6251Worksheet(Worksheet):
        def __init__(self):
            Worksheet.__init__(self, w_should_fill_6251, 13)
            self.fill6251 = None

        def build(self):
            if k_1040sa in forms_state:
                self.d[1] = forms_state[k_1040]['15_dollar']
                self.d[2] = forms_state[k_1040sa]['7']
                self.d[3] = self.d[1] + self.d[2]
            else:
                self.d[3] = forms_state[k_1040]['13_dollar']
            self.d[4] = forms_state[k_1040s1].get('1_dollar', 0) \
                + forms_state[k_1040s1].get('8z_dollar', 0) \
                if k_1040s1 in forms_state else 0
            self.d[5] = self.d[3] - self.d[4]
            self.d[6] = 81300  # single
            if self.d[5] <= self.d[6]:
                self.fill6251 = False
                return
            self.d[7] = self.d[5] - self.d[6]
            self.d[8] = 578150  # single
            if self.d[5] <= self.d[8]:
                self.d[9] = 0
                self.d[11] = self.d[7]
            else:
                self.d[9] = self.d[5] - self.d[8]
                self.d[10] = min(self.d[9] * 0.25, self.d[6])
                self.d[11] = self.d[7] + self.d[10]
            if self.d[11] >= 220700:  # single
                self.fill6251 = True
                return
            self.d[12] = self.d[11] * 0.26
            self.d[13] = forms_state[k_1040]['11a'] \
                + forms_state[k_1040s2]['46']
            self.fill6251 = (self.d[13] < self.d[12])

    class FormIT201(Form):
        def __init__(self):
            Form.__init__(self, k_it201)

        def build(self):
            self.push_to_dict('1', forms_state[k_1040]['1_z'])
            self.push_to_dict('2', forms_state[k_1040]['2_b'])
            self.push_to_dict('3', forms_state[k_1040]['3_b'])
            self.push_to_dict('7', forms_state[k_1040]['7_value'])
            self.push_sum('17', ['1', '2', '3', '7'])
            self.push_to_dict('19', self.d.get('17', 0) - self.d.get('18', 0))
            self.push_sum('24', ['19', '20', '21', '22', '23'])  # additions
            self.push_sum('32', ['25', '26', '27', '28', '29', '30', '31'])  # subtractions
            self.push_to_dict('33', self.d.get('24', 0) - self.d.get('32', 0))
            if '33' in self.d:
                summary_info[f"{self.key} 33 New York adjusted gross income"] = self.d['33']
            standard_deduction_ny = 8000
            FormIT196().build()
            itemized_deduction_ny = forms_state[k_it196].get('49', 0)
            if itemized_deduction_ny > standard_deduction_ny:
                self.push_to_dict('34', itemized_deduction_ny)
            else:
                self.push_to_dict('34', standard_deduction_ny)
            if '34' in self.d:
                summary_info[f"{self.key} 34 Standard/Itemized deduction"] = self.d['34']
            self.push_to_dict('35', self.d.get('33', 0) - self.d.get('34', 0))
            self.push_to_dict('37', self.d.get('35', 0) - self.d.get('36', 0))
            if '37' in self.d:
                summary_info[f"{self.key} 37 Taxable income"] = self.d['37']
            self.push_sum('38', ['37'])
            computed_tax_ny = computation_ny(amount=self.d.get('38', 0))
            summary_info[f"{self.key} 39 Tax pre-Recapture"] = computed_tax_ny
            recapture_amount_ny = computation_ny_recapture(amount=self.d['38'], gross=self.d['33'])
            computed_tax_ny_full = computed_tax_ny + recapture_amount_ny
            summary_info[f"{self.key} 39 Tax post-Recapture"] = computed_tax_ny_full
            self.push_to_dict('39', computed_tax_ny_full)
            self.push_sum('43', ['40', '41', '42'])
            self.push_to_dict('44', self.d.get('39', 0) - self.d.get('43', 0))
            self.push_sum('46', ['44', '45'])
            if '46' in self.d:
                summary_info[f"{self.key} 46 Total New York State taxes"] = self.d['46']

            self.push_sum('47', ['38'])
            self.push_to_dict('47a', computation_nyc(amount=self.d.get('47', 0)))
            self.push_to_dict('49', max(0, self.d.get('47a', 0) - self.d.get('48', 0)))
            self.push_sum('52', ['49', '50', '51'])
            self.push_to_dict('54', max(0, self.d.get('52', 0) - self.d.get('53', 0)))
            self.push_sum('58', ['54', '54e', '55', '56', '57'])
            if '58' in self.d:
                summary_info[
                    f"{self.key} 58 Total New York City and Yonkers taxes / surcharges and MCTMT"
                ] = self.d['58']
            if '59' in self.d:
                summary_info[f"{self.key} 59 Sales or use tax"] = self.d['59']
            if '60' in self.d:
                summary_info[f"{self.key} 60 Voluntary contributions"] = self.d['60']
            if '61' in self.d:
                summary_info[
                    (f"{self.key} 61 "
                     f"Total New York State, New York City, Yonkers, "
                     f"and sales or use taxes, MCTMT, and voluntary contributions"
                     )] = self.d['61']
            self.push_sum('61', ['46', '58', '59', '60'])

            self.push_sum('62', ['61'])

            # fixed school tax
            taxable_income = self.d['37']
            fixed_school_tax = 63 if taxable_income < 250_000 else 0
            self.push_to_dict('69', fixed_school_tax)
            # school tax rate reduction
            school_tax_reduction = taxable_income * 0.00171 \
                if taxable_income < 12_000 else 21 + (taxable_income - 12_000) * 0.00228 \
                if taxable_income < 500_000 else 0
            self.push_to_dict('69a', school_tax_reduction)

            self.push_to_dict('72', state_tax)
            self.push_to_dict('73', local_tax)

            estimated_payments_ny = 0
            if "EstimatedIncomeTax" in d:
                if "State" in d["EstimatedIncomeTax"]:
                    for line in d["EstimatedIncomeTax"]["State"]:
                        estimated_payments_ny += line["Amount"]
            self.push_to_dict('75', estimated_payments_ny)

            self.push_sum('76', [
                '63', '64', '65', '66', '67', '68', '69', '69a',
                '70', '71', '72', '73', '74', '75',
            ])

            if '76' in self.d:
                summary_info[f"{self.key} 76 Total Payments"] = self.d['76']

            if self.d.get('76', 0) > self.d.get('62', 0):
                self.push_to_dict('77', max(0, self.d.get('76', 0) - self.d.get('62', 0)))
                if '77' in self.d:
                    summary_info[f"{self.key} 77 overpaid"] = self.d['77']
                self.push_to_dict('78', max(0, self.d.get('77', 0) - self.d.get('79', 0)))
                if '78' in self.d:
                    summary_info[f"{self.key} 78 Refund"] = self.d['78']
                self.push_to_dict('78b', max(0, self.d.get('78', 0) - self.d.get('78a', 0)))
            else:
                self.push_to_dict('80', max(0, self.d.get('62', 0) - self.d.get('76', 0)))
                if '80' in self.d:
                    summary_info[f"{self.key} 80 owe"] = self.d['80']

    class FormIT196(Form):
        def __init__(self):
            Form.__init__(self, k_it196)

        def build(self):
            self.push_name_ssn()  # ssn not mapped

            # medical and dental
            # self.push_to_dict('1', 100)
            self.push_to_dict('2', forms_state[k_it201]['19'])
            self.push_to_dict('3', self.d['2'] * 0.10)
            self.push_to_dict('4', max(0, self.d.get('1', 0) - self.d['3']))

            # taxes
            self.push_to_dict('5', state_tax + local_tax)
            property_tax_state = 0
            if "Other" in d:
                for line in d["Other"]:
                    property_tax_state += line.get("CoopStateTaxes", 0)
            self.push_to_dict('7', property_tax_state)

            self.push_sum('9', ['5', '6', '7', '8'])

            # interest
            if w_mortgage_interest_deduction in worksheets:
                # cap is 1mil - need to be applied
                self.push_to_dict('10', worksheets[w_mortgage_interest_deduction][13])
            self.push_sum('15', ['10', '11', '12', '14'])

            # gifts
            self.push_sum('19', ['16', '17', '18'])

            # casualty - theft 20

            # line 40
            NYLine40TotalItemizedDeductionsWorksheet().build()

            # adjustments
            NYLine41ItemizedDeductionsSubtractionsWorksheet().build()
            self.push_to_dict('42', self.d['40'] - self.d['41'])
            # 44
            self.push_sum('45', ['42', '43', '44'])
            # 46
            NYLine46ItemizedDeductionsAdjustmentWorksheet().build()
            self.push_to_dict('47', self.d['45'] - self.d.get('46', 0))
            # 48
            self.push_sum('49', ['47', '48'])

            summary_info[f"{self.key} 49 NY State Itemized Deductions"] = self.d['49']

    class NYLine40TotalItemizedDeductionsWorksheet(Worksheet):
        def __init__(self):
            Worksheet.__init__(self, w_ny_line40_itemized_deductions, 10)

        def build(self):
            line1 = sum(forms_state[k_it196].get(entry, 0) for entry in ['4', '9', '15', '19', '20', '28', '39'])
            line2 = sum(forms_state[k_it196].get(entry, 0) for entry in ['4', '14', '16_a', '20', '29', '30', '37'])
            self.d[1] = line1
            self.d[2] = line2
            if line1 <= line2:
                summary_info[f"{self.key} 10 Total itemized deductions"] = self.d[1]
                Form(k_it196, get_existing=True).push_to_dict('40', self.d[1])
                return
            self.d[3] = self.d[1] - self.d[2]
            self.d[4] = self.d[3] * 0.80
            self.d[5] = forms_state[k_it201]['19']  # federal AGI
            self.d[6] = 330_200  # single
            if self.d[6] >= self.d[5]:
                summary_info[f"{self.key} 10 Total itemized deductions"] = self.d[1]
                Form(k_it196, get_existing=True).push_to_dict('40', self.d[1])
                return
            self.d[7] = self.d[5] - self.d[6]
            self.d[8] = self.d[7] * 0.03
            self.d[9] = min(self.d[4], self.d[8])
            self.d[10] = max(0., self.d[1] - self.d[9])
            summary_info[f"{self.key} 10 Total itemized deductions"] = self.d[10]
            Form(k_it196, get_existing=True).push_to_dict('40', self.d[10])

    class NYLine41ItemizedDeductionsSubtractionsWorksheet(Worksheet):
        def __init__(self):
            Worksheet.__init__(self, w_ny_line41_itemized_deductions_subtractions, 11)

        def build(self):
            federal_agi = forms_state[k_it201]['19']  # federal AGI
            taxes_paid = forms_state[k_it196]['9']
            if federal_agi <= 330_200:
                Form(k_it196, get_existing=True).push_to_dict('41', taxes_paid)
                return

            # self.push_to_dict('41', state_tax + local_tax)
            # ny_agi = forms_state[k_it201]['33']
            self.d[1] = worksheets[w_ny_line40_itemized_deductions][9]
            self.d[2] = worksheets[w_ny_line40_itemized_deductions][3]
            self.d[3] = round(self.d[1] / self.d[2], 4)
            self.d[4] = taxes_paid
            self.d[5] = 0  # B,C
            self.d[6] = self.d[4] + self.d[5]
            self.d[7] = self.d[3] * self.d[6]
            self.d[8] = self.d[6] - self.d[7]
            self.d[9] = 0  # D,E
            self.d[10] = 0  # long-term care
            self.d[11] = self.d[8] + self.d[9] + self.d[10]
            summary_info[f"{self.key} NY Worksheet2 Line 41 - Itemized Deduction Subtractions"] = self.d[11]
            Form(k_it196, get_existing=True).push_to_dict('41', self.d[11])

    class NYLine46ItemizedDeductionsAdjustmentWorksheet(Worksheet):
        def __init__(self):
            Worksheet.__init__(self, w_ny_line46_itemized_deduction_adjustments, 7)

        def build(self):
            ny_agi = forms_state[k_it201]['33']
            # worksheet 3
            self.d[1] = ny_agi
            self.d[2] = 100_000  # single
            self.d[3] = self.d[1] - self.d[2]
            self.d[4] = min(self.d[3], 50_000)
            self.d[5] = round(self.d[4] / 50_000, 4)
            self.d[6] = forms_state[k_it196]['45'] * 0.25
            self.d[7] = self.d[5] * self.d[6]
            summary_info[f"{self.key} NY Worksheet3 Line 46 - Itemized Deduction Adjustment"] = self.d[7]
            Form(k_it196, get_existing=True).push_to_dict('46', self.d[7])

    state_form = FormIT201()

    if d['resident']:
        Form1040().build()  # one other version for NR
    else:
        logger.error("Non-resident not yet implemented")
        # Form1040NR().build()  # one other version for NR

    state_form.build()  # asynchronous for US Treasury Interest

    # forms_state[k_1040]['married_filling_separately'] = True

    return forms_state, worksheets, summary_info
