"""Independent physical fracture versus chemical decomposition smoke tests.

Assertions are numerical/qualitative model contracts, not empirical validation.
"""
import json
import math
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import simulate
CAT = json.loads((ROOT / 'ingredients.json').read_text())

def run(mix, temp=220, minutes=90, depth=15, air=100):
    return simulate({'catalog':CAT,'amounts':mix,'settings':{'oven_c':temp,'minutes':minutes,'thickness_mm':depth,'proof_minutes':0,'air_access_pct':air}})

class TestDifferentCrackingProcesses(unittest.TestCase):
    def test_water_cannot_generate_char_fissures_or_fat_cracking(self):
        s = run({'water':1000},600,360)['summary']
        self.assertEqual(s['chemical_conversion_pct'],0)
        self.assertEqual(s['fat_thermal_conversion_pct'],0)
        self.assertEqual(s['visible_fracture_pct'],0)
        self.assertIsNone(s['fat_conversion_10pct_min'])
    def test_fat_can_decompose_without_physical_crust_fissures(self):
        r = run({'olive_oil':700},600,90)
        s = r['summary']
        self.assertGreater(s['fat_thermal_conversion_pct'],80)
        self.assertLess(s['fracture_damage_pct'],1)
        self.assertLess(s['visible_fracture_pct'],1)
        self.assertIsNotNone(s['fat_conversion_10pct_min'])
    def test_low_heat_is_not_fat_thermolysis_point(self):
        s=run({'olive_oil':700},220,120)['summary']
        self.assertLess(s['fat_thermal_conversion_pct'],5)
        self.assertIsNone(s['fat_conversion_10pct_min'])
    def test_lower_heat_creates_crust_stress_without_chemical_breakdown(self):
        s=run({'bread_flour':500,'water':320,'salt':8},220,70,60)['summary']
        self.assertGreater(s['fracture_damage_pct'],20)
        self.assertLess(s['chemical_conversion_pct'],10)
    def test_banana_water_can_make_mechanical_fissures_before_decomposition(self):
        r=run({'banana':250,'water':500},240,180)
        s=r['summary']
        self.assertGreater(s['fracture_damage_pct'],20)
        self.assertIsNotNone(s['crack_risk_onset_min'])
    def test_minerals_survive_and_cannot_form_organic_crack_model(self):
        s=run({'salt':100},600,360)['summary']
        self.assertEqual(s['estimated_remaining_mass_g'],100)
        self.assertEqual(s['chemical_conversion_pct'],0)
        self.assertEqual(s['visible_fracture_pct'],0)
    def test_triglyceride_conversion_percentage_non_decreasing(self):
        rows=run({'olive_oil':600},380,120)['timeline']
        self.assertGreater(rows[-1]['fat_thermal_conversion_pct'],rows[0]['fat_thermal_conversion_pct'])
        for a,b in zip(rows,rows[1:]):
            self.assertGreaterEqual(b['fat_thermal_conversion_pct']+1e-4,a['fat_thermal_conversion_pct'])
            self.assertGreaterEqual(b['estimated_remaining_mass_g'],0)
    def test_chemical_10pct_threshold_is_modelled_food_temp_not_oven(self):
        s=run({'olive_oil':600},600,90)['summary']
        self.assertIsNotNone(s['fat_conversion_10pct_min'])
        self.assertLessEqual(s['fat_conversion_10pct_material_c'],600.01)
    def test_all_new_fields_finite_over_extreme_cases(self):
        for mix in ({'water':1000},{'olive_oil':600},{'banana':250,'water':500},
                    {'bread_flour':500,'water':350},{'oats':200,'water':500},{'salt':100}):
            with self.subTest(mix=mix):
                r=run(mix,600,360)
                for row in r['timeline']:
                    for key in ('visible_fracture_pct','fracture_damage_pct','chemical_conversion_pct','fat_thermal_conversion_pct',
                                'fracture_stress_ratio_proxy','fracture_strain_proxy_pct'):
                        self.assertTrue(math.isfinite(row[key]),(mix,key))
                        self.assertGreaterEqual(row[key],0)
                    self.assertLessEqual(row['chemical_conversion_pct'],100.01)
                    self.assertLessEqual(row['fat_thermal_conversion_pct'],100.01)
    def test_ui_contract(self):
        html=(ROOT/'index.html').read_text()
        js=(ROOT/'app.js').read_text()
        for ident in ['fracture-damage','fracture-stress','chem-conversion','fat-conversion','fat-onset']:
            self.assertIn(f'id="{ident}"',html)
            self.assertIn(f"$('{ident}')",js)
        for metric in ['value="cracking"','value="chemistry"','value="fatbreak"']:
            self.assertIn(metric,html)
        self.assertIn('visible_fracture_pct',js)
        self.assertIn('fat_thermal_conversion_pct',js)

if __name__ == '__main__':unittest.main()
