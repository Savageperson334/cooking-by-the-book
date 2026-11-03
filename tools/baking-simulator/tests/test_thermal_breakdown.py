"""Regression coverage for high-temperature matter loss and visual contract."""
import json, math, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine import simulate
CAT=json.loads((ROOT/'ingredients.json').read_text())

def run(amounts,oven=600,mins=360,air=100,depth=15):
    return simulate({'catalog':CAT,'amounts':amounts,'settings':{'oven_c':oven,'minutes':mins,'thickness_mm':depth,'proof_minutes':0,'air_access_pct':air,'fan':1}})

class TestHighEnd(unittest.TestCase):
    def test_original_six_hour_600c_error_repaired_as_estimate(self):
        for amounts in ({'banana':250,'water':500},{'oats':200,'water':600},
                        {'sugar':400,'water':300},{'olive_oil':600},
                        {'milk':600},{'bread_flour':500,'water':340}):
            with self.subTest(amounts=amounts):
                r=run(amounts);s=r['summary']
                self.assertLess(s['estimated_remaining_mass_g'],s['end_mass_g']*0.7)
                self.assertGreater(s['estimated_total_mass_loss_pct'],s['mass_loss_pct'])
                self.assertLessEqual(s['estimated_remaining_mass_g'],s['total_g']+0.01)
                self.assertAlmostEqual(s['total_g'],s['estimated_remaining_mass_g'] + s['estimated_total_mass_loss_pct']*s['total_g']/100,delta=0.04)
    def test_salt_survives_600_no_invented_char(self):
        s=run({'salt':100})['summary']
        self.assertAlmostEqual(s['estimated_remaining_mass_g'],100,delta=0.01)
        self.assertEqual(s['estimated_char_g'],0)
        self.assertEqual(s['estimated_ash_g'],100)
    def test_pure_water_no_false_ash(self):
        s=run({'water':1000})['summary']
        self.assertEqual(s['estimated_remaining_mass_g'],0)
        self.assertEqual(s['estimated_ash_g'],0)
        self.assertEqual(s['estimated_char_g'],0)
    def test_air_retains_more_char_when_restricted(self):
        r1=run({'water':350,'banana':400},oven=370,mins=150,air=0)
        r2=run({'water':350,'banana':400},oven=370,mins=150,air=100)
        self.assertGreaterEqual(r1['summary']['estimated_char_g'],r2['summary']['estimated_char_g'])
    def test_no_phantom_matter_or_negative_mass_across_ranges(self):
        for amount in ({'water':1000},{'salt':100},{'olive_oil':1000},{'banana':200,'water':500},{'sugar':500,'water':100}):
            for temp in (140,260,600):
                with self.subTest(amount=amount,temp=temp):
                    r=run(amount,oven=temp,mins=120)
                    for f in r['timeline']:
                        for k in ('estimated_remaining_mass_g','estimated_char_g','estimated_intact_organic_g','estimated_ash_g','estimated_total_mass_loss_pct','crack_risk_index_pct'):
                            self.assertTrue(math.isfinite(f[k]),(amount,temp,k))
                            self.assertGreaterEqual(f[k],0,(amount,temp,k))
                        self.assertLessEqual(f['estimated_remaining_mass_g'],r['summary']['total_g']+0.1)
    def test_browning_not_disguised_as_pyrolysis(self):
        r=run({'water':1000},oven=160,mins=30)
        self.assertEqual(r['summary']['estimated_char_g'],0)
        self.assertEqual(r['summary']['estimated_volatile_loss_g'],0)
    def test_no_mechanical_cracking_in_pure_salt_or_oil(self):
        for amt in ({'salt':100},{'olive_oil':600}):
            r=run(amt,oven=600,mins=250)
            self.assertLess(r['summary']['crack_risk_index_pct'],10)
    def test_field_contract(self):
        js=(ROOT/'app.js').read_text();html=(ROOT/'index.html').read_text();worker=(ROOT/'worker.js').read_text()
        self.assertIn('thermal_breakdown.py',worker)
        for id in ['thermal-remain','thermal-char','thermal-ash','thermal-crack']:
            self.assertIn(f'id="{id}"',html);self.assertIn(f"$('{id}')",js)
        self.assertIn('value="survival"',html)
        self.assertIn('value="fracture"',html)
        self.assertIn('BUILD 0.9',html)

if __name__=='__main__': unittest.main()
