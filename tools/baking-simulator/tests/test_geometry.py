"""Shapes (slab / cylinder / sphere) and pan or support contact."""
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import engine
import geometry

CATALOG = json.loads((HERE / 'ingredients.json').read_text())
LOAF = {'bread_flour': 500, 'water': 340, 'salt': 10, 'instant_yeast': 7}


def run(amounts=LOAF, **settings):
    return engine.simulate({'catalog': CATALOG, 'amounts': amounts,
                            'settings': {'oven_c': 220, 'minutes': 35, 'thickness_mm': 60, **settings}})


def first(result, key, threshold):
    return next((f['minute'] for f in result['timeline'] if f.get(key, -1e9) >= threshold), None)


class FullThicknessSolverMatchesSymmetricSolver(unittest.TestCase):
    """An open bottom identical to the top must reproduce the symmetric half-slab."""

    def test_open_identical_faces_agree(self):
        rack = dict(geometry.PANS['rack'])
        try:
            geometry.PANS['rack'].update(heat_scale=1.0, evap_scale=1.0)
            full = run(pan='rack', minutes=40)
        finally:
            geometry.PANS['rack'].clear(); geometry.PANS['rack'].update(rack)
        half = run(pan='none', minutes=40)
        self.assertAlmostEqual(full['summary']['center_c'], half['summary']['center_c'], delta=1.0)
        self.assertAlmostEqual(full['summary']['surface_c'], half['summary']['surface_c'], delta=1.0)
        self.assertAlmostEqual(full['summary']['bottom_c'], half['summary']['surface_c'], delta=1.0)
        self.assertAlmostEqual(full['summary']['mass_loss_pct'], half['summary']['mass_loss_pct'], delta=0.15)


class Shapes(unittest.TestCase):
    def test_more_surface_per_volume_heats_faster(self):
        times = {s: first(run(shape=s, minutes=60), 'coldest_c', 95) for s in ('slab', 'cylinder', 'sphere')}
        self.assertLess(times['sphere'], times['cylinder'])
        self.assertLess(times['cylinder'], times['slab'])

    def test_water_is_conserved_in_radial_cells(self):
        r = run(shape='sphere', minutes=30)
        w0 = r['summary']['water_pct'] / 100
        weights = r['metadata']['cell_mass_fraction']
        self.assertAlmostEqual(sum(weights), 1.0, places=5)
        cells = [w / 100 for w in r['profile']['water_pct']]
        remaining = sum(m * w / (1 - w) for m, w in zip(weights, cells)) * (1 - w0) / w0
        self.assertAlmostEqual(remaining, 1 - (r['summary']['mass_loss_pct'] / 100) / w0, delta=0.003)

    def test_round_shapes_ignore_pan_with_warning(self):
        r = run(shape='sphere', pan='baking_stone')
        self.assertTrue(any('only modelled for the flat slab' in w for w in r['warnings']))
        self.assertNotIn('bottom_c', r['summary'])

    def test_rejects_unknown_shape_or_pan(self):
        with self.assertRaises(ValueError):
            run(shape='torus')
        with self.assertRaises(ValueError):
            run(pan='frying_pan_of_doom')


class Pans(unittest.TestCase):
    def flat(self, pan, **kw):
        return run(pan=pan, thickness_mm=20, minutes=20, oven_c=230, **kw)

    def test_preheated_stone_and_steel_heat_the_bottom_fastest(self):
        t = {p: first(self.flat(p), 'bottom_c', 99) for p in ('baking_steel', 'baking_stone', 'dark_steel_pan', 'aluminium_sheet')}
        self.assertLess(t['baking_steel'], t['dark_steel_pan'])
        self.assertLess(t['baking_stone'], t['dark_steel_pan'])
        self.assertLess(t['dark_steel_pan'], t['aluminium_sheet'])  # shiny aluminium absorbs little radiation

    def test_dark_pan_bottom_runs_hotter_than_glass_then_shiny(self):
        face = {p: self.flat(p)['timeline'][len(self.flat(p)['timeline'])//3]['bottom_face_c']
                for p in ('dark_steel_pan', 'glass_dish', 'aluminium_sheet')}
        self.assertGreater(face['dark_steel_pan'], face['glass_dish'])
        self.assertGreater(face['glass_dish'], face['aluminium_sheet'])

    def test_hot_steel_browns_a_thin_base_and_cold_aluminium_does_not(self):
        pizza = {'bread_flour': 300, 'water': 195, 'salt': 8, 'instant_yeast': 2}
        steel = run(pizza, pan='baking_steel', thickness_mm=8, minutes=8, oven_c=280, proof_minutes=0)
        sheet = run(pizza, pan='aluminium_sheet', thickness_mm=8, minutes=8, oven_c=280, proof_minutes=0)
        self.assertGreater(steel['summary']['bottom_browning_index'], 5.0)
        self.assertLess(sheet['summary']['bottom_browning_index'], 1.0)

    def test_sealed_bottom_loses_less_water_than_open_faces(self):
        sealed = self.flat('glass_dish')['summary']['mass_loss_pct']
        open_both = self.flat('none')['summary']['mass_loss_pct']
        self.assertLess(sealed, open_both)

    def test_pan_temperature_stays_physical(self):
        for pan in ('aluminium_sheet', 'glass_dish', 'baking_stone', 'cast_iron'):
            r = self.flat(pan)
            temps = [f['pan_c'] for f in r['timeline']]
            self.assertGreaterEqual(min(temps), min(geometry.ROOM_C, 22.0) - 0.5)
            self.assertLessEqual(max(temps), 230.0 + 0.5)

    def test_profile_axis_is_reported(self):
        self.assertEqual(self.flat('glass_dish')['profile']['axis'], 'bottom_to_top')
        self.assertEqual(self.flat('none')['profile']['axis'], 'centre_to_surface')


class HighHeatPostprocessorUsesCellMasses(unittest.TestCase):
    def test_sphere_organic_ledger_closes(self):
        r = run(shape='sphere', oven_c=450, minutes=90)
        s = r['summary']
        parts = (s['estimated_intact_organic_g'] + s['estimated_char_g'] + s['estimated_volatile_loss_g']
                 + s['estimated_char_oxidation_loss_g'] + s['estimated_light_fragments_g'])
        organics = s['total_g'] * (s['sugar_pct'] + s['starch_pct'] + s['protein_pct'] + s['fiber_pct'] + s['fat_pct']) / 100
        self.assertAlmostEqual(parts, organics, delta=0.01 * organics)


if __name__ == '__main__':
    unittest.main()
