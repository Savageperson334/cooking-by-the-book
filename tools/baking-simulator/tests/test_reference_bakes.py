"""Compare the dough solver with published loaves (reference_bakes.json).

The steam heat-transport coefficient (engine.EC_DIFFUSIVITY) was fitted ONLY
to the 'fit' case. The 'holdout' case was not used for fitting; its tolerances
record how well the model generalises today, so a regression shows up here.
"""
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import engine

CATALOG = json.loads((HERE / 'ingredients.json').read_text())
CASES = {c['id']: c for c in json.loads((HERE / 'reference_bakes.json').read_text())['cases']}


def simulate(case_id, **overrides):
    inputs = CASES[case_id]['bakelab_inputs']
    return engine.simulate({'catalog': CATALOG, 'amounts': inputs['amounts'],
                            'settings': {**inputs['settings'], **overrides}})


def first_minute(result, threshold_c):
    return next((f['minute'] for f in result['timeline'] if f['center_c'] >= threshold_c), None)


class FitCase(unittest.TestCase):
    """Papasidero et al.: 810 g pagnotta, 200 °C fan oven, 40 min."""
    case = 'papasidero2015_pagnotta'

    def test_centre_reaches_plateau_on_time(self):
        r = simulate(self.case)
        measured = CASES[self.case]['measured']['centre_t97_min_approx']
        t97 = first_minute(r, 97.0)
        self.assertIsNotNone(t97)
        self.assertAlmostEqual(t97, measured, delta=3.0)
        self.assertGreaterEqual(r['summary']['center_c'], 97.0)

    def test_weight_loss_close_without_being_fitted(self):
        r = simulate(self.case)
        self.assertAlmostEqual(r['summary']['mass_loss_pct'],
                               CASES[self.case]['measured']['mass_loss_pct'], delta=1.5)

    def test_without_steam_term_centre_is_far_too_slow(self):
        saved = engine.EC_DIFFUSIVITY
        try:
            engine.EC_DIFFUSIVITY = 0.0
            r = simulate(self.case)
        finally:
            engine.EC_DIFFUSIVITY = saved
        self.assertIsNone(first_minute(r, 97.0))  # documents why the term exists


class HoldoutCase(unittest.TestCase):
    """Zhang et al. 2025: ~20 mm dough in a glass mould, 180 °C, 30 min. NOT used for fitting."""
    case = 'zhang2025_glass_mould'

    def test_centre_passes_93c_near_measured_time(self):
        t93 = first_minute(simulate(self.case), 93.0)
        self.assertIsNotNone(t93)
        self.assertAlmostEqual(t93, CASES[self.case]['measured']['coolest_point_above_93c_min'], delta=4.0)

    def test_mid_depth_reaches_boiling_near_measured_time(self):
        t99 = first_minute(simulate(self.case), 99.0)
        self.assertIsNotNone(t99)
        self.assertAlmostEqual(t99, CASES[self.case]['measured']['t2_reach_100c_min'], delta=4.0)

    def test_water_loss_gap_is_known_and_bounded(self):
        # Known gap: the symmetric slab evaporates from both faces, while the
        # real dough sat in a glass mould open only on top. Today ~21 g vs 15 g.
        r = simulate(self.case)
        lost_g = r['summary']['total_g'] * r['summary']['mass_loss_pct'] / 100
        measured = CASES[self.case]['measured']['water_lost_g']
        self.assertGreater(lost_g, 0.8 * measured)
        self.assertLess(lost_g, 1.6 * measured)


class SteamTransportPhysics(unittest.TestCase):
    def test_water_is_conserved_when_steam_moves_it(self):
        r = simulate('papasidero2015_pagnotta')
        w0 = r['summary']['water_pct'] / 100
        cells = [w / 100 for w in r['profile']['water_pct']]
        # Each cell holds the same dry mass, so water per cell is proportional to w/(1-w).
        remaining = sum(w / (1 - w) for w in cells) * (1 - w0) / (w0 * len(cells))
        expected = 1 - (r['summary']['mass_loss_pct'] / 100) / w0
        self.assertAlmostEqual(remaining, expected, delta=0.002)

    def test_crust_still_forms_and_crumb_gains_moisture(self):
        r = engine.simulate({'catalog': CATALOG,
                             'amounts': {'bread_flour': 500, 'water': 340, 'salt': 10, 'instant_yeast': 7},
                             'settings': {'oven_c': 230, 'minutes': 60, 'thickness_mm': 80}})
        self.assertGreater(r['summary']['surface_c'], 130.0)  # dried crust heats past boiling
        self.assertGreater(r['profile']['water_pct'][0], r['summary']['water_pct'])  # condensed vapour in crumb

    def test_steam_term_off_when_dry_and_peaks_near_boiling(self):
        self.assertLess(engine.evaporation_condensation_k(99.0, 0.0), 1e-3)
        self.assertGreater(engine.evaporation_condensation_k(99.0, 0.45),
                           engine.evaporation_condensation_k(60.0, 0.45) * 3)


if __name__ == '__main__':
    unittest.main()
