"""Compute marginal tax rates by perturbing each input category.

Standalone script — imports the existing fill_taxes pipeline without modifying it.
For each input category (wages, capital gains, dividends, etc.), adds a delta to the
input, re-runs the tax computation, and measures the change in total tax.

Usage:
    python marginal_rates.py [--delta 100] [--year 2025]

Notes:
    - W2 wages marginal rate is ~0.9% higher than other ordinary income (interest,
      short-term gains, non-qualified dividends) because of the Additional Medicare Tax
      on wages above $200k (0.9%, Form 8959).
    - Long-term capital gains and qualified dividends get preferential federal rates
      (0%/15%/20%) via the Qualified Dividends and Capital Gains worksheet.
    - 1256 contracts use a 60/40 split: 60% long-term (preferential) + 40% short-term
      (ordinary), yielding a blended federal rate (e.g. 26.8% = 60%*20% + 40%*37%).
    - If input data has net capital losses, LTCG and 1256 gains may show ordinary rates
      because the additional gain just offsets losses rather than creating net taxable gain.
    - Charitable contributions show 0% NY/NYC impact at high income because NY itemized
      deductions are capped at 50% of AGI for NYAGI above $1M.
"""
import argparse
import copy
import json
import os

from pipeline.fill_taxes import gather_inputs, FILL_FUNCTIONS
from computation.form_worksheet_names import k_1040, k_it201


def extract_taxes(forms_state):
    """Pull the tax totals we care about from a completed forms_state."""
    federal = forms_state.get(k_1040, {}).get('24', 0)
    ny_state = forms_state.get(k_it201, {}).get('46', 0)
    nyc = forms_state.get(k_it201, {}).get('58', 0)
    return dict(federal=federal, ny_state=ny_state, nyc=nyc)


def compute_rates(base_taxes, perturbed_taxes, delta):
    """Compute marginal rate for each tax jurisdiction."""
    rates = {}
    for key in base_taxes:
        diff = perturbed_taxes[key] - base_taxes[key]
        rates[key] = round(diff / delta, 6)
    rates['combined'] = round(sum(rates.values()), 6)
    return rates


PERTURBATIONS = {
    'W2 Wages': {
        'description': 'Additional dollar of W-2 wage income',
        'apply': '_perturb_wages',
    },
    'Short-term capital gain': {
        'description': 'Additional dollar of short-term capital gain',
        'apply': '_perturb_short_term',
    },
    'Long-term capital gain': {
        'description': 'Additional dollar of long-term capital gain',
        'apply': '_perturb_long_term',
    },
    'Qualified dividends': {
        'description': 'Additional dollar of qualified dividends (also ordinary)',
        'apply': '_perturb_qualified_dividends',
    },
    'Ordinary dividends (non-qualified)': {
        'description': 'Additional dollar of ordinary dividends only',
        'apply': '_perturb_ordinary_dividends',
    },
    'Interest income': {
        'description': 'Additional dollar of interest income',
        'apply': '_perturb_interest',
    },
    '1256 contracts': {
        'description': 'Additional dollar of Section 1256 contract gain (60/40 split)',
        'apply': '_perturb_1256',
    },
    'Charitable contributions': {
        'description': 'Additional dollar of charitable cash contribution (reduces tax)',
        'apply': '_perturb_charitable',
    },
}


def _ensure_1099(data):
    """Return the first 1099 entry, creating one if needed."""
    if '1099' not in data:
        data['1099'] = [{'Institution': 'MarginalRate_Synthetic'}]
    return data['1099'][0]


def _perturb_wages(data, delta):
    data['W2'][0]['Wages'] += delta
    data['W2'][0]['Medicare_wages'] += delta


def _perturb_short_term(data, delta):
    entry = _ensure_1099(data)
    synthetic_trade = {
        'SalesDescription': 'MarginalRate_Synthetic',
        'Shares': '1',
        'DateAcquired': '2025/01/01',
        'DateSold': '2025/06/01',
        'WashSaleCode': '',
        'Proceeds': delta,
        'Cost': 0,
        'WashSaleValue': 0,
        'LongShort': 'SHORT',
        'FormCode': 'B',
    }
    entry.setdefault('Trades', []).append(synthetic_trade)


def _perturb_long_term(data, delta):
    entry = _ensure_1099(data)
    synthetic_trade = {
        'SalesDescription': 'MarginalRate_Synthetic',
        'Shares': '1',
        'DateAcquired': '2024/01/01',
        'DateSold': '2025/06/01',
        'WashSaleCode': '',
        'Proceeds': delta,
        'Cost': 0,
        'WashSaleValue': 0,
        'LongShort': 'LONG',
        'FormCode': 'E',
    }
    entry.setdefault('Trades', []).append(synthetic_trade)


def _perturb_qualified_dividends(data, delta):
    entry = _ensure_1099(data)
    entry['Qualified Dividends'] = entry.get('Qualified Dividends', 0) + delta
    entry['Ordinary Dividends'] = entry.get('Ordinary Dividends', 0) + delta


def _perturb_ordinary_dividends(data, delta):
    entry = _ensure_1099(data)
    entry['Ordinary Dividends'] = entry.get('Ordinary Dividends', 0) + delta


def _perturb_interest(data, delta):
    entry = _ensure_1099(data)
    entry['Interest'] = entry.get('Interest', 0) + delta


def _perturb_1256(data, delta):
    entry = _ensure_1099(data)
    entry['Realized1256'] = entry.get('Realized1256', 0) + delta


def _perturb_charitable(data, delta):
    if 'Charitable' not in data:
        data['Charitable'] = [{'Entity': 'MarginalRate_Synthetic', 'Amount': 0}]
    data['Charitable'][0]['Amount'] += delta


PERTURB_FUNCTIONS = {
    '_perturb_wages': _perturb_wages,
    '_perturb_short_term': _perturb_short_term,
    '_perturb_long_term': _perturb_long_term,
    '_perturb_qualified_dividends': _perturb_qualified_dividends,
    '_perturb_ordinary_dividends': _perturb_ordinary_dividends,
    '_perturb_interest': _perturb_interest,
    '_perturb_1256': _perturb_1256,
    '_perturb_charitable': _perturb_charitable,
}


def run_computation(data, year):
    """Run fill_taxes and return forms_state."""
    fill_func = FILL_FUNCTIONS[year]
    forms_state, _worksheets, _summary, _carryover = fill_func(d=data)
    return forms_state


def compute_marginal_rates(year, delta):
    """Compute marginal rates for all perturbation categories."""
    base_data = gather_inputs(year)
    base_state = run_computation(copy.deepcopy(base_data), year=year)
    base_taxes = extract_taxes(base_state)

    results = {
        'year': year,
        'delta': delta,
        'base_taxes': base_taxes,
        'marginal_rates': {},
    }

    for name, spec in PERTURBATIONS.items():
        perturbed_data = copy.deepcopy(base_data)
        perturb_fn = PERTURB_FUNCTIONS[spec['apply']]
        perturb_fn(perturbed_data, delta)

        perturbed_state = run_computation(perturbed_data, year=year)
        perturbed_taxes = extract_taxes(perturbed_state)

        rates = compute_rates(base_taxes, perturbed_taxes, delta)
        results['marginal_rates'][name] = {
            'description': spec['description'],
            'rates': rates,
        }

    return results


def main():
    parser = argparse.ArgumentParser(description='Compute marginal tax rates')
    parser.add_argument('--delta', type=float, default=10000, help='Perturbation amount in dollars (default: 100)')
    parser.add_argument('--year', type=str, default='2025', help='Tax year (default: 2025)')
    args = parser.parse_args()

    results = compute_marginal_rates(year=args.year, delta=args.delta)

    output_dir = os.path.join('output', args.year)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'marginal_rates.json')
    with open(output_path, 'w') as fout:
        json.dump(results, fout, indent=4)

    print(f"\nMarginal tax rates (delta=${args.delta:,.0f}, year={args.year})")
    print(f"{'Category':<40} {'Federal':>10} {'NY State':>10} {'NYC':>10} {'Combined':>10}")
    print('-' * 82)
    for name, entry in results['marginal_rates'].items():
        rates = entry['rates']
        print(
            f"{name:<40} {rates['federal']:>9.2%} {rates['ny_state']:>9.2%}"
            f" {rates['nyc']:>9.2%} {rates['combined']:>9.2%}"
        )

    print(f"\nSaved to {output_path}")


if __name__ == '__main__':
    main()
