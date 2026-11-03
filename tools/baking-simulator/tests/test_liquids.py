"""Conservation, cross-phase limits, small differences and extreme-formula coverage."""
import json
import math
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import simulate
CAT = json.loads((ROOT/'ingredients.json').read_text())


def run(amounts, oven=220, minutes=90, depth=30):
    return simulate({'catalog':CAT,'amounts':amounts,'settings':{
        'oven_c':oven,'minutes':minutes,'thickness_mm':depth,'initial_c':22,
        'proof_minutes':0,'steam_pct':5}})


class TestLiquidPhysics(unittest.TestCase):
    def test_pure_water_no_superheated_liquid(self):
        r=run({'water':1000},minutes=180)
        self.assertEqual(r['summary']['liquid_mode'],'aqueous')
        for t in r['timeline']:
            if t['water_remaining_g'] > 0.01:
                self.assertLessEqual(t['surface_c'],100.02)

    def test_water_evaporation_reduces_mass_volume_depth(self):
        r=run({'water':1000},minutes=180)
        series=r['timeline']
        for k in ('water_remaining_g','liquid_depth_mm','liquid_volume_ml'):
            self.assertTrue(all(x[k]>=y[k]-0.01 for x,y in zip(series,series[1:])),k)
        self.assertLess(series[-1]['liquid_depth_mm'],series[0]['liquid_depth_mm'])
        self.assertLess(series[-1]['water_remaining_g'],series[0]['water_remaining_g'])
        self.assertAlmostEqual(series[0]['liquid_depth_mm'],30,delta=0.0001)

    def test_empty_water_has_zero_depth_and_finite_sentinel(self):
        r=run({'water':1000},minutes=300)
        self.assertAlmostEqual(r['summary']['liquid_depth_mm'],0,delta=0.001)
        self.assertAlmostEqual(r['summary']['water_remaining_g'],0,delta=0.001)
        self.assertTrue(math.isfinite(r['summary']['center_c']))
        self.assertTrue(any('exhausted' in w for w in r['warnings']))

    def test_milk_evaporation_leaves_solids(self):
        r=run({'milk':1000},minutes=300)
        s=r['summary']
        self.assertEqual(s['liquid_mode'],'aqueous')
        self.assertGreater(s['dry_mass_g'],110)
        self.assertLess(s['end_mass_g'],200)
        self.assertGreater(s['liquid_depth_mm'],0)

    def test_milk_skin_requires_milk_and_heating(self):
        milk=run({'water':500,'milk':500},minutes=90)
        water=run({'water':1000},minutes=90)
        cold=run({'milk':1000},oven=22,minutes=90)
        self.assertGreater(milk['summary']['milk_skin_index_pct'],2)
        self.assertEqual(water['summary']['milk_skin_index_pct'],0)
        self.assertLess(cold['summary']['milk_skin_index_pct'],2)

    def test_pure_oil_does_not_evaporate_as_water(self):
        r=run({'olive_oil':1000},minutes=180)
        self.assertEqual(r['summary']['liquid_mode'],'oil')
        self.assertEqual(r['summary']['mass_loss_pct'],0)
        self.assertAlmostEqual(r['summary']['liquid_depth_mm'],30)
        self.assertTrue(any('smoke' in w.lower() for w in r['warnings']))

    def test_added_oil_separates_upward_and_remains(self):
        r=run({'olive_oil':500,'water':500},minutes=180)
        self.assertEqual(r['summary']['liquid_mode'],'biphasic')
        self.assertEqual(r['timeline'][0]['oil_layer_mm'],0)
        self.assertGreater(r['timeline'][-1]['oil_layer_mm'],4)
        self.assertLessEqual(r['summary']['oil_layer_mm'],r['summary']['liquid_depth_mm']+.001)
        self.assertGreater(r['summary']['end_mass_g'],499)

    def test_syrup_gets_more_concentrated(self):
        r=run({'water':500,'sugar':500},minutes=180)
        t=r['timeline']
        self.assertEqual(r['summary']['liquid_mode'],'syrup')
        self.assertGreater(t[-1]['sugar_concentration_pct'],t[0]['sugar_concentration_pct'])
        self.assertGreater(t[-1]['syrup_thickening_index_pct'],t[0]['syrup_thickening_index_pct'])
        self.assertGreater(r['summary']['center_c'],100)

    def test_mass_balance_for_multiple_extremes(self):
        for mix in ({'water':1000},{'milk':1000},{'sugar':500,'water':500},
                    {'olive_oil':500,'water':500},{'olive_oil':1000}):
            with self.subTest(mix=mix):
                r=run(mix,minutes=180)
                s=r['summary']
                self.assertAlmostEqual(s['total_g'],s['end_mass_g']+s['total_g']*s['mass_loss_pct']/100,delta=.025)
                self.assertAlmostEqual(s['end_mass_g'],s['dry_mass_g']+s['moisture_end_g'],delta=.025)

    def test_shallower_pan_evaporates_faster(self):
        a=run({'water':1000},minutes=90,depth=15)['summary']
        b=run({'water':1000},minutes=90,depth=75)['summary']
        self.assertLess(a['water_remaining_g'],b['water_remaining_g'])

    def test_single_degree_oven_change_affects_liquid_depth(self):
        a=run({'water':1000},oven=220,minutes=100)['summary']
        b=run({'water':1000},oven=221,minutes=100)['summary']
        self.assertGreater(abs(a['liquid_depth_mm']-b['liquid_depth_mm']),0.001)

    def test_zero_time_returns_initial_state(self):
        r=run({'milk':700,'water':300},minutes=0)
        self.assertAlmostEqual(r['summary']['liquid_depth_mm'],30)
        self.assertEqual(r['summary']['mass_loss_pct'],0)

    def test_flour_slurry_keeps_dough_solver_warning(self):
        r=run({'ap_flour':200,'water':1000},minutes=30)
        self.assertNotIn('liquid_mode',r['summary'])

    def test_very_extreme_remains_finite(self):
        for mix in ({'water':1000},{'milk':1000},{'sugar':1000,'water':220},
                    {'olive_oil':900,'water':100},{'olive_oil':1000}):
            with self.subTest(mix=mix):
                r=run(mix,oven=400,minutes=300,depth=2)
                s=r['summary']
                for key in ('center_c','surface_c','liquid_depth_mm','end_mass_g','liquid_volume_ml'):
                    self.assertTrue(math.isfinite(s[key]),(mix,key,s[key]))
                self.assertGreaterEqual(s['liquid_depth_mm'],0)


class TestMobilePhysicsUI(unittest.TestCase):
    def test_scroll_rail_and_units_rendered(self):
        html=(ROOT/'index.html').read_text()
        css=(ROOT/'style.css').read_text()
        js=(ROOT/'app.js').read_text()
        self.assertEqual(html.count('class="scroll-rail"'),2)
        self.assertIn('touch-action:pan-y',css)
        self.assertIn('AMOUNT (g)',html)
        self.assertIn("text:'g'",js)
        self.assertIn("class:'amount-wrap'",js)

    def test_liquid_visual_uses_physical_depth_and_colour_mix(self):
        js=(ROOT/'app.js').read_text()
        html=(ROOT/'index.html').read_text()
        for key in ('liquid_depth_mm','liquid_volume_ml','milk_skin_index_pct','oil_layer_mm','syrup_thickening_index_pct','ingredientVisuals'):
            self.assertIn(key,js)
        self.assertIn("const pa=colorToRgb(a),pb=colorToRgb(b)",js)
        self.assertIn('id="scene-material-note"',html)
        self.assertIn('id="fluid-depth"',html)
        self.assertIn('value="oilwater"',html)
        self.assertIn('BUILD 0.8',html)
        worker=(ROOT/'worker.js').read_text()
        self.assertIn("fetch('./liquids.py')",worker)
        self.assertIn("'/home/pyodide/liquids.py'",worker)

if __name__=='__main__':unittest.main()
