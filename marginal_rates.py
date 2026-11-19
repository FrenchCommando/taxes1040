"""Compute marginal tax rates by re-running the real tax computation.

For each input category (wages, gains, dividends, deductions, ...) the input is increased by an amount x
and the full computation (computation/forms_core_impl.fill_taxes) is re-run. Total tax is split into
    federal = Form 1040 line 24 (includes AMT, NIIT, Additional Medicare Tax, credits)
    NY state = IT-201 line 46
    NYC = IT-201 line 58 minus the NYC school tax credits (lines 69, 69a)
The computation runs with `exact=True` (no rounding to whole dollars or form-specified decimals), so the
tax is piecewise linear in x. Knots (where the marginal rate changes) are found by recursive subdivision
and placed where the left and right lines meet; jumps (cliffs) are located by bisection. Each knot is
labelled with the thresholds crossed between its two sides (brackets, NIIT, SALT, AMT, itemizing, ...).

Every rule implemented in the computation (AMT, the 2026 OBBBA rules, Schedule 1-A, NY worksheets, ...)
is reflected automatically - there is no separate model of the tax rules here.

Usage:
    python marginal_rates.py                  # default: 2025
    python marginal_rates.py --year 2024
"""
import argparse
import copy
import json
import os

from pipeline.fill_taxes import gather_inputs
from computation.form_worksheet_names import (
    k_1040, k_1040s1a, k_1040sa, k_1040sd, k_1116, k_6251, k_8959, k_8960, k_it196, k_it201,
    w_itemized_limitation, w_qualified_dividends_and_capital_gains, w_salt_deduction,
)
from computation.forms_core_impl import fill_taxes, resolve_config, get_filing_status
from computation.forms_core_2024 import CONFIG_2024
from computation.forms_core_2025 import CONFIG_2025
from computation.forms_core_2026 import CONFIG_2026

YEAR_CONFIGS = {
    '2024': CONFIG_2024,
    '2025': CONFIG_2025,
    '2026': CONFIG_2026,
}

INCOME_HORIZON = 30_000_000  # past the top NY bracket ($25M)
SLOPE_STEP = 100  # width used to measure one-sided slopes
LOCATE_WIDTH = 4 * SLOPE_STEP  # intervals this small holding a slope change are resolved to a knot
SLOPE_TOLERANCE = 5e-5  # slope changes below this are treated as linear
LABEL_OFFSET = 3 * SLOPE_STEP  # thresholds crossed within this distance of a knot label it
COMPONENTS = ('federal', 'ny_state', 'nyc')


# ---------------------------------------------------------------------------------------------------------
# Input changes, one per category: each returns a modified copy of the input data for `amount` more dollars


def _add_wages(data, amount):
    w2 = next(w2 for w2 in data['W2'] if w2.get('Owner', 'self') == 'self')
    w2['Wages'] += amount
    w2['Medicare_wages'] += amount


def _new_1099(data, **fields):
    data.setdefault('1099', []).append({'Institution': 'Marginal', **fields})


def _add_trade(data, amount, long_short, form_code):
    trade = {
        'SalesDescription': 'MARGINAL', 'Shares': '1',
        'DateAcquired': 'VARIOUS', 'DateSold': 'VARIOUS',
        'Proceeds': amount, 'Cost': 0, 'LongShort': long_short, 'FormCode': form_code,
    }
    _new_1099(data, Trades=[trade])


def _add_1256(data, amount):
    # Form 6781 has room for 3 lines: add to an existing aggregate entry when there is one
    entry = next((entry for entry in data.get('1099', []) if 'Realized1256' in entry), None)
    if entry is not None:
        entry['Realized1256'] += amount
    else:
        _new_1099(data, Realized1256=amount)


def _add_hsa(data, amount):
    data['health_savings_account'] = True
    data['health_savings_account_contributions'] = data.get('health_savings_account_contributions', 0) + amount


def _add_mortgage_interest(data, amount):
    data['1098'][0]['Payments'][0]['InterestAmount'] += amount


def _add_foreign_tax(data, amount):
    entry = next(entry for entry in data['1099'] if entry.get('Foreign Tax Paid', 0) > 0)
    entry['Foreign Tax Paid'] += amount


def _categories(base_data, base_metrics, config):
    """(name, note, change(data, amount), horizon) for every category that applies to this input."""
    hsa_room = (
        config['hsa_max_contribution_family']
        if base_data.get('health_savings_account_coverage', 'self') == 'family'
        else config['hsa_max_contribution']
    ) - base_data.get('health_savings_account_contributions', 0) \
        - base_data.get('health_savings_account_employer_contributions', 0)
    agi = base_metrics['agi']
    categories = [
        ('W2 Wages', 'added to the first W2 (wages and Medicare wages)',
         _add_wages, INCOME_HORIZON),
        ('Short-term capital gain', 'new Form 8949 box A trade',
         lambda data, amount: _add_trade(data, amount, long_short='SHORT', form_code='A'), INCOME_HORIZON),
        ('Long-term capital gain', 'new Form 8949 box D trade',
         lambda data, amount: _add_trade(data, amount, long_short='LONG', form_code='D'), INCOME_HORIZON),
        ('Qualified dividends', 'new 1099-DIV, qualified',
         lambda data, amount: _new_1099(data, **{'Qualified Dividends': amount, 'Ordinary Dividends': amount}),
         INCOME_HORIZON),
        ('Ordinary dividends (non-qualified)', 'new 1099-DIV, non-qualified',
         lambda data, amount: _new_1099(data, **{'Ordinary Dividends': amount}), INCOME_HORIZON),
        ('Interest income', 'new 1099-INT',
         lambda data, amount: _new_1099(data, Interest=amount), INCOME_HORIZON),
        ('1256 contracts', 'Form 6781 realized gain (60% long-term / 40% short-term)',
         _add_1256, INCOME_HORIZON),
        ('HSA contribution', f'Form 8889, up to the remaining limit (${max(0, hsa_room):,})',
         _add_hsa, max(0, hsa_room)),
        ('Charitable contributions', 'new cash gift (Schedule A line 11, IT-196 line 16)',
         lambda data, amount: data.setdefault('Charitable', []).append({'Entity': 'Marginal', 'Amount': amount}),
         agi),
        ('Property tax', 'added to Schedule A line 5c / IT-196 line 6',
         lambda data, amount: data.setdefault('Other', []).append({'PropertyTax': amount}), agi),
    ]
    if base_data.get('1098'):
        categories.append(('Mortgage interest', 'added to the first 1098 payment',
                           _add_mortgage_interest, agi))
    if any(entry.get('Foreign Tax Paid', 0) > 0 for entry in base_data.get('1099', [])):
        categories.append(('Foreign tax paid', 'added to the 1099 that reports foreign tax (Form 1116)',
                           _add_foreign_tax, base_metrics['federal']))
    return categories


# ---------------------------------------------------------------------------------------------------------
# Running the computation


def _run(base_data, config, change, amount):
    data = copy.deepcopy(base_data)
    if amount:
        change(data, amount)
    forms_state, worksheets, summary, carryover = fill_taxes(d=data, config=config)
    return forms_state, worksheets, summary, data, config


def _metrics(forms_state, worksheets, summary, data, config):
    f1040 = forms_state[k_1040]
    it201 = forms_state.get(k_it201, {})
    schedule_d = forms_state.get(k_1040sd, {})
    salt_worksheet = worksheets.get(w_salt_deduction, [0] * 11)
    f8960 = forms_state.get(k_8960, {})
    nan = float('nan')  # metrics that don't apply: never cross a threshold
    amt_taxable = forms_state[k_6251].get('6_value', 0) if k_6251 in forms_state else nan
    # Form 6251 Part III: qualified dividends + net capital gain are taxed at the capital gain rates
    net_gain = min(schedule_d['15'], schedule_d['16']) \
        if schedule_d.get('15', 0) > 0 and schedule_d.get('16', 0) > 0 else 0
    amt_gains = f1040.get('3_a', 0) + net_gain
    limitation = worksheets.get(w_itemized_limitation) if k_1040sa in forms_state else None
    gifts = data.get('Charitable', [])
    gift_total = sum(gift.get('Amount', 0) for gift in gifts)
    non_daf_gifts = sum(gift.get('Amount', 0) for gift in gifts if not gift.get('DonorAdvisedFund', False))
    amt_foreign_tax_credit = summary.get(f"{k_6251} 8 AMT foreign tax credit (simplified limitation election)")
    floor_rate = config.get('charitable_agi_floor_rate')
    return dict(
        federal=f1040.get('24', 0),
        ny_state=it201.get('46', 0),
        nyc=it201.get('58', 0) - it201.get('69', 0) - it201.get('69a', 0),
        agi=f1040.get('11', 0),
        taxable_income=f1040.get('15', 0),
        # ordinary part of taxable income: the regular brackets apply to it when gains/dividends stack on top
        ordinary_taxable=worksheets[w_qualified_dividends_and_capital_gains][5]
        if w_qualified_dividends_and_capital_gains in worksheets else f1040.get('15', 0),
        medicare_wages=sum(w2['Medicare_wages'] for w2 in data['W2']),
        net_capital=forms_state.get(k_1040sd, {}).get('16', 0),
        net_long_term=forms_state.get(k_1040sd, {}).get('15', 0),
        net_short_term=forms_state.get(k_1040sd, {}).get('7', 0),
        preferential_income=f1040.get('3_a', 0) > 0 or (
            forms_state.get(k_1040sd, {}).get('15', 0) > 0 and forms_state.get(k_1040sd, {}).get('16', 0) > 0),
        schedule_1a=k_1040s1a in forms_state,
        amti=summary.get(f"{k_6251} 4 Alternative minimum taxable income", 0),
        # Form 6251 line 6 and its ordinary part (the 26%/28% rates apply to it when Part III taxes gains)
        amt_taxable=amt_taxable,
        amt_ordinary=max(0, amt_taxable - amt_gains) if amt_gains > 0 else amt_taxable,
        # IRC 68 worksheet (2026+): income over the 37% bracket start, and that excess minus the itemized
        # deductions (the limitation is 2/37 of the smaller)
        irc68_income_over=limitation[2] - limitation[3] if limitation else nan,
        irc68_over_itemized=limitation[4] - limitation[1] if limitation else nan,
        # 2026+: Schedule A gifts minus the 0.5% AGI floor
        charitable_over_floor=gift_total - f1040.get('11', 0) * floor_rate if floor_rate else nan,
        ny_agi=it201.get('33', 0),
        ny_taxable=it201.get('37', 0),
        federal_agi_ny=it201.get('19', 0),
        itemizing=k_1040sa in forms_state,
        ny_itemizing=k_it196 in forms_state,
        amt=k_6251 in forms_state,
        foreign_tax_limited=any('Excess foreign tax' in key for key in summary),
        amt_foreign_tax_limited=amt_foreign_tax_credit is not None
        and amt_foreign_tax_credit < forms_state.get(k_1116, {}).get('14', 0),
        nonitemizer_charitable_capped=0 < f1040.get('charitable_nonitemizer', 0) < non_daf_gifts,
        salt_capped=salt_worksheet[9] > 0 and salt_worksheet[10] >= salt_worksheet[9],
        # Form 8960 line 15 - line 12: MAGI over the threshold minus net investment income (NIIT = 3.8% of the smaller)
        niit_magi_over_income=f8960.get('15', 0) - f8960.get('12', 0),
        niit=k_8960 in forms_state,
        additional_medicare=forms_state.get(k_8959, {}).get('18', 0) > 0,
    )


class TaxCurve:
    """Tax components as a function of the additional amount, with evaluations cached."""

    def __init__(self, base_data, config, change):
        self.base_data = base_data
        self.config = config
        self.change = change
        self.cache = {}

    def metrics(self, amount):
        amount = max(0, amount)
        if amount not in self.cache:
            self.cache[amount] = _metrics(*_run(self.base_data, self.config, self.change, amount))
        return self.cache[amount]

    def total(self, amount):
        return sum(self.tax(amount))

    def tax(self, amount):
        metrics = self.metrics(amount)
        return tuple(metrics[component] for component in COMPONENTS)

    def slope(self, start, end):
        return tuple((after - before) / (end - start)
                     for before, after in zip(self.tax(start), self.tax(end)))


def _differs(slope_a, slope_b):
    return max(abs(first - second) for first, second in zip(slope_a, slope_b)) > SLOPE_TOLERANCE


def _locate(curve, start, end):
    """Resolve a small interval holding one rate change into (knot, jump). The left and right lines are
    measured just outside the interval and intersected; if they don't meet inside it, the change is a
    jump (cliff), located to the dollar by bisection.
    The measuring windows stop a dollar short of the interval, so a cliff sitting right at `start` or just
    past `end` (e.g. a Schedule 1-A step and the NYC school credit cliff a dollar apart) doesn't skew them."""
    left_end = start - 1 if start > 1 else start
    left = curve.slope(max(0, left_end - SLOPE_STEP), left_end) if start > 0 else curve.slope(start, start + 1)
    right = curve.slope(end + 1, end + 1 + SLOPE_STEP)
    total_left, total_right = sum(left), sum(right)
    base_total, end_total = curve.total(start), curve.total(end)
    # use the component whose slope changes the most
    index = max(range(len(COMPONENTS)), key=lambda each: abs(left[each] - right[each]))
    if abs(left[index] - right[index]) > SLOPE_TOLERANCE:
        tax_start, tax_end = curve.tax(start)[index], curve.tax(end)[index]
        knot = (tax_end - tax_start + left[index] * start - right[index] * end) / (left[index] - right[index])

        def on_lines(point):
            return base_total + total_left * (min(point, knot) - start) + total_right * max(0, point - knot)

        # a kink: the total tax at the intersection lies on both lines, and nothing else (a jump in another
        # component) happens in the interval
        if start <= knot <= end and abs(curve.total(knot) - on_lines(knot)) < 0.5 \
                and abs(end_total - on_lines(end)) < 0.5:
            return round(knot), 0
    # jump: find where the tax leaves the left line
    # gap at `end` between the actual tax and the left line: the jump plus the slope change since the jump
    gap = end_total - base_total - total_left * (end - start)
    low, high = start, end
    while high - low > 1:
        middle = (low + high) // 2
        if abs(curve.total(middle) - base_total - total_left * (middle - start)) > abs(gap) / 2:
            high = middle
        else:
            low = middle
    # the jump itself: the right line and the left line, both evaluated at the located knot
    jump = (end_total - total_right * (end - high)) - (base_total + total_left * (high - start))
    return high, round(jump)


def _pieces(curve, start, end):
    """Split [start, end] into knots: returns a list of (knot, jump)."""
    right_of_start = curve.slope(start, start + SLOPE_STEP)
    left_of_end = curve.slope(end - SLOPE_STEP, end)
    secant = curve.slope(start, end)
    if not _differs(right_of_start, left_of_end) and not _differs(right_of_start, secant):
        return []
    if end - start <= LOCATE_WIDTH:
        return [_locate(curve, start, end)]
    middle = (start + end) // 2
    knots = _pieces(curve, start, middle) + _pieces(curve, middle, end)
    # a rate change exactly at the midpoint is invisible to both halves
    if _differs(curve.slope(middle - SLOPE_STEP, middle), curve.slope(middle, middle + SLOPE_STEP)) \
            and not any(abs(knot - middle) <= LOCATE_WIDTH for knot, jump in knots):
        knots.append(_locate(curve, middle - SLOPE_STEP, middle + SLOPE_STEP))
    return sorted(knots)


def _find_knots(curve, horizon):
    points = [0]
    while points[-1] * 2 + 1_000 < horizon:
        points.append(points[-1] * 2 + 1_000)
    points.append(horizon)
    knots = []
    for start, end in zip(points, points[1:]):
        knots += _pieces(curve, start, end)
        # rate change at a partition point
        if end < horizon and _differs(curve.slope(end - SLOPE_STEP, end), curve.slope(end, end + SLOPE_STEP)):
            knots.append(_locate(curve, end - SLOPE_STEP, end + SLOPE_STEP))
    # the same knot can be found from neighbouring intervals: keep one per position (preferring the one that
    # measured the cliff). Knots a dollar or two apart are separate events (e.g. cliffs in two components)
    # shown as one, with their jumps added.
    by_position = {}
    for knot, jump in knots:
        if knot not in by_position or abs(jump) > abs(by_position[knot]):
            by_position[knot] = jump
    unique = []
    for knot, jump in sorted(by_position.items()):
        if unique and knot - unique[-1][0] <= 2:
            unique[-1] = (unique[-1][0], unique[-1][1] + jump)
        else:
            unique.append((knot, jump))
    return unique


# ---------------------------------------------------------------------------------------------------------
# Labels


def _thresholds(config):
    """(metric, threshold, label, condition) checked on both sides of each knot. A label is only used when
    its condition (a boolean metric) holds on either side, so e.g. SALT thresholds don't label knots of a
    return that takes the standard deduction."""
    thresholds = [('ordinary_taxable', bracket, f'Federal bracket at ordinary taxable income ${bracket:,}', None)
                  for bracket in config['fed_brackets']]
    thresholds += [
        ('taxable_income', 0, 'Federal taxable income reaches zero', None),
        ('ny_taxable', 0, 'NY taxable income reaches zero', None),
        ('taxable_income', config['qualified_div_0pct'],
         f"0% -> 15% capital gain rate at taxable ${config['qualified_div_0pct']:,}", 'preferential_income'),
        ('taxable_income', config['qualified_div_20pct'],
         f"15% -> 20% capital gain rate at taxable ${config['qualified_div_20pct']:,}", 'preferential_income'),
        ('ordinary_taxable', 0, 'Ordinary taxable income reaches zero', 'preferential_income'),
        ('ordinary_taxable', config['qualified_div_0pct'],
         f"Gains start to fill the 0% band (ordinary taxable ${config['qualified_div_0pct']:,})", 'preferential_income'),
        ('ordinary_taxable', config['qualified_div_20pct'],
         f"Gains start to fill the 15% band (ordinary taxable ${config['qualified_div_20pct']:,})", 'preferential_income'),
        ('agi', config['salt_phaseout_start'],
         f"SALT cap phaseout begins (AGI ${config['salt_phaseout_start']:,})", 'itemizing'),
        ('niit_magi_over_income', 0,
         f"NIIT capped at net investment income (MAGI over ${config['niit_threshold']:,} reaches it)", 'niit'),
        ('net_capital', 0, 'Net capital gain/loss crosses zero', None),
        ('net_long_term', 0, 'Net long-term gain/loss crosses zero', None),
        ('net_short_term', 0, 'Net short-term gain/loss crosses zero', None),
        ('net_capital', -config['capital_loss_limit'], f"Capital loss limit (${config['capital_loss_limit']:,})", None),
        ('amti', config['should_fill_6251_phaseout'],
         f"AMT exemption phaseout begins (AMTI ${config['should_fill_6251_phaseout']:,})", 'amt'),
        ('ny_agi', config['ny_itemized_adjustment_start'],
         f"NY itemized deduction adjustment begins (NYAGI ${config['ny_itemized_adjustment_start']:,})", 'ny_itemizing'),
        ('ny_agi', config['ny_itemized_adjustment_start'] + 50_000,
         f"NY itemized deduction adjustment fully phased in (NYAGI ${config['ny_itemized_adjustment_start'] + 50_000:,})",
         'ny_itemizing'),
        ('federal_agi_ny', config['ny_itemized_deduction_threshold'],
         f"NY itemized deductions reduced by 3% of federal AGI over ${config['ny_itemized_deduction_threshold']:,}",
         'ny_itemizing'),
        ('ny_agi', 475_000, 'NY itemized deduction adjustment worksheet 4 (NYAGI $475,000)', 'ny_itemizing'),
        ('ny_agi', 525_000, 'NY itemized deduction adjustment reaches 50% (NYAGI $525,000)', 'ny_itemizing'),
        ('ny_agi', 1_000_000, 'NY itemized deduction limited to 50% of charitable gifts (NYAGI $1M)', 'ny_itemizing'),
        ('ny_agi', 10_000_000, 'NY itemized deduction limited to 25% of charitable gifts (NYAGI $10M)', 'ny_itemizing'),
        ('ny_agi', 107_650, 'NY tax recapture begins (NYAGI $107,650)', None),
        ('ny_agi', 157_650, 'NY tax recapture of the lower brackets complete (NYAGI $157,650)', None),
        ('federal_agi_ny', 250_000, 'NYC fixed school credit ends (income $250,000)', None),
        ('federal_agi_ny', 500_000, 'NYC school rate reduction ends (income $500,000)', None),
    ]
    salt_floor_agi = config['salt_phaseout_start']         + (config['salt_limit'] - config['salt_floor']) / config['salt_phaseout_rate']
    if salt_floor_agi > config['salt_phaseout_start']:
        thresholds.append(('agi', salt_floor_agi,
                           f'SALT cap reaches the ${config["salt_floor"]:,} floor (AGI ${salt_floor_agi:,.0f})', 'itemizing'))
    amt_exemption_gone = config['should_fill_6251_phaseout']         + config['amt_exemption'] / config.get('amt_phaseout_rate', 0.25)
    thresholds.append(('amti', amt_exemption_gone, f'AMT exemption fully phased out (AMTI ${amt_exemption_gone:,.0f})', 'amt'))
    amt_28, zero_band, twenty_band = config['amt_28pct_threshold'], config['qualified_div_0pct'], config['qualified_div_20pct']
    thresholds += [
        ('amt_ordinary', amt_28, f'AMT 26% -> 28% rate (Form 6251 ordinary income ${amt_28:,})', 'amt'),
        ('amt_taxable', zero_band, f'AMT: 0% -> 15% capital gain rate at Form 6251 line 6 ${zero_band:,}', 'amt'),
        ('amt_taxable', twenty_band, f'AMT: 15% -> 20% capital gain rate at Form 6251 line 6 ${twenty_band:,}', 'amt'),
        ('amt_ordinary', zero_band, f'AMT: gains start to fill the 0% band (ordinary ${zero_band:,})', 'amt'),
        ('amt_ordinary', twenty_band, f'AMT: gains start to fill the 15% band (ordinary ${twenty_band:,})', 'amt'),
    ]
    thresholds += [('ny_taxable', bracket, f'NY bracket at taxable ${bracket:,}', None)
                   for bracket in config['ny_brackets']]
    for bracket in config['ny_recapture_brackets']:
        thresholds.append(('ny_agi', bracket, f'NY recapture phase-in begins (NYAGI ${bracket:,})', None))
        thresholds.append(('ny_agi', bracket + 50_000, f'NY recapture phase-in ends (NYAGI ${bracket + 50_000:,})', None))
    thresholds += [('ny_taxable', bracket, f'NYC bracket at taxable ${bracket:,}', None)
                   for bracket in config['nyc_brackets']]
    if config.get('itemized_limitation_rate'):
        top_bracket = config['fed_brackets'][-1]
        thresholds += [
            ('irc68_income_over', 0,
             f'IRC 68 itemized deduction limitation begins (income before deductions over ${top_bracket:,})', 'itemizing'),
            ('irc68_over_itemized', 0,
             f'IRC 68 limitation reaches 2/37 of all itemized deductions (income over ${top_bracket:,} exceeds them)',
             'itemizing'),
        ]
    if config.get('charitable_agi_floor_rate'):
        thresholds.append(('charitable_over_floor', 0,
                           f"Charitable gifts reach the {config['charitable_agi_floor_rate'] * 100:g}% AGI floor", 'itemizing'))
    if config.get('schedule_1a'):
        thresholds += [
            ('agi', config['tips_overtime_phaseout_start'], 'Schedule 1-A tips/overtime phaseout begins', 'schedule_1a'),
            ('agi', config['car_loan_phaseout_start'], 'Schedule 1-A car loan interest phaseout begins', 'schedule_1a'),
            ('agi', config['senior_phaseout_start'], 'Schedule 1-A senior deduction phaseout begins', 'schedule_1a'),
        ]
    return thresholds


FLAG_LABELS = {
    'itemizing': ('switches to itemized deductions', 'switches to the standard deduction'),
    'ny_itemizing': ('NY switches to itemized deductions', 'NY switches to the standard deduction'),
    'amt': ('AMT starts to apply', 'AMT stops applying'),
    'foreign_tax_limited': ('foreign tax credit reaches the Form 1116 limit', 'foreign tax credit below the Form 1116 limit'),
    'amt_foreign_tax_limited': ('AMT foreign tax credit reaches its limit', 'AMT foreign tax credit below its limit'),
    'nonitemizer_charitable_capped': ('non-itemizer charitable deduction reaches its limit',
                                      'non-itemizer charitable deduction below its limit'),
    'salt_capped': ('SALT deduction reaches its cap', 'SALT deduction below its cap'),
    'niit': ('NIIT starts to apply', 'NIIT stops applying'),
    'additional_medicare': ('Additional Medicare Tax starts to apply', 'Additional Medicare Tax stops applying'),
}


def _label(curve, knot, jump, thresholds):
    before, after = curve.metrics(knot - LABEL_OFFSET), curve.metrics(knot + LABEL_OFFSET)
    labels = [label for metric, threshold, label, condition in thresholds
              if min(before[metric], after[metric]) <= threshold < max(before[metric], after[metric])
              and (condition is None or before[condition] or after[condition])]
    labels += [FLAG_LABELS[flag][0 if after[flag] else 1]
               for flag in FLAG_LABELS if before[flag] != after[flag]]
    if jump:
        labels.append(f'cliff: tax {"+" if jump > 0 else "-"}${abs(jump):,}')
    return '; '.join(labels) or 'rate change'


# ---------------------------------------------------------------------------------------------------------
# Segments


def _segment_rates(curve, start, end):
    inside_start = start + min(SLOPE_STEP, (end - start) / 4)
    inside_end = end - min(SLOPE_STEP, (end - start) / 4)
    rates = dict(zip(COMPONENTS, (round(rate, 6) for rate in curve.slope(inside_start, inside_end))))
    rates['combined'] = round(sum(rates[component] for component in COMPONENTS), 6)
    return rates


def _segments(curve, horizon, thresholds):
    if horizon <= 0:
        return []
    knots = _find_knots(curve, horizon)
    bounds = [0] + [knot for knot, jump in knots] + [horizon]
    jumps = dict(knots)
    segments = []
    for start, end in zip(bounds, bounds[1:]):
        if end <= start:
            continue
        segment = dict(**{'from': start, 'to': end if end < horizon else None},
                       rates=_segment_rates(curve, start, end))
        if end < horizon:
            segment['next_knot'] = _label(curve, end, jumps[end], thresholds)
        segments.append(segment)
    # merge neighbours that show the same rates (sub-0.01% drift, e.g. Form 1116 limitation curvature)
    merged = []
    for segment in segments:
        previous = merged[-1] if merged else None
        if previous and not jumps.get(segment['from']) and all(
                round(previous['rates'][component], 4) == round(segment['rates'][component], 4)
                for component in COMPONENTS):
            previous['to'] = segment['to']
            if 'next_knot' in segment:
                previous['next_knot'] = segment['next_knot']
            else:
                previous.pop('next_knot', None)
        else:
            merged.append(segment)
    return _collapse_staircases(curve, merged, jumps, thresholds)


def _same_rates(first, second):
    return all(round(first[component], 4) == round(second[component], 4) for component in COMPONENTS)


# Stepped phaseouts (Schedule 1-A: $200 / $100 less deduction per $1,000 or fraction of income) make a cliff
# every $1,000. A run of at least MIN_STEPS equal cliffs at equal spacing with the same rate in between is
# shown as one segment whose rate averages the steps in. The cliff at the start of the run stays on the
# previous segment.
MIN_STEPS = 3


def _collapse_staircases(curve, segments, jumps, thresholds):
    result = []
    position = 0
    while position < len(segments):
        first = segments[position]
        jump = jumps.get(first['from'], 0)
        # extend while the next segment starts with the same cliff, at the same spacing, with the same rates
        last = position
        while jump and last + 1 < len(segments):
            current, following = segments[last], segments[last + 1]
            if jumps.get(following['from']) != jump or not _same_rates(current['rates'], first['rates']) \
                    or abs((following['from'] - current['from']) - (segments[position + 1]['from'] - first['from'])) > 2:
                break
            last += 1
        steps = last - position  # cliffs inside the collapsed range (at the start of segments position+1..last)
        if steps + 1 < MIN_STEPS:
            result.append(first)
            position += 1
            continue
        # [first.from, end]: `steps` cliffs, the last one at `end`
        end = segments[last]['from']
        rates = dict(zip(COMPONENTS, (round(rate, 6) for rate in curve.slope(first['from'], end))))
        rates['combined'] = round(sum(rates[component] for component in COMPONENTS), 6)
        other_labels = _label(curve, end, 0, thresholds)
        result.append({
            'from': first['from'], 'to': end, 'rates': rates,
            'next_knot': f'stepped phaseout: {steps} steps of {"+" if jump > 0 else "-"}${abs(jump):,} '
                         f'every ${round((end - first["from"]) / steps):,}, averaged into this rate'
                         + ('' if other_labels == 'rate change' else f'; {other_labels}'),
        })
        # the segment after the last cliff keeps its own rate and label
        result.append(segments[last])
        position = last + 1
    return result


def compute_marginal_rates(year, base_data):
    filing_status = get_filing_status(base_data)
    config = YEAR_CONFIGS[year] | dict(exact=True, field_maps=None)
    resolved = resolve_config(config, filing_status)
    thresholds = _thresholds(resolved)
    base_metrics = _metrics(*_run(base_data, config, change=None, amount=0))

    marginal_rates = {}
    for name, note, change, horizon in _categories(base_data, base_metrics, resolved):
        curve = TaxCurve(base_data=base_data, config=config, change=change)
        marginal_rates[name] = dict(note=note, segments=_segments(curve, round(horizon), thresholds))

    baseline_keys = ['agi', 'taxable_income', 'itemizing', 'amt', 'ny_agi', 'ny_taxable', 'ny_itemizing',
                     'federal', 'ny_state', 'nyc']
    return dict(
        year=year,
        filing_status=filing_status,
        method='numeric (re-runs the tax computation, exact mode)',
        baseline={key: base_metrics[key] for key in baseline_keys},
        marginal_rates=marginal_rates,
    )


# ---------------------------------------------------------------------------------------------------------
# Output


def _format_amount(amount):
    return '...' if amount is None else f'${amount:,.0f}'


def format_results(results):
    """Format results as a list of lines for display and text file output."""
    base = results['baseline']
    lines = [
        f"Marginal tax rates (numeric, year={results['year']}, {results['filing_status']})",
        f"Baseline: AGI=${base['agi']:,.0f}, taxable=${base['taxable_income']:,.0f}, "
        f"{'itemizing' if base['itemizing'] else 'standard deduction'}, AMT={'yes' if base['amt'] else 'no'}, "
        f"NY AGI=${base['ny_agi']:,.0f}, NY taxable=${base['ny_taxable']:,.0f}",
        f"Tax: federal=${base['federal']:,.0f}, NY state=${base['ny_state']:,.0f}, NYC=${base['nyc']:,.0f}",
        '',
    ]
    for name, category in results['marginal_rates'].items():
        lines.append(f"  {name}:  ({category['note']})")
        segments = category['segments']
        if not segments:
            lines += ['    (no room)', '']
            continue
        range_strs = [f"{_format_amount(segment['from'])} - {_format_amount(segment['to'])}" for segment in segments]
        col_width = max(len(range_str) for range_str in range_strs) + 2
        lines.append(f"    {'Additional':<{col_width}} {'Federal':>10} {'NY State':>10} {'NYC':>10} {'Combined':>10}")
        for segment, range_str in zip(segments, range_strs):
            rates = segment['rates']
            line = (f"    {range_str:<{col_width}} {rates['federal']:>9.2%} {rates['ny_state']:>9.2%}"
                    f" {rates['nyc']:>9.2%} {rates['combined']:>9.2%}")
            if 'next_knot' in segment:
                line += f"  <- {segment['next_knot']}"
            lines.append(line)
        lines.append('')
    return lines


def main():
    parser = argparse.ArgumentParser(description='Compute marginal tax rates')
    parser.add_argument('--year', type=str, default='2025', help='Tax year (default: 2025)')
    args = parser.parse_args()

    results = compute_marginal_rates(year=args.year, base_data=gather_inputs(args.year))

    output_dir = os.path.join('output', args.year)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'marginal_rates.json')
    with open(output_path, 'w') as fout:
        json.dump(results, fout, indent=4)

    lines = format_results(results)
    print('\n'.join(lines))
    txt_path = os.path.join(output_dir, 'marginal_rates.txt')
    with open(txt_path, 'w') as fout:
        fout.write('\n'.join(lines) + '\n')
    print(f"\nSaved to {output_path} and {txt_path}")


if __name__ == '__main__':
    main()
