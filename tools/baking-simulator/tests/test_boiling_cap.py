"""Wet dough must not hold liquid water far above its boiling point (v0.9.2)."""
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from engine import simulate, BOIL_C

CATALOG = json.loads((HERE / 'ingredients.json').read_text())
LOAF = {'bread_flour': 500, 'water': 340, 'salt': 10, 'instant_yeast': 7}


def run(**settings):
    return simulate({'catalog': CATALOG, 'amounts': LOAF,
                     'settings': {'oven_c': 220, 'minutes': 35, 'thickness_mm': 80, **settings}})


def hot_wet_cells(result, moisture_pct=1.0, tolerance_c=0.5):
    """(minute, temperature, moisture) for every cell above boiling that is still wet."""
    bad = []
    for frame in result['timeline']:
        for t, w in zip(frame['temp_profile'], frame['water_profile']):
            if w > moisture_pct and t > BOIL_C + tolerance_c:
                bad.append((frame['minute'], t, w))
    return bad


class BoilingCeiling(unittest.TestCase):
    def test_ordinary_bake_keeps_wet_crumb_at_or_below_boiling(self):
        r = run(oven_c=230, minutes=60)
        self.assertEqual(hot_wet_cells(r), [])
        self.assertGreater(r['summary']['surface_c'], BOIL_C)  # dried crust may still heat

    def test_extreme_bake_dries_before_interior_overheats(self):
        r = run(oven_c=600, minutes=1440, thickness_mm=250)
        self.assertEqual(hot_wet_cells(r), [])
        # All water should eventually leave a loaf held at 600 °C for a day.
        self.assertAlmostEqual(r['summary']['mass_loss_pct'], r['summary']['water_pct'], delta=0.5)
        self.assertNotEqual(r['summary']['thermal_stage'], 'wet / boiling')

    def test_boiled_water_is_conserved_in_mass_loss(self):
        r = run(oven_c=260, minutes=90)
        s = r['summary']
        self.assertAlmostEqual(s['end_mass_g'] + s['total_g']*s['mass_loss_pct']/100, s['total_g'], delta=0.05)
        self.assertGreaterEqual(s['moisture_end_g'], -1e-6)

    def test_cold_centre_is_flagged(self):
        r = run()
        if r['summary']['center_c'] < 90:
            self.assertTrue(any('Centre ended below 90' in w for w in r['warnings']))

    def test_zero_minute_run_has_single_initial_frame(self):
        r = run(minutes=0)
        self.assertEqual(len(r['timeline']), 1)
        self.assertEqual(r['timeline'][0]['minute'], 0.0)
        self.assertEqual(r['metadata']['steps'], 0)


if __name__ == '__main__':
    unittest.main()
