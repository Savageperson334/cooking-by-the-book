"""Regression tests for the distinct physical/chemical cracking interfaces.

Physical fracture is a drying-gradient index; triglyceride cracking is a
separate high-temperature chemistry proxy. Neither predicts ignition.
"""
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import simulate

CAT = json.loads((ROOT / "ingredients.json").read_text(encoding="utf-8"))

def run(mix, temp=220, minutes=90, depth=15, air=100):
    return simulate({
        "catalog": CAT, "amounts": mix,
        "settings": {
            "oven_c": temp, "minutes": minutes,
            "thickness_mm": depth, "proof_minutes": 0,
            "air_access_pct": air,
        },
    })

class TestDistinctCrackingModes(unittest.TestCase):
    def test_pure_water_never_has_char_or_cracking(self):
        s = run({"water":1000}, 600, 360)["summary"]
        self.assertEqual(s["estimated_triglyceride_cracked_pct"], 0)
        self.assertEqual(s["estimated_char_g"], 0)
        self.assertEqual(s["physical_crack_risk_pct"], 0)
        self.assertIsNone(s["estimated_cracking_1pct_crossing_min"])

    def test_hot_oil_chemically_cracks_without_solid_fracture(self):
        s = run({"olive_oil":700}, 600, 90)["summary"]
        self.assertGreater(s["estimated_triglyceride_cracked_pct"], 10)
        self.assertEqual(s["physical_crack_risk_pct"], 0)
        self.assertIsNotNone(s["estimated_cracking_1pct_crossing_min"])

    def test_normal_heating_is_not_the_same_as_high_temperature_cracking(self):
        s = run({"olive_oil":700}, 220, 120)["summary"]
        self.assertLess(s["estimated_triglyceride_cracked_pct"], 1)
        self.assertIsNone(s["estimated_cracking_1pct_crossing_min"])

    def test_bread_can_have_physical_fissure_risk_without_oil_cracking(self):
        r = run({"bread_flour":500,"water":320,"salt":8}, 220, 70, 60)
        self.assertGreater(max(x["physical_crack_risk_pct"] for x in r["timeline"]), 10)
        self.assertLess(r["summary"]["estimated_triglyceride_cracked_pct"], 1)

    def test_banana_slurry_is_separate_from_bread_fracture(self):
        r = run({"banana":250,"water":500}, 240, 180)
        s = r["summary"]
        self.assertGreater(s["mass_loss_pct"], 0)
        self.assertGreaterEqual(s["physical_crack_risk_pct"], 0)
        self.assertLessEqual(s["physical_crack_risk_pct"], 100)

    def test_inert_mineral_residue(self):
        s = run({"salt":100}, 600, 360)["summary"]
        self.assertAlmostEqual(s["estimated_remaining_mass_g"], 100, delta=0.01)
        self.assertEqual(s["estimated_char_g"], 0)
        self.assertEqual(s["physical_crack_risk_pct"], 0)
        self.assertEqual(s["estimated_triglyceride_cracked_g"], 0)

    def test_chemical_conversion_is_monotonic(self):
        rows = run({"olive_oil":600}, 400, 120)["timeline"]
        self.assertGreater(rows[-1]["estimated_triglyceride_cracked_pct"], 0)
        for a,b in zip(rows, rows[1:]):
            self.assertGreaterEqual(
                b["estimated_triglyceride_cracked_pct"]+0.002,
                a["estimated_triglyceride_cracked_pct"])
            self.assertGreaterEqual(b["estimated_remaining_mass_g"], 0)

    def test_chemical_crossing_is_a_timeline_threshold(self):
        s = run({"olive_oil":600}, 400, 120)["summary"]
        self.assertGreater(s["estimated_cracking_1pct_crossing_min"], 0)
        self.assertLess(s["estimated_cracking_1pct_crossing_min"], 120)

    def test_extreme_fields_are_finite(self):
        for mix in (
            {"water":1000}, {"olive_oil":600}, {"banana":250,"water":500},
            {"bread_flour":500,"water":350}, {"oats":200,"water":500},
            {"salt":100},
        ):
            with self.subTest(mix=mix):
                r = run(mix, 600, 360)
                for frame in r["timeline"]:
                    for field in (
                        "physical_crack_risk_pct", "physical_shrinkage_drive",
                        "physical_gradient_drive", "estimated_triglyceride_cracked_pct",
                        "estimated_triglyceride_cracked_g",
                        "estimated_remaining_mass_g",
                    ):
                        self.assertTrue(math.isfinite(frame[field]), (mix,field))
                        self.assertGreaterEqual(frame[field], 0)
                    self.assertLessEqual(frame["estimated_triglyceride_cracked_pct"], 100.01)

    def test_independent_crossing_times_have_material_temperatures(self):
        oil = run({"olive_oil":700}, 600, 90)["summary"]
        self.assertIsNotNone(oil["estimated_cracking_1pct_crossing_min"])
        self.assertIsNotNone(oil["estimated_cracking_1pct_material_c"])
        self.assertGreater(oil["estimated_cracking_1pct_material_c"], 0)
        self.assertLessEqual(oil["estimated_cracking_1pct_material_c"], 600.01)

        bread = run({"bread_flour":500,"water":320,"salt":8}, 220, 70, 60)["summary"]
        self.assertIn("physical_crack_proxy_20pct_crossing_min", bread)
        self.assertIn("physical_crack_proxy_20pct_surface_c", bread)
        if bread["physical_crack_proxy_20pct_crossing_min"] is not None:
            self.assertIsNotNone(bread["physical_crack_proxy_20pct_surface_c"])
            self.assertLessEqual(bread["physical_crack_proxy_20pct_surface_c"], 220.01)

    def test_ui_exposes_both_cracking_modes(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn('value="fracture"', html)
        self.assertIn('value="chemcrack"', html)
        self.assertIn('id="thermal-chem"', html)
        self.assertIn('id="thermal-chem-point"', html)
        self.assertIn('id="thermal-fracture-point"', html)
        self.assertIn("'physical_crack_risk_pct'",js)
        self.assertIn("'estimated_triglyceride_cracked_pct'",js)

if __name__ == "__main__":
    unittest.main()
