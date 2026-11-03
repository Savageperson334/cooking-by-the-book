"""The word 'cracking' must never conflate physical fracture with oil thermolysis."""
import json
import math
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import engine
CAT=json.loads((ROOT/'ingredients.json').read_text(encoding='utf-8'))


def run(amounts,temp=400,minutes=120,depth=15,air=100):
    return engine.simulate({'catalog':CAT,'amounts':amounts,
        'settings':{'oven_c':temp,'minutes':minutes,'thickness_mm':depth,
                    'air_access_pct':air}})


class CrackingSeparationTests(unittest.TestCase):
    def test_pure_oil_chemistry_not_surface_fracture(self):
        sim=run({'olive_oil':600},400,120)
        summary=sim['summary']
        self.assertGreater(summary['estimated_triglyceride_cracked_g'],20)
        self.assertGreater(summary['estimated_triglyceride_cracked_pct'],10)
        self.assertEqual(summary['physical_crack_risk_pct'],0)
        self.assertIsNotNone(summary['estimated_cracking_1pct_crossing_min'])
        self.assertTrue(all('physical_crack_risk_pct' in f for f in sim['timeline']))

    def test_water_and_salt_have_no_chemical_or_physical_cracking(self):
        for mix in ({'water':500},{'salt':400}):
            with self.subTest(mix=mix):
                result=run(mix,600,360)['summary']
                self.assertEqual(result['estimated_triglyceride_cracked_pct'],0)
                self.assertEqual(result['estimated_triglyceride_cracked_g'],0)
                self.assertEqual(result['physical_crack_risk_pct'],0)
                self.assertIsNone(result['estimated_cracking_1pct_crossing_min'])

    def test_dryable_bread_has_physical_risk(self):
        result=run({'bread_flour':500,'water':350,'salt':10,'instant_yeast':5},220,45)
        maximum=max(f['physical_crack_risk_pct'] for f in result['timeline'])
        self.assertGreater(maximum,10)
        self.assertGreater(result['summary']['physical_shrinkage_drive'],0)
        self.assertTrue(all(f['physical_moisture_contrast_pct']>=0 for f in result['timeline']))

    def test_time_and_temperature_change_oil_cleavage(self):
        inputs={'olive_oil':400}
        mild=run(inputs,230,25)['summary']['estimated_triglyceride_cracked_pct']
        hot=run(inputs,400,25)['summary']['estimated_triglyceride_cracked_pct']
        hot_long=run(inputs,400,95)['summary']['estimated_triglyceride_cracked_pct']
        self.assertLess(mild,1.0)
        self.assertGreater(hot,mild)
        self.assertGreaterEqual(hot_long,hot)

    def test_mass_ledger_is_bounded_for_oil_milk_oats_banana(self):
        for amounts in ({'olive_oil':600},{'water':500,'milk':250,'olive_oil':100},
                        {'water':500,'banana':250},{'water':600,'oats':200}):
            with self.subTest(amounts=amounts):
                sim=run(amounts,500,240)
                total=sum(amounts.values())
                initial_water=total*sim['summary']['water_pct']/100
                for frame in sim['timeline'][::max(1,len(sim['timeline'])//15)]:
                    left=frame['estimated_remaining_mass_g']
                    water_lost=total*frame['mass_loss_pct']/100
                    organic_lost=frame['estimated_volatile_loss_g']+frame['estimated_char_oxidation_loss_g']
                    self.assertGreaterEqual(left,-1e-8)
                    self.assertLessEqual(left,total+0.01)
                    self.assertAlmostEqual(left+water_lost+organic_lost,total,delta=0.13)
                    self.assertLessEqual(frame['estimated_triglyceride_cracked_g'],total+0.01)
                    self.assertGreaterEqual(frame['estimated_light_fragments_g'],0)

    def test_no_universal_cracking_point(self):
        # A model crossing at 1% is documented as a numerical reporting marker,
        # not a material-specific threshold temperature or ignition point.
        sim=run({'olive_oil':600},400,120)
        crossing=sim['summary']['estimated_cracking_1pct_crossing_min']
        self.assertGreater(crossing,0)
        self.assertLess(crossing,120)
        self.assertIn('physical_fracture',sim['metadata'])
        self.assertIn('upper_end',sim['metadata'])

    def test_browser_worker_fetches_both_independent_modules(self):
        worker=(ROOT/'worker.js').read_text(encoding='utf-8')
        js=(ROOT/'app.js').read_text(encoding='utf-8')
        html=(ROOT/'index.html').read_text(encoding='utf-8')
        self.assertIn('physical_fracture.py',worker)
        self.assertIn('thermal_breakdown.py',worker)
        self.assertIn("'physical_crack_risk_pct'",js)
        self.assertIn("'estimated_triglyceride_cracked_pct'",js)
        self.assertIn('id="thermal-chem"',html)
        self.assertIn('value="chemcrack"',html)


if __name__=='__main__': unittest.main()
