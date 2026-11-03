"""BakeLab 0.8 regression coverage: plant suspensions, dry-down and temperature UX."""
import json
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine import simulate
CAT=json.loads((ROOT/'ingredients.json').read_text())


def run(amounts,oven=260,minutes=240,depth=15):
    return simulate(dict(catalog=CAT,amounts=amounts,settings=dict(oven_c=oven,minutes=minutes,
                     thickness_mm=depth,initial_c=22,proof_minutes=0,steam_pct=5,fan=0)))


class TestResidueDryDown(unittest.TestCase):
    def test_banana_water_drives_slurry_to_scorched_residue(self):
        r=run({'water':500,'banana':250})
        first,last=r['timeline'][0],r['timeline'][-1]
        self.assertEqual(r['summary']['liquid_mode'],'suspension')
        self.assertEqual(first['residue_state'],'slurry')
        self.assertEqual(last['residue_state'],'scorched')
        self.assertGreater(last['residue_browning_index'],75)
        self.assertLess(last['water_remaining_g'],1)
        self.assertGreater(last['liquid_depth_mm'],0)
        self.assertLess(last['liquid_depth_mm'],first['liquid_depth_mm'])
        self.assertGreater(r['summary']['dry_mass_g'],60)

    def test_oat_water_hydrates_then_toasts(self):
        r=run({'water':600,'oats':200})
        first,last=r['timeline'][0],r['timeline'][-1]
        self.assertEqual(r['summary']['liquid_mode'],'suspension')
        self.assertGreater(last['oat_hydration_index_pct'],90)
        self.assertEqual(first['oat_hydration_index_pct'],0)
        self.assertGreater(last['residue_browning_index'],65)
        self.assertGreater(last['liquid_depth_mm'],0)

    def test_short_bake_is_wet_and_not_scorched(self):
        r=run({'water':500,'banana':250},oven=140,minutes=40)
        self.assertEqual(r['summary']['residue_state'],'slurry')
        self.assertLess(r['summary']['residue_browning_index'],1)

    def test_pure_water_can_be_empty_but_not_brown(self):
        r=run({'water':1000},oven=350,minutes=300)
        self.assertEqual(r['summary']['residue_state'],'empty')
        self.assertEqual(r['summary']['residue_browning_index'],0)
        self.assertEqual(r['summary']['browning_index'],0)
        self.assertEqual(r['summary']['dry_mass_g'],0)

    def test_darkening_changes_continuously_with_oven_temp(self):
        lower=run({'water':500,'banana':250},oven=240,minutes=120)['summary']['browning_index']
        higher=run({'water':500,'banana':250},oven=241,minutes=120)['summary']['browning_index']
        self.assertGreater(higher,lower)
        self.assertLess(higher-lower,20)

    def test_original_milk_oil_syrup_regressions(self):
        for m in ({'milk':1000},{'olive_oil':500,'water':500},{'sugar':500,'water':500}):
            with self.subTest(m=m):
                r=run(m,minutes=100)
                self.assertAlmostEqual(r['summary']['total_g'],r['summary']['end_mass_g']+
                                 r['summary']['total_g']*r['summary']['mass_loss_pct']/100,delta=.03)
                self.assertTrue(math.isfinite(r['summary']['center_c']))

    def test_new_extended_max_and_rejection(self):
        r=run({'water':500,'banana':250},oven=600,minutes=1440,depth=2)
        self.assertGreater(r['summary']['residue_browning_index'],90)
        self.assertEqual(r['settings']['oven_c'],600)
        for value,field in ((601,'oven_c'),(1441,'minutes')):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    kw={'oven_c':260,'minutes':20}
                    kw[field]=value
                    simulate(dict(catalog=CAT,amounts={'banana':200,'water':500},settings=kw))

    def test_large_extreme_dough_is_bounded_for_browser(self):
        r=run({'bread_flour':500,'water':350},oven=600,minutes=1440,depth=2)
        self.assertLessEqual(r['metadata']['steps'],40000)
        self.assertTrue(any('coarsened' in w for w in r['warnings']))


class TestUIContract(unittest.TestCase):
    def test_temperature_both_units_and_slider_switch(self):
        js=(ROOT/'app.js').read_text()
        html=(ROOT/'index.html').read_text()
        self.assertIn('const cToF=',js)
        self.assertIn('const fToC=',js)
        self.assertIn("let temperatureUnit='C'",js)
        self.assertIn('bothTemps(s.center_c)',js)
        self.assertIn("const cToF=c=>c*9/5+32",js)
        self.assertRegex(html, r'BUILD 0\.\d+')

    def test_new_chart_keys_and_ingredient_demo(self):
        js=(ROOT/'app.js').read_text()
        html=(ROOT/'index.html').read_text()
        for k in ('oat_hydration_index_pct','residue_browning_index','residue_state','solids_fraction_pct'):
            self.assertIn(k,js)
        self.assertIn('value="bananadry"',html)
        self.assertIn('value="oatporridge"',html)
        self.assertIn('value="residue"',html)

if __name__=='__main__':unittest.main()
