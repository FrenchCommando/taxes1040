"""Marginal rate tests: marginal_rates.py re-runs the tax computation, these check rates and knots that are
easy to verify by hand on a few scenarios.

Run: python -m unittest tests.test_marginal_rates -v
"""
import os
import unittest

from marginal_rates import compute_marginal_rates
from tests.test_computation import load_scenario_input

SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), 'scenarios')


def _results(year, scenario):
    data = load_scenario_input(os.path.join(SCENARIOS_DIR, year, scenario))
    return compute_marginal_rates(year=year, base_data=data)


def _segment_at(segments, amount):
    return next(segment for segment in segments
                if segment['from'] <= amount and (segment['to'] is None or amount < segment['to']))


class TestMarginalRates(unittest.TestCase):

    def test_2025_w2_only_wages(self):
        # single, $150,000 wages, standard deduction: taxable $134,250 in the 24% bracket
        wages = _results('2025', 'w2_only')['marginal_rates']['W2 Wages']['segments']
        self.assertAlmostEqual(wages[0]['rates']['federal'], 0.24, places=6)
        # Additional Medicare Tax at $200,000 wages (+$50,000), 32% bracket at taxable $197,300 (+$63,050)
        self.assertAlmostEqual(_segment_at(wages, 55_000)['rates']['federal'], 0.249, places=6)
        self.assertAlmostEqual(_segment_at(wages, 64_000)['rates']['federal'], 0.329, places=6)
        self.assertIn(63_050, [segment['from'] for segment in wages])

    def test_2025_w2_only_charitable(self):
        # no benefit until itemized deductions ($10,000 SALT + gifts) beat the $15,750 standard deduction
        charitable = _results('2025', 'w2_only')['marginal_rates']['Charitable contributions']['segments']
        self.assertEqual(charitable[0]['to'], 5_750)
        self.assertEqual(charitable[0]['rates']['combined'], 0)
        self.assertAlmostEqual(charitable[1]['rates']['federal'], -0.24, places=6)

    def test_2025_amt_owed_dividends(self):
        # AMT applies with the exemption fully phased out: qualified dividends at 20% + 3.8% NIIT
        results = _results('2025', 'amt_owed')
        self.assertTrue(results['baseline']['amt'])
        dividends = results['marginal_rates']['Qualified dividends']['segments']
        self.assertAlmostEqual(dividends[0]['rates']['federal'], 0.238, places=6)

    def test_2025_mfj_high_income_wages(self):
        # MFJ, AGI $523,000, itemizing, Medicare wages over the $250,000 MFJ threshold:
        # each $1 of wages also costs 30% of $1 of SALT deduction (phaseout above $500,000 AGI)
        results = _results('2025', 'mfj_high_income')
        self.assertEqual(results['filing_status'], 'married_filing_jointly')
        wages = results['marginal_rates']['W2 Wages']['segments']
        self.assertAlmostEqual(wages[0]['rates']['federal'], 0.32 + 0.009 + 0.30 * 0.32, places=6)
        # 35% MFJ bracket at ordinary taxable $501,050, still in the SALT phaseout
        self.assertAlmostEqual(_segment_at(wages, 50_000)['rates']['federal'], 0.35 + 0.009 + 0.30 * 0.35, places=6)
        # SALT reaches the $10,000 floor at AGI $600,000 (+$77,000): no more phaseout
        self.assertIn(77_000, [segment['from'] for segment in wages])
        self.assertAlmostEqual(_segment_at(wages, 80_000)['rates']['federal'], 0.35 + 0.009, places=6)

    def test_2026_runs(self):
        # provisional year: rates come from the same computation
        wages = _results('2026', 'w2_only')['marginal_rates']['W2 Wages']['segments']
        self.assertAlmostEqual(wages[0]['rates']['federal'], 0.24, places=6)


if __name__ == '__main__':
    unittest.main()
