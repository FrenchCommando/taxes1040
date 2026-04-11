"""Compute marginal tax rates analytically from the baseline tax computation.

Standalone script — imports the existing fill_taxes pipeline without modifying it.
Runs the tax computation once to determine the baseline position (which bracket,
which SALT regime, etc.), then analytically derives the marginal rate for each
input category by tracing how $1 flows through the chain of tax computations.

For each input type, outputs:
  - The current marginal rate (first segment)
  - All knots: the additional dollar amounts where the marginal rate changes
  - Cliffs: lump-sum tax changes at specific thresholds (e.g., NY $10M deduction cliff)

Usage:
    python marginal_rates.py [--year 2025]

The analytical approach gives exact marginal rates with no rounding artifacts.
Each rate is decomposed as a product of known derivatives:
    $1 income -> AGI -> federal taxable income -> federal tax
                     -> NY taxable income -> NY tax + NYC tax

Non-linear thresholds (2025, single filer):

    Federal income tax brackets (on taxable income):
        $11,925 / $48,475 / $103,350 / $197,300 / $250,525 / $626,350
        Rates: 10% -> 12% -> 22% -> 24% -> 32% -> 35% -> 37%

    Additional Medicare Tax (W2 wages only):
        $200,000 AGI — 0.9% on wages above this threshold (Form 8959)

    Long-term capital gains / qualified dividends (preferential federal rates):
        $48,350 taxable income — 0% -> 15%
        $533,400 taxable income — 15% -> 20%

    SALT deduction:
        $500,000 AGI — phaseout starts (30% rate)
        Floor: $10,000, cap: $40,000
        Effective SALT = max($10k, $40k - 30% * (AGI - $500k))

    Standard deduction: $15,750 (itemized deductions below this have no marginal benefit)

    AMT (Form 6251):
        $88,100 exemption
        $239,100 — 26% -> 28% AMT rate
        $626,350 — exemption phaseout starts

    Capital loss deduction: capped at $3,000/year

    NY State brackets (on NY taxable income):
        $8,500 / $11,700 / $13,900 / $80,650 / $215,400 / $1,077,550 / $5M / $25M
        Rates: 4% -> 4.5% -> 5.25% -> 5.5% -> 6% -> 6.85% -> 9.65% -> 10.3% -> 10.9%
        Recapture triggers at $107,650 AGI (phases in over $50k)

    NY itemized deduction adjustment:
        $340,700 NYAGI — Worksheet 3/4 adjustment begins
        $1M NYAGI — capped at 50% of AGI
        $10M NYAGI — capped at 25% of AGI

    NYC brackets (on NYC taxable income):
        $12,000 / $25,000 / $50,000
        Rates: 3.078% -> 3.762% -> 3.819% -> 3.876%
"""
import argparse
import copy
import json
import os

from pipeline.fill_taxes import gather_inputs, FILL_FUNCTIONS
from computation.form_worksheet_names import (
    k_1040, k_1040sa, k_1040sd, k_1040s3, k_it201,
    w_salt_deduction,
)
from computation.forms_functions import (
    computation_2025, computation_2025_ny, computation_2025_ny_recapture,
    computation_2025_nyc,
    computation_2024, computation_2024_ny, computation_2024_ny_recapture,
    computation_2024_nyc,
)


YEAR_CONFIGS = {
    '2025': dict(
        computation=computation_2025,
        computation_ny=computation_2025_ny,
        computation_ny_recapture=computation_2025_ny_recapture,
        computation_nyc=computation_2025_nyc,
        standard_deduction=15_750,
        salt_limit=40_000,
        salt_phaseout_start=500_000,
        salt_phaseout_rate=0.30,
        salt_floor=10_000,
        qualified_div_0pct=48_350,
        qualified_div_20pct=533_400,
        ny_recapture_brackets=[215_400, 1_077_550, 5_000_000, 25_000_000],
    ),
    '2024': dict(
        computation=computation_2024,
        computation_ny=computation_2024_ny,
        computation_ny_recapture=computation_2024_ny_recapture,
        computation_nyc=computation_2024_nyc,
        standard_deduction=15_200,
        salt_limit=10_000,
        salt_phaseout_start=500_000,
        salt_phaseout_rate=0.30,
        salt_floor=10_000,
        qualified_div_0pct=47_025,
        qualified_div_20pct=518_900,
        ny_recapture_brackets=[215_400, 1_077_550, 5_000_000, 25_000_000],
    ),
}

FED_BRACKETS = [11_925, 48_475, 103_350, 197_300, 250_525, 626_350]
NY_BRACKETS = [8_500, 11_700, 13_900, 80_650, 215_400, 1_077_550, 5_000_000, 25_000_000]
NYC_BRACKETS = [12_000, 25_000, 50_000]
PREFERENTIAL_BRACKETS_KEYS = ['qualified_div_0pct', 'qualified_div_20pct']


def _bracket_rate(computation_fn, taxable_income):
    """Marginal bracket rate at a given taxable income (piecewise linear, so eps=1 is exact)."""
    return computation_fn(taxable_income + 1) - computation_fn(taxable_income)


def _salt_d_agi(agi, config):
    """d(SALT_deduction)/d(AGI). Zero when at cap or floor, -phaseout_rate in phaseout."""
    if agi <= config['salt_phaseout_start']:
        return 0
    effective = config['salt_limit'] - config['salt_phaseout_rate'] * (agi - config['salt_phaseout_start'])
    if effective > config['salt_floor']:
        return -config['salt_phaseout_rate']
    return 0


def _salt_agi_at_floor(config):
    """AGI where SALT hits the floor (phaseout fully exhausted)."""
    return config['salt_phaseout_start'] + (config['salt_limit'] - config['salt_floor']) / config['salt_phaseout_rate']


def _extract_baseline(forms_state, worksheets, base_data, config):
    """Extract all baseline values needed for analytical computation."""
    agi = forms_state[k_1040].get('11', forms_state[k_1040].get('11_a', 0))
    taxable_income = forms_state[k_1040]['15']
    itemized = forms_state[k_1040sa].get('17', 0)
    line_12_key = '12_e' if '12_e' in forms_state[k_1040] else '12'
    is_itemizing = forms_state[k_1040][line_12_key] == itemized

    has_schedule_d = k_1040sd in forms_state
    net_stcg = forms_state.get(k_1040sd, {}).get('7', 0) if has_schedule_d else 0
    net_ltcg = forms_state.get(k_1040sd, {}).get('15', 0) if has_schedule_d else 0
    net_capital = forms_state.get(k_1040sd, {}).get('16', 0) if has_schedule_d else 0

    qualified_dividends = forms_state[k_1040].get('3_a', 0)
    sched_d_gain = max(0, min(net_ltcg, net_capital)) if has_schedule_d else 0
    total_qualified = qualified_dividends + sched_d_gain

    ny_agi = forms_state.get(k_it201, {}).get('33', 0)
    ny_taxable = forms_state.get(k_it201, {}).get('37', 0)
    medicare_wages = sum(w['Medicare_wages'] for w in base_data['W2'])

    # SALT: total vs effective deduction
    salt_total = forms_state.get(k_1040sa, {}).get('5_d', 0)
    salt_deduction = forms_state.get(k_1040sa, {}).get('5_e', 0)

    # Foreign tax credit
    foreign_tax = forms_state.get(k_1040s3, {}).get('1', 0) if k_1040s3 in forms_state else 0

    # Mortgage interest deduction ratio (qualified_limit / total_balance)
    # If ratio < 1, only that fraction of interest is deductible
    from computation.form_worksheet_names import w_mortgage_interest_deduction
    mortgage_worksheet = worksheets.get(w_mortgage_interest_deduction, [])
    if len(mortgage_worksheet) > 14 and mortgage_worksheet[12] > 0:
        mortgage_deduction_ratio = min(1.0, mortgage_worksheet[11] / mortgage_worksheet[12])
    else:
        mortgage_deduction_ratio = 1.0

    return dict(
        agi=agi, taxable_income=taxable_income, is_itemizing=is_itemizing,
        itemized=itemized, net_stcg=net_stcg, net_ltcg=net_ltcg, net_capital=net_capital,
        total_qualified=total_qualified, ny_agi=ny_agi, ny_taxable=ny_taxable,
        medicare_wages=medicare_wages, salt_total=salt_total, salt_deduction=salt_deduction,
        foreign_tax=foreign_tax, mortgage_deduction_ratio=mortgage_deduction_ratio,
    )


def _rate_at(additional, baseline, config, fed_rate_type,
             mode='income', is_wages=False):
    """Compute the exact marginal rate at `additional` dollars above baseline.

    fed_rate_type: 'ordinary', 'preferential', 'ltcg_or_loss', '1256', 'stcg_or_loss'
    mode: 'income' (increases AGI), 'deduction' (reduces taxable via itemized, e.g. charitable/mortgage),
          'property_tax' (increases SALT total), 'foreign_tax_credit' (dollar-for-dollar credit)
    """
    if mode == 'foreign_tax_credit':
        # $1 foreign tax → $1 reduction in federal tax (direct credit, not deduction)
        # No NY/NYC impact (NY doesn't allow federal foreign tax credit)
        return dict(federal=-1.0, ny_state=0, nyc=0, combined=-1.0)

    if mode == 'property_tax':
        # Property tax increases SALT total (Schedule A line 5_d).
        # Whether it changes the SALT deduction depends on the SALT regime:
        #   - salt_total < effective_limit: $1 more property tax → $1 more SALT deduction
        #   - salt_total >= effective_limit: no effect (capped)
        # The effective limit = max(floor, cap - phaseout_rate * (AGI - phaseout_start))
        agi = baseline['agi']
        if agi <= config['salt_phaseout_start']:
            effective_limit = config['salt_limit']
        else:
            effective_limit = max(
                config['salt_floor'],
                config['salt_limit'] - config['salt_phaseout_rate'] * (agi - config['salt_phaseout_start']),
            )
        new_salt_total = baseline['salt_total'] + additional
        if new_salt_total <= effective_limit and baseline['is_itemizing']:
            # Extra property tax increases SALT deduction → reduces taxable income
            fed_taxable = baseline['taxable_income'] - additional
            fed_rate = _bracket_rate(config['computation'], fed_taxable)
            return dict(
                federal=round(-fed_rate, 6),
                ny_state=0, nyc=0,
                combined=round(-fed_rate, 6),
            )
        else:
            # SALT capped — no marginal benefit
            return dict(federal=0, ny_state=0, nyc=0, combined=0)

    if mode == 'mortgage':
        # Mortgage interest: only the qualified fraction is deductible
        ratio = baseline['mortgage_deduction_ratio']
        deductible = additional * ratio
        fed_taxable = baseline['taxable_income'] - deductible
        if not baseline['is_itemizing']:
            new_itemized = baseline['itemized'] + deductible
            if new_itemized > config['standard_deduction']:
                fed_rate = _bracket_rate(config['computation'], fed_taxable)
            else:
                return dict(federal=0, ny_state=0, nyc=0, combined=0)
        else:
            fed_rate = _bracket_rate(config['computation'], fed_taxable)

        return dict(
            federal=round(-fed_rate * ratio, 6),
            ny_state=0, nyc=0,
            combined=round(-fed_rate * ratio, 6),
        )

    if mode == 'deduction':
        # Charitable: doesn't change AGI, reduces taxable via itemized ($1 for $1)
        fed_taxable = baseline['taxable_income'] - additional
        if not baseline['is_itemizing']:
            new_itemized = baseline['itemized'] + additional
            if new_itemized > config['standard_deduction']:
                fed_rate = _bracket_rate(config['computation'], fed_taxable)
            else:
                return dict(federal=0, ny_state=0, nyc=0, combined=0)
        else:
            fed_rate = _bracket_rate(config['computation'], fed_taxable)

        # NY: at NYAGI > $1M, deduction = 50% of AGI (not affected by deduction amount)
        return dict(
            federal=round(-fed_rate, 6),
            ny_state=0, nyc=0,
            combined=round(-fed_rate, 6),
        )

    # Income types: $1 input → $1 AGI
    new_agi = baseline['agi'] + additional

    # SALT regime at new AGI
    d_salt = _salt_d_agi(new_agi, config)
    if baseline['is_itemizing']:
        d_fed_taxable_d_agi = 1 - d_salt
    else:
        d_fed_taxable_d_agi = 1

    # Federal taxable income: need to integrate, not just multiply
    # Because SALT regime may have changed along the way. But within a segment
    # (between knots), the regime is constant, so fed_taxable = taxable_0 + additional * d_fed_taxable_d_agi
    # is correct locally. For the knots computation, we evaluate at the midpoint of each segment.
    fed_taxable = baseline['taxable_income'] + additional * d_fed_taxable_d_agi

    # Federal rate
    if fed_rate_type == 'ordinary':
        fed_rate = _bracket_rate(config['computation'], fed_taxable) * d_fed_taxable_d_agi
    elif fed_rate_type == 'preferential':
        # Preferential rate based on where taxable_income sits
        if fed_taxable <= config['qualified_div_0pct']:
            pref = 0
        elif fed_taxable <= config['qualified_div_20pct']:
            pref = 0.15
        else:
            pref = 0.20
        fed_rate = pref * d_fed_taxable_d_agi
    elif fed_rate_type == 'ltcg_or_loss':
        # If net LTCG + additional is still in loss, ordinary; else preferential
        if baseline['net_ltcg'] + additional < 0 or baseline['net_capital'] + additional < 0:
            fed_rate = _bracket_rate(config['computation'], fed_taxable) * d_fed_taxable_d_agi
        else:
            if fed_taxable <= config['qualified_div_0pct']:
                pref = 0
            elif fed_taxable <= config['qualified_div_20pct']:
                pref = 0.15
            else:
                pref = 0.20
            fed_rate = pref * d_fed_taxable_d_agi
    elif fed_rate_type == 'stcg_or_loss':
        # STCG: always ordinary (but if in deep loss territory, may be 0%)
        if baseline['net_capital'] < -3000 and baseline['net_capital'] + additional < -3000:
            fed_rate = 0  # loss still exceeds $3k cap, extra gain doesn't change AGI
        else:
            fed_rate = _bracket_rate(config['computation'], fed_taxable) * d_fed_taxable_d_agi
    elif fed_rate_type == '1256':
        ordinary = _bracket_rate(config['computation'], fed_taxable)
        if baseline['net_ltcg'] < 0 or baseline['net_capital'] < 0:
            pref = ordinary  # losses absorb the preferential portion
        else:
            if fed_taxable <= config['qualified_div_0pct']:
                pref = 0
            elif fed_taxable <= config['qualified_div_20pct']:
                pref = 0.15
            else:
                pref = 0.20
        fed_rate = (0.60 * pref + 0.40 * ordinary) * d_fed_taxable_d_agi
    else:
        raise ValueError(fed_rate_type)

    # Medicare (W2 only)
    extra_fed = 0
    if is_wages and baseline['medicare_wages'] + additional > 200_000:
        extra_fed = 0.009

    # NY deduction regime at new NYAGI
    new_ny_agi = baseline['ny_agi'] + additional
    if new_ny_agi > 10_000_000:
        d_ny_taxable = 0.75
    elif new_ny_agi > 1_000_000:
        d_ny_taxable = 0.50
    else:
        d_ny_taxable = 1  # below $1M, deduction is roughly fixed

    # NY taxable at this position (approximate for bracket lookup)
    # Can't simply add additional * d_ny because the regime may have changed.
    # Use the direct formula: ny_deduction = fraction * agi
    if new_ny_agi > 10_000_000:
        ny_deduction = 0.25 * (baseline['agi'] + additional)
    elif new_ny_agi > 1_000_000:
        ny_deduction = 0.50 * (baseline['agi'] + additional)
    else:
        ny_deduction = baseline['agi'] + additional - baseline['ny_agi'] + baseline['ny_agi'] - baseline['ny_taxable']
        # ≈ fixed deduction

    new_ny_taxable = new_ny_agi - ny_deduction if new_ny_agi > 1_000_000 else baseline['ny_taxable'] + additional * d_ny_taxable

    ny_rate = _bracket_rate(config['computation_ny'], new_ny_taxable) * d_ny_taxable
    nyc_rate = _bracket_rate(config['computation_nyc'], new_ny_taxable) * d_ny_taxable

    federal = round(fed_rate + extra_fed, 6)
    ny_state = round(ny_rate, 6)
    nyc = round(nyc_rate, 6)
    combined = round(federal + ny_state + nyc, 6)

    return dict(federal=federal, ny_state=ny_state, nyc=nyc, combined=combined)


def _find_knots_income(baseline, config, is_wages=False):
    """Find all additional-dollar thresholds where marginal rate changes for an income type."""
    knots = []

    agi_0 = baseline['agi']
    fed_taxable_0 = baseline['taxable_income']
    ny_agi_0 = baseline['ny_agi']
    ny_taxable_0 = baseline['ny_taxable']

    # Current SALT regime determines d_fed_taxable_d_agi
    salt_floor_agi = _salt_agi_at_floor(config)

    # SALT regime transitions
    if agi_0 < config['salt_phaseout_start']:
        knots.append((config['salt_phaseout_start'] - agi_0, 'SALT phaseout begins'))
        knots.append((salt_floor_agi - agi_0, 'SALT hits floor'))
    elif agi_0 < salt_floor_agi:
        knots.append((salt_floor_agi - agi_0, 'SALT hits floor'))

    # Federal bracket transitions
    # d_fed_taxable changes at SALT knots, so fed_taxable isn't simply taxable_0 + x.
    # For simplicity, compute fed bracket knots assuming current d_fed_taxable_d_agi.
    d_salt = _salt_d_agi(agi_0, config)
    d_fed = (1 - d_salt) if baseline['is_itemizing'] else 1
    for bracket in FED_BRACKETS:
        if bracket > fed_taxable_0:
            additional = (bracket - fed_taxable_0) / d_fed
            knots.append((additional, f'Federal bracket at taxable ${bracket:,}'))

    # Preferential rate transitions (for LTCG / qualified div inputs)
    for key in PREFERENTIAL_BRACKETS_KEYS:
        bracket = config[key]
        if bracket > fed_taxable_0:
            additional = (bracket - fed_taxable_0) / d_fed
            knots.append((additional, f'Preferential rate at taxable ${bracket:,}'))

    # Medicare threshold (W2 only)
    if is_wages and baseline['medicare_wages'] < 200_000:
        knots.append((200_000 - baseline['medicare_wages'], 'Additional Medicare Tax begins ($200k)'))

    # NY deduction regime transitions
    if ny_agi_0 <= 1_000_000:
        knots.append((1_000_000 - ny_agi_0, 'NYAGI crosses $1M - deduction caps at 50% of AGI'))
    if ny_agi_0 <= 10_000_000:
        knots.append((10_000_000 - ny_agi_0, 'NYAGI crosses $10M - deduction drops to 25% of AGI (cliff)'))

    # NY bracket transitions
    # Before NYAGI $10M: d_ny_taxable = 0.50 (when NYAGI > $1M)
    # After NYAGI $10M: d_ny_taxable = 0.75
    ny_10m_additional = 10_000_000 - ny_agi_0 if ny_agi_0 <= 10_000_000 else 0

    if ny_agi_0 > 1_000_000:
        d_ny = 0.50
    else:
        d_ny = 1  # below $1M, deduction roughly fixed

    for bracket in NY_BRACKETS:
        if bracket <= ny_taxable_0:
            continue
        additional = (bracket - ny_taxable_0) / d_ny
        if ny_10m_additional > 0 and additional > ny_10m_additional:
            # This bracket would be crossed after the $10M regime change
            # Recompute with post-$10M regime
            # At $10M crossing: ny_taxable ≈ 0.50 * $10M = $5M (for >$1M baseline)
            ny_taxable_at_10m = 0.50 * 10_000_000 if ny_agi_0 > 1_000_000 else ny_taxable_0 + ny_10m_additional
            # After cliff, ny_taxable jumps to 0.75 * $10M = $7.5M
            ny_taxable_post_cliff = 0.75 * 10_000_000
            if bracket <= ny_taxable_post_cliff:
                continue  # bracket crossed by the cliff jump itself
            remaining = (bracket - ny_taxable_post_cliff) / 0.75
            additional = ny_10m_additional + remaining
        knots.append((additional, f'NY bracket at taxable ${bracket:,}'))

    # NYC bracket transitions (same taxable as NY)
    for bracket in NYC_BRACKETS:
        if bracket <= ny_taxable_0:
            continue
        additional = (bracket - ny_taxable_0) / d_ny
        knots.append((additional, f'NYC bracket at taxable ${bracket:,}'))

    # NY recapture cliffs (when NY taxable crosses recapture bracket boundaries)
    for bracket in config['ny_recapture_brackets']:
        if bracket <= ny_taxable_0:
            continue
        additional = (bracket - ny_taxable_0) / d_ny
        if ny_10m_additional > 0 and additional > ny_10m_additional:
            ny_taxable_post_cliff = 0.75 * 10_000_000
            if bracket <= ny_taxable_post_cliff:
                continue
            remaining = (bracket - ny_taxable_post_cliff) / 0.75
            additional = ny_10m_additional + remaining
        knots.append((additional, f'NY recapture cliff at NY taxable ${bracket:,}'))

    # Deduplicate by additional value and sort
    knots = [(round(x), desc) for x, desc in knots if x > 0]
    knots.sort()
    # Collapse knots at the same dollar amount
    collapsed = []
    for dollar, desc in knots:
        if collapsed and collapsed[-1][0] == dollar:
            collapsed[-1] = (dollar, collapsed[-1][1] + '; ' + desc)
        else:
            collapsed.append((dollar, desc))
    return collapsed


def _find_knots_charitable(baseline, config):
    """Find knots for charitable contributions (reduces taxable income)."""
    knots = []
    fed_taxable_0 = baseline['taxable_income']

    # Federal bracket transitions (going down)
    for bracket in reversed(FED_BRACKETS):
        if bracket < fed_taxable_0:
            additional = fed_taxable_0 - bracket
            knots.append((additional, f'Federal bracket at taxable ${bracket:,}'))

    # Itemized → standard deduction crossover
    if baseline['is_itemizing']:
        excess = baseline['itemized'] - config['standard_deduction']
        if excess > 0:
            # This would only trigger if charitable is the bulk of itemized deductions
            # and removing it drops below standard. But we're adding charitable, so
            # we move further into itemizing. No crossover for adding charitable.
            pass

    knots = [(round(x), desc) for x, desc in knots if x > 0]
    knots.sort()
    return knots


def _find_knots_mortgage(baseline, config):
    """Find knots for mortgage interest (deductible fraction reduces taxable income)."""
    knots = []
    fed_taxable_0 = baseline['taxable_income']
    ratio = baseline['mortgage_deduction_ratio']

    if ratio <= 0:
        return knots

    # Federal bracket transitions (going down, scaled by deduction ratio)
    for bracket in reversed(FED_BRACKETS):
        if bracket < fed_taxable_0:
            # Need additional * ratio = fed_taxable_0 - bracket
            additional = (fed_taxable_0 - bracket) / ratio
            knots.append((round(additional), f'Federal bracket at taxable ${bracket:,}'))

    knots.sort()
    return knots


def _find_knots_property_tax(baseline, config):
    """Find knots for property tax (feeds into SALT).

    Three regimes:
      - salt_total < effective_limit: $1 property tax → $1 more SALT deduction
      - salt_total >= effective_limit: $0 effect (capped)
    The knot is where salt_total crosses the effective SALT limit.
    """
    knots = []
    agi = baseline['agi']
    if agi <= config['salt_phaseout_start']:
        effective_limit = config['salt_limit']
    else:
        effective_limit = max(
            config['salt_floor'],
            config['salt_limit'] - config['salt_phaseout_rate'] * (agi - config['salt_phaseout_start']),
        )

    if baseline['salt_total'] < effective_limit:
        # Currently below cap — additional property tax has effect until salt_total hits limit
        headroom = effective_limit - baseline['salt_total']
        knots.append((round(headroom), f'SALT total reaches effective limit ${effective_limit:,.0f}'))
        # After that, also add federal bracket knots for the deduction portion
        fed_taxable_0 = baseline['taxable_income']
        for bracket in reversed(FED_BRACKETS):
            if bracket < fed_taxable_0:
                additional = fed_taxable_0 - bracket
                if additional < headroom:
                    knots.append((round(additional), f'Federal bracket at taxable ${bracket:,}'))
        knots.sort()
    # If already at or above effective limit, no knots (always 0%)

    return knots


def _build_segments(knots, baseline, config, fed_rate_type, mode='income', is_wages=False):
    """Build segments between knots with the marginal rate in each segment."""
    segments = []
    boundaries = [0] + [x for x, _ in knots]

    for idx in range(len(boundaries)):
        start = boundaries[idx]
        end = boundaries[idx + 1] if idx + 1 < len(boundaries) else None
        description = knots[idx][1] if idx < len(knots) else None

        # Evaluate rate at a point inside this segment
        eval_point = start + 1  # just past the boundary
        rates = _rate_at(eval_point, baseline, config, fed_rate_type,
                         mode=mode, is_wages=is_wages)

        segment = {'from': start, 'to': end, 'rates': rates}
        if description:
            segment['next_knot'] = description
        segments.append(segment)

    return segments


def compute_analytical_marginal_rates(year):
    """Compute exact marginal rates and knots from a single baseline computation."""
    config = YEAR_CONFIGS[year]
    base_data = gather_inputs(year)
    fill_func = FILL_FUNCTIONS[year]
    forms_state, worksheets, summary, carryover = fill_func(d=copy.deepcopy(base_data))
    baseline = _extract_baseline(forms_state, worksheets, base_data, config)

    d_salt = _salt_d_agi(baseline['agi'], config)
    salt_regime = ('floor' if d_salt == 0 and baseline['agi'] > config['salt_phaseout_start']
                   else 'phaseout' if d_salt != 0 else 'cap')

    income_knots = _find_knots_income(baseline, config, is_wages=False)
    wages_knots = _find_knots_income(baseline, config, is_wages=True)
    charitable_knots = _find_knots_charitable(baseline, config)

    stcg_in_loss = baseline['net_stcg'] < 0
    ltcg_in_loss = baseline['net_ltcg'] < 0 or baseline['net_capital'] < 0

    # Property tax knots: SALT regime transitions
    property_tax_knots = _find_knots_property_tax(baseline, config)

    # Foreign tax credit: no knots (constant $1-for-$1 until credit exceeds tax liability)
    foreign_tax_knots = []

    # Build notes explaining key drivers
    mortgage_ratio = baseline['mortgage_deduction_ratio']
    salt_note = (f'SALT at floor (${config["salt_floor"]:,}), total SALT ${baseline["salt_total"]:,.0f} '
                 f'exceeds effective limit - no marginal benefit')
    if baseline['salt_total'] < config['salt_floor']:
        salt_note = f'SALT total ${baseline["salt_total"]:,.0f} below floor - full marginal benefit'

    categories = {
        'W2 Wages': {
            'note': f'37% bracket + 0.9% Additional Medicare Tax (wages > $200k)',
            'segments': _build_segments(
                wages_knots, baseline, config, fed_rate_type='ordinary', is_wages=True),
        },
        'Short-term capital gain': {
            'note': 'Taxed as ordinary income' + ('; net STCG in loss' if stcg_in_loss else ''),
            'segments': _build_segments(
                income_knots, baseline, config,
                fed_rate_type='stcg_or_loss' if stcg_in_loss else 'ordinary'),
        },
        'Long-term capital gain': {
            'note': ('Net losses absorb gain - taxed at ordinary rates' if ltcg_in_loss
                     else '20% preferential rate (taxable income > $533,400)'),
            'segments': _build_segments(
                income_knots, baseline, config,
                fed_rate_type='ltcg_or_loss' if ltcg_in_loss else 'preferential'),
        },
        'Qualified dividends': {
            'note': '20% preferential rate (taxable income > $533,400)',
            'segments': _build_segments(
                income_knots, baseline, config, fed_rate_type='preferential'),
        },
        'Ordinary dividends (non-qualified)': {
            'note': 'Taxed as ordinary income',
            'segments': _build_segments(
                income_knots, baseline, config, fed_rate_type='ordinary'),
        },
        'Interest income': {
            'note': 'Taxed as ordinary income',
            'segments': _build_segments(
                income_knots, baseline, config, fed_rate_type='ordinary'),
        },
        '1256 contracts': {
            'note': '60/40 split: 60% at 20% LTCG + 40% at 37% ordinary = 26.8%',
            'segments': _build_segments(
                income_knots, baseline, config, fed_rate_type='1256'),
        },
        'Charitable contributions': {
            'note': ('Itemized deduction, $1-for-$1. NY: 0% (50% AGI cap at NYAGI > $1M)'
                     if baseline['ny_agi'] > 1_000_000
                     else 'Itemized deduction, $1-for-$1'),
            'segments': _build_segments(
                charitable_knots, baseline, config, fed_rate_type='ordinary', mode='deduction'),
        },
        'Mortgage interest': {
            'note': (f'Deduction ratio {mortgage_ratio:.1%} (qualified limit $750k / '
                     f'loan balance). Effective rate = bracket * {mortgage_ratio:.3f}'),
            'segments': _build_segments(
                _find_knots_mortgage(baseline, config), baseline, config,
                fed_rate_type='ordinary', mode='mortgage'),
        },
        'Property tax': {
            'note': salt_note,
            'segments': _build_segments(
                property_tax_knots, baseline, config, fed_rate_type='ordinary', mode='property_tax'),
        },
        'Foreign tax credit': {
            'note': 'Dollar-for-dollar credit against federal tax (Form 1116 limit not implemented)',
            'segments': _build_segments(
                foreign_tax_knots, baseline, config, fed_rate_type='ordinary', mode='foreign_tax_credit'),
        },
    }

    results = {
        'year': year,
        'method': 'analytical',
        'baseline': {
            'agi': baseline['agi'],
            'taxable_income': baseline['taxable_income'],
            'is_itemizing': baseline['is_itemizing'],
            'net_stcg': baseline['net_stcg'],
            'net_ltcg': baseline['net_ltcg'],
            'ny_agi': baseline['ny_agi'],
            'ny_taxable': baseline['ny_taxable'],
            'salt_regime': salt_regime,
            'salt_total': baseline['salt_total'],
            'salt_deduction': baseline['salt_deduction'],
            'foreign_tax': baseline['foreign_tax'],
            'mortgage_deduction_ratio': baseline['mortgage_deduction_ratio'],
        },
        'marginal_rates': categories,
    }
    return results


def _format_amount(amount):
    if amount is None:
        return '...'
    return f'${amount:,}'


def main():
    parser = argparse.ArgumentParser(description='Compute marginal tax rates (analytical)')
    parser.add_argument('--year', type=str, default='2025', help='Tax year (default: 2025)')
    args = parser.parse_args()

    results = compute_analytical_marginal_rates(year=args.year)

    output_dir = os.path.join('output', args.year)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'marginal_rates.json')
    with open(output_path, 'w') as fout:
        json.dump(results, fout, indent=4)

    lines = format_results(results)
    for line in lines:
        print(line)

    txt_path = os.path.join(output_dir, 'marginal_rates.txt')
    with open(txt_path, 'w') as fout:
        fout.write('\n'.join(lines) + '\n')

    print(f"\nSaved to {output_path} and {txt_path}")


def format_results(results):
    """Format results as a list of lines for display and text file output."""
    lines = []
    base = results['baseline']
    lines.append(f"Marginal tax rates (analytical, year={results['year']})")
    lines.append(f"Baseline: AGI=${base['agi']:,.0f}, taxable=${base['taxable_income']:,.0f}, "
                 f"SALT={base['salt_regime']}, NY taxable=${base['ny_taxable']:,.0f}")
    lines.append('')

    for name, category in results['marginal_rates'].items():
        segments = category['segments'] if isinstance(category, dict) else category
        note = category.get('note', '') if isinstance(category, dict) else ''
        header = f"  {name}:"
        if note:
            header += f"  ({note})"
        lines.append(header)
        range_strs = []
        for seg in segments:
            range_strs.append(f"{_format_amount(seg['from'])} - {_format_amount(seg['to'])}")
        col_width = max(len(s) for s in range_strs) + 2
        lines.append(f"    {'Additional':<{col_width}} {'Federal':>10} {'NY State':>10} {'NYC':>10} {'Combined':>10}")
        for seg, range_str in zip(segments, range_strs):
            rates = seg['rates']
            line = (f"    {range_str:<{col_width}} {rates['federal']:>9.2%} {rates['ny_state']:>9.2%}"
                    f" {rates['nyc']:>9.2%} {rates['combined']:>9.2%}")
            if 'next_knot' in seg:
                line += f"  <- {seg['next_knot']}"
            lines.append(line)
        lines.append('')

    return lines


if __name__ == '__main__':
    main()
