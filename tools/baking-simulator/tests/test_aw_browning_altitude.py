"""Water activity (GAB), literature browning kinetics and altitude."""
import json
import math
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import engine

CATALOG = json.loads((HERE / 'ingredients.json').read_text())
LOAF = {'bread_flour': 500, 'water': 340, 'salt': 10, 'instant_yeast': 7}


def run(amounts=LOAF, **settings):
    return engine.simulate({'catalog': CATALOG, 'amounts': amounts, 'settings': settings})


class Altitude(unittest.TestCase):
    def test_standard_atmosphere_boiling_points(self):
        self.assertAlmostEqual(engine.boiling_point_c(engine.pressure_at_altitude(0)), 100.0, delta=0.05)
        self.assertAlmostEqual(engine.boiling_point_c(engine.pressure_at_altitude(1500)), 95.0, delta=0.3)
        self.assertAlmostEqual(engine.boiling_point_c(engine.pressure_at_altitude(3000)), 90.0, delta=0.4)

    def test_water_never_exceeds_local_boiling_point(self):
        r = run({'water': 500}, oven_c=220, minutes=60, thickness_mm=30, altitude_m=3000)
        wet = [f['center_c'] for f in r['timeline'] if f['water_remaining_g'] > 1.0]
        self.assertLessEqual(max(wet), r['settings']['boil_c'] + 0.01)

    def test_dough_crumb_plateaus_at_local_boiling_point(self):
        r = run(altitude_m=2500, minutes=90, thickness_mm=40, pan='glass_dish')
        self.assertLessEqual(r['summary']['center_c'], r['settings']['boil_c'] + 0.05)
        self.assertGreater(r['summary']['center_c'], r['settings']['boil_c'] - 1.0)

    def test_gas_expands_more_at_altitude(self):
        low = run(altitude_m=0, minutes=40)['summary']['max_rise_pct']
        high = run(altitude_m=2500, minutes=40)['summary']['max_rise_pct']
        self.assertGreater(high, low)


class WaterActivity(unittest.TestCase):
    def test_gab_inversion_round_trips(self):
        xm, c, k = engine.GAB_XM, engine.GAB_C, engine.GAB_K
        for aw in (0.1, 0.3, 0.5, 0.7, 0.9):
            x = xm * c * k * aw / ((1 - k*aw) * (1 - k*aw + c*k*aw))
            self.assertAlmostEqual(engine.crust_water_activity(x / (1 + x)), aw, places=6)

    def test_wet_dough_is_near_one_and_dry_crust_is_low(self):
        self.assertGreater(engine.crust_water_activity(0.45), 0.99)
        self.assertLess(engine.crust_water_activity(0.05), 0.15)


class Browning(unittest.TestCase):
    def test_needs_both_heat_and_dryness(self):
        full = engine.browning_rate(170, 0.3)
        self.assertGreater(full, 1e-4)
        self.assertLess(engine.browning_rate(105, 0.3), 0.01 * full)   # too cool
        self.assertLess(engine.browning_rate(170, 0.95), 0.01 * full)  # too wet

    def test_arrhenius_ratio_matches_published_activation_energy(self):
        ratio = engine.browning_rate(200, 0.1) / engine.browning_rate(160, 0.1)
        expected = math.exp(engine.BROWN_EA / engine.R_GAS * (1/433.15 - 1/473.15))
        self.assertAlmostEqual(ratio, expected, delta=0.02 * expected)

    def test_skin_is_hotter_than_outer_cell_while_heating(self):
        r = run(minutes=30, oven_c=220, thickness_mm=60)
        frame = r['timeline'][len(r['timeline'])//2]
        self.assertGreater(frame['crust_surface_c'], frame['surface_c'])
        self.assertLess(frame['crust_surface_c'], 220.0)

    def test_hotter_oven_browns_more(self):
        cool = run(minutes=35, oven_c=190)['summary']['browning_index']
        hot = run(minutes=35, oven_c=240)['summary']['browning_index']
        self.assertGreater(hot, cool)

    def test_colour_change_estimate_only_inside_its_fitted_range(self):
        inside = run({'bread_flour': 500, 'water': 290, 'salt': 10, 'instant_yeast': 10},
                     oven_c=200, fan=1, minutes=40, thickness_mm=50, initial_c=25, pan='rack')['summary']
        self.assertIsNotNone(inside['colour_change_dE_purlis2007'])
        expected = (0.0266*200 + 3.4991) * inside['mass_loss_pct']
        self.assertAlmostEqual(inside['colour_change_dE_purlis2007'], expected, delta=0.1)
        self.assertIsNone(run(minutes=40, oven_c=250)['summary']['colour_change_dE_purlis2007'])


if __name__ == '__main__':
    unittest.main()
