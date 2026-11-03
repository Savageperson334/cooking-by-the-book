import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]

class TestUIContract(unittest.TestCase):
    def test_pyodide_module_worker(self):
        js = (HERE / 'worker.js').read_text()
        app = (HERE / 'app.js').read_text()
        self.assertIn('import { loadPyodide }', js)
        self.assertNotIn('importScripts(', js)
        self.assertIn("new Worker('./worker.js',{type:'module'})", app)

    def test_gas_controls_outputs_and_export_are_wired(self):
        html = (HERE / 'index.html').read_text()
        js = (HERE / 'app.js').read_text()
        for key in ('proof_minutes','proof_c','rise_pct','co2_generated_g'):
            self.assertIn(key, js)
        for key in ('value="rise"','value="gas"','Rise estimate','CO₂ generated'):
            self.assertIn(key, html)
        self.assertEqual(html.count('<article>'), 6)

    def test_viewport_controls_and_aria_are_wired(self):
        html = (HERE / 'index.html').read_text()
        js = (HERE / 'app.js').read_text()
        for key in ('scene-play','scene-reset','scene-speed','scrub-scene','scene-clock','bake-scene'):
            self.assertIn(f'id="{key}"', html)
            self.assertIn(key, js)
        for item in ('purewater','syrup','pureoil'):
            self.assertIn(f'value="{item}"', html)
            self.assertIn(item, js)
        self.assertIn('requestAnimationFrame(stepPlayback)', js)

    def test_svg_text_helper_avoids_invalid_append_return(self):
        js=(HERE/'app.js').read_text()
        self.assertNotIn(')).textContent=', js)
        self.assertIn('function svgText(', js)

if __name__ == '__main__': unittest.main()
