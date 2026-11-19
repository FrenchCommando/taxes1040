"""Marginal rate tests: marginal_rates.py re-runs the tax computation, these check rates and knots that are
easy to verify by hand on a few scenarios.

Run: python -m unittest tests.test_marginal_rates -v
"""
import os
import unittest

from computation.forms_core_impl import get_filing_status, resolve_config
from marginal_rates import YEAR_CONFIGS, TaxCurve, _add_wages, _segments, _thresholds, compute_marginal_rates
from tests.test_computation import load_scenario_input

SCENARIOS_DIR = os.path.join(os.path.dirname(__file__), 'scenarios')


def _results(year, scenario):
    data = load_scenario_input(os.path.join(SCENARIOS_DIR, year, scenario))
    return compute_marginal_rates(year=year, base_data=data)


def _segment_at(segments, amount):
    return next(segment for segment in segments
                if segment['from'] <= amount and (segment['to'] is None or amount < segment['to']))


def _knot_at(segments, amount):
    """Label of the knot at `amount` (the segment ending there)."""
    return next(segment['next_knot'] for segment in segments if segment['to'] == amount)


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

    def test_2026_niit_cap(self):
        # single, $150,000 wages + $30,000 interest: NIIT starts at AGI $200,000 (+$20,000), then each $1 of
        # wages adds 3.8% NIIT until MAGI over the threshold reaches the $30,000 of investment income
        # (+$50,000). Medicare wages $170,000 (pre-tax 401(k)) keep the Additional Medicare Tax at +$30,000:
        # with Medicare wages = wages it would start at the same $200,000 of wages as the NIIT cap.
        data = load_scenario_input(os.path.join(SCENARIOS_DIR, '2026', 'w2_only'))
        data['W2'] = [data['W2'][0] | dict(Medicare_wages=170_000)]
        data['1099'] = [{'Institution': 'Bank', 'Interest': 30_000}]
        wages = compute_marginal_rates(year='2026', base_data=data)['marginal_rates']['W2 Wages']['segments']
        self.assertIn('NIIT capped at net investment income', _knot_at(wages, 50_000))
        self.assertAlmostEqual(
            _segment_at(wages, 49_000)['rates']['federal'] - _segment_at(wages, 51_000)['rates']['federal'],
            0.038, places=6)

    def test_2026_cliffs_measured_at_the_knot(self):
        # MFJ, one $100,000 W2, standard deduction: NY taxable $83,950
        data = load_scenario_input(os.path.join(SCENARIOS_DIR, '2026', 'mfj_two_w2'))
        data['W2'] = [data['W2'][0] | dict(Wages=100_000, SocialSecurity_wages=100_000, Medicare_wages=100_000)]
        wages = compute_marginal_rates(year='2026', base_data=data)['marginal_rates']['W2 Wages']['segments']
        # the NYC schedule's rounded base amount makes a $0.45 jump at $90,000: not a cliff in whole dollars
        self.assertEqual(_knot_at(wages, 6_051), 'NYC bracket at taxable $90,000')
        # NY recapture worksheet 2 starts at taxable $161,550 (IT-201-I): $333 + $807 x 32.1% - $332.25 = $260
        self.assertIn('cliff: tax +$260', _knot_at(wages, 77_601))

    def test_2026_schedule_1a_staircase(self):
        # tips phaseout: $100 less deduction per $1,000 (or fraction) of MAGI over $150,000, a $32 step at 32%.
        # At +$69,501 the step coincides with the $63 NYC fixed school credit ending (income over $250,000)
        data = load_scenario_input(os.path.join(SCENARIOS_DIR, '2026', 'schedule_1a_phaseout'))
        config = YEAR_CONFIGS['2026'] | dict(exact=True, field_maps=None)
        curve = TaxCurve(base_data=data, config=config, change=_add_wages)
        thresholds = _thresholds(resolve_config(config, get_filing_status(data)))
        wages = _segments(curve, 80_000, thresholds)  # the full horizon walks ~150 steps per category
        self.assertEqual(_knot_at(wages, 69_501), 'NYC fixed school credit ends (income $250,000); cliff: tax +$95')
        stepped = _segment_at(wages, 75_000)
        self.assertTrue(stepped['next_knot'].startswith('stepped phaseout: 9 steps of +$32 every $1,000'))
        # averaged: 32% bracket + 0.9% Additional Medicare Tax + $32 per $1,000
        self.assertAlmostEqual(stepped['rates']['federal'], 0.329 + 0.032, places=6)
        self.assertTrue(all(segment.get('next_knot') != 'rate change' for segment in wages))


if __name__ == '__main__':
    unittest.main()
