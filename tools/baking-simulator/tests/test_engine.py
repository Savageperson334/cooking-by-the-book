import json
import math
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from engine import simulate, composition_of, physical_properties

CATALOG = json.loads((HERE / 'ingredients.json').read_text())

def run(amounts=None, **settings):
    return simulate({'catalog': CATALOG, 'amounts': amounts or {'bread_flour': 500, 'water': 340, 'salt': 10, 'instant_yeast': 5},
                     'settings': {'oven_c': 220, 'minutes': 35, 'thickness_mm': 80, **settings}})

class TestSolver(unittest.TestCase):
    def test_20_ingredients(self):
        self.assertGreaterEqual(len(CATALOG), 20)
        self.assertEqual(len({i['id'] for i in CATALOG}), len(CATALOG))
        for i in CATALOG:
            self.assertAlmostEqual(sum(i[x] for x in ('water','protein','fat','starch','sugar','fiber','ash')),
                                   1, delta=0.026, msg=i['id'])

    def test_heat_response(self):
        low = run(oven_c=190)['summary']
        high = run(oven_c=230)['summary']
        self.assertGreater(high['surface_c'], low['surface_c'])
        self.assertGreater(high['center_c'], low['center_c'])

    def test_small_change_has_observable_effect(self):
        a=run(oven_c=220)['summary']['surface_c']
        b=run(oven_c=221)['summary']['surface_c']
        self.assertGreater(abs(a-b), 0.005)

    def test_longer_time_heats_center(self):
        self.assertGreater(run(minutes=50)['summary']['center_c'],run(minutes=15)['summary']['center_c'])

    def test_geometry_affects_center(self):
        self.assertGreater(run(thickness_mm=30)['summary']['center_c'], run(thickness_mm=100)['summary']['center_c'])

    def test_wetter_dough_changes_results(self):
        a=run({'bread_flour':500,'water':280})['summary']
        b=run({'bread_flour':500,'water':360})['summary']
        self.assertNotEqual(a['surface_c'], b['surface_c'])
        self.assertNotEqual(a['mass_loss_pct'], b['mass_loss_pct'])

    def test_mass_conservation(self):
        x=run()['summary']
        self.assertAlmostEqual(x['total_g'], x['end_mass_g']+(x['total_g']*x['mass_loss_pct']/100), delta=.012)
        self.assertAlmostEqual(x['end_mass_g'], x['dry_mass_g']+x['moisture_end_g'], delta=.02)

    def test_surface_hotter_than_center(self):
        r=run(minutes=25)
        self.assertGreater(r['summary']['surface_c'],r['summary']['center_c'])

    def test_more_sugar_changes_index(self):
        a=run({'bread_flour':500,'water':340,'sugar':5})['summary']['browning_index']
        b=run({'bread_flour':500,'water':340,'sugar':70})['summary']['browning_index']
        self.assertGreater(b,a)

    def test_no_flour_warnings(self):
        r=run({'water':500})
        self.assertEqual(r['summary']['starch_progress_pct'],0)
        self.assertTrue(any('No flour' in w for w in r['warnings']))

    def test_all_dry(self):
        r=run({'sugar':1000,'salt':100},oven_c=300,minutes=120)
        self.assertEqual(r['summary']['mass_loss_pct'],0)
        self.assertGreater(r['summary']['surface_c'],200)

    def test_unreasonable_extreme_is_finite(self):
        r=run({'water':1000},oven_c=400,minutes=300,thickness_mm=2)
        self.assertTrue(math.isfinite(r['summary']['center_c']))
        self.assertTrue(0 <= r['summary']['mass_loss_pct'] <= 100)

    def test_extreme_nearly_pure_oil_and_syrup_are_finite(self):
        for recipe in ({'olive_oil':1000}, {'water':1000}, {'sugar':1000,'water':220}):
            with self.subTest(recipe=recipe):
                r=run(recipe,oven_c=400,minutes=100,thickness_mm=2)
                s=r['summary']
                self.assertTrue(all(math.isfinite(float(s[k])) for k in ('center_c','surface_c','mass_loss_pct','rise_pct')))
                self.assertLessEqual(s['mass_loss_pct'],100)
                self.assertGreaterEqual(s['end_mass_g'],0)

    def test_zero_time(self):
        r=run(minutes=0,initial_c=29)
        self.assertAlmostEqual(r['summary']['center_c'],29)
        self.assertEqual(r['summary']['mass_loss_pct'],0)

    def test_boundary_no_spurious_heating(self):
        r=run(oven_c=22,initial_c=22,minutes=15,steam_pct=100)
        self.assertAlmostEqual(r['summary']['center_c'],22,delta=.01)

    def test_proofing_produces_gas_and_expansion(self):
        base=run(proof_minutes=0)['summary']
        proof=run(proof_minutes=60,proof_c=29)['summary']
        self.assertGreater(proof['co2_generated_g'],base['co2_generated_g'])
        self.assertGreater(proof['proof_rise_pct'],0)
        self.assertGreater(proof['rise_pct'],base['rise_pct'])
        self.assertGreater(proof['thickness_mm_est'],base['thickness_mm_est'])

    def test_yeast_removal_removes_fermentation(self):
        r=run({'bread_flour':500,'water':340,'salt':10},proof_minutes=180)['summary']
        self.assertEqual(r['co2_generated_g'],0)
        self.assertEqual(r['co2_retained_g'],0)

    def test_salt_extreme_inhibits_fermentation(self):
        lean=run({'bread_flour':500,'water':340,'instant_yeast':5,'salt':10},proof_minutes=50)['summary']
        salty=run({'bread_flour':500,'water':340,'instant_yeast':5,'salt':150},proof_minutes=50)['summary']
        self.assertGreater(lean['co2_generated_g'],salty['co2_generated_g'])

    def test_chemical_leavener_is_gas_source(self):
        plain=run({'ap_flour':250,'milk':200,'egg':100},oven_c=185,minutes=35,thickness_mm=40)['summary']
        leavened=run({'ap_flour':250,'milk':200,'egg':100,'baking_powder':10},oven_c=185,minutes=35,thickness_mm=40)['summary']
        self.assertGreater(leavened['co2_generated_g'],plain['co2_generated_g'])
        self.assertGreater(leavened['rise_pct'],plain['rise_pct'])

    def test_baking_soda_not_assumed_reactive_without_acid(self):
        r=run({'water':200,'baking_soda':40},minutes=60)
        self.assertEqual(r['summary']['co2_generated_g'],0)
        self.assertTrue(any('Baking soda gas' in w for w in r['warnings']))

    def test_extreme_proof_bounded_and_finite(self):
        r=run({'bread_flour':500,'water':340,'instant_yeast':100},proof_minutes=720,proof_c=35,oven_c=400,minutes=300,thickness_mm=2)
        s=r['summary']
        self.assertTrue(math.isfinite(s['rise_pct']))
        self.assertTrue(math.isfinite(s['center_c']))
        self.assertTrue(-50 <= s['rise_pct'] <= 250)

    def test_small_yeast_change_continuous(self):
        a=run({'bread_flour':500,'water':340,'instant_yeast':5.0},proof_minutes=60)['summary']['proof_rise_pct']
        b=run({'bread_flour':500,'water':340,'instant_yeast':5.1},proof_minutes=60)['summary']['proof_rise_pct']
        self.assertGreater(b,a)
        self.assertLess(b-a,5)

    def test_gas_timeline_tracks_final_summary(self):
        r=run(proof_minutes=70)
        self.assertAlmostEqual(r['timeline'][-1]['rise_pct'],r['summary']['rise_pct'],delta=.001)
        self.assertAlmostEqual(r['timeline'][-1]['co2_generated_g'],r['summary']['co2_generated_g'],delta=.001)

    def test_invalid_amount_rejected(self):
        with self.assertRaises(ValueError):run({'bread_flour':-12})
        with self.assertRaises(ValueError):run({'bread_flour':float('nan')})
        with self.assertRaises(ValueError):run({'garbage':100})
        with self.assertRaises(ValueError):run({'water':0})

    def test_invalid_setting_rejected(self):
        with self.assertRaises(ValueError):run(oven_c=401)
        with self.assertRaises(ValueError):run(thickness_mm=0)

    def test_composition_properties_positive(self):
        for item in CATALOG:
            c=composition_of(CATALOG,{item['id']:10})['fraction']
            for temp in (0,60,120,220):
                cp,k=physical_properties(c,temp)
                self.assertGreater(cp,0)
                self.assertGreater(k,0)

    def test_profiles_and_monotonic_timeline(self):
        r=run()
        self.assertEqual(len(r['profile']['temp_c']),r['metadata']['grid_cells'])
        self.assertEqual(r['timeline'][0]['minute'],0)
        self.assertAlmostEqual(r['timeline'][-1]['minute'],35)
        self.assertTrue(all(r['timeline'][i]['minute']<r['timeline'][i+1]['minute'] for i in range(len(r['timeline'])-1)))
        self.assertTrue(all(len(item['temp_profile'])==r['metadata']['grid_cells'] for item in r['timeline']))

if __name__=='__main__':unittest.main()
