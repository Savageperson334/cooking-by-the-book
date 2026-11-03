import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]

class TestUIContract(unittest.TestCase):
    def test_pyodide_module_worker(self):
        js = (HERE / 'worker.js').read_text()
        app = (HERE / 'app.js').read_text()
        self.assertIn('{ loadPyodide } = await import(PYODIDE_URL)', js)
        self.assertIn("pyodide/v314.0.7/full/pyodide.mjs", js)
        self.assertNotIn('importScripts(', js)
        # A failed CDN download must surface a readable message, not a generic worker error.
        self.assertIn('Could not download the Python runtime', js)
        self.assertIn("new Worker('./worker.js?ui=0.11.0',{type:'module'})", app)

    def test_ui_release_uses_versioned_assets(self):
        html = (HERE / 'index.html').read_text()
        app = (HERE / 'app.js').read_text()
        self.assertIn('BUILD 0.11.0', html)
        self.assertIn('./app.js?ui=0.11.0', html)
        self.assertIn('./style.css?ui=0.11.0', html)
        self.assertIn('./worker.js?ui=0.11.0', app)
        # SVG labels must not be reintroduced: show metrics below the pan.
        self.assertNotIn('ANGLED PAN · ILLUSTRATIVE', app)
        for identifier in ('scene-oven', 'scene-thickness',
                           'scene-rise', 'scene-warning-details'):
            self.assertIn(f'id="{identifier}"', html)

    def test_shape_and_pan_choices_match_python(self):
        import re, sys
        sys.path.insert(0, str(HERE))
        import geometry
        app = (HERE / 'app.js').read_text()
        js_shapes = re.findall(r"\['(\w+)','[^']*'\]", app[app.index('const shapeOptions'):app.index('const panOptions')])
        js_pans = re.findall(r"\['(\w+)','[^']*'\]", app[app.index('const panOptions'):app.index('\n', app.index('const panOptions'))])
        self.assertEqual(js_shapes, list(geometry.SHAPES))
        self.assertEqual(js_pans, list(geometry.PANS))
        self.assertIn("shape:'slab',pan:'none'", app)

    def test_worker_loads_geometry_and_versions_python_files(self):
        js = (HERE / 'worker.js').read_text()
        self.assertIn("get('geometry.py')", js)
        self.assertIn("/home/pyodide/geometry.py", js)
        self.assertIn("searchParams.get('ui')", js)

    def test_worker_skips_superseded_runs(self):
        js = (HERE / 'worker.js').read_text()
        self.assertIn('latestId = Math.max(latestId, id)', js)
        self.assertIn('if (id !== latestId) return;', js)

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

    def test_bake_readouts_do_not_overlap_svg_scene(self):
        html = (HERE / 'index.html').read_text()
        js = (HERE / 'app.js').read_text()
        css = (HERE / 'style.css').read_text()
        for identifier in ('scene-oven', 'scene-thickness', 'scene-rise',
                           'scene-warning-details', 'scene-warning-text'):
            self.assertIn(f'id="{identifier}"', html)
            self.assertIn("'" + identifier + "'", js)
        pan_end = html.index('</svg></div>', html.index('id="bake-scene"'))
        readouts = html.index('class="scene-readouts"')
        self.assertGreater(readouts, pan_end)
        self.assertNotIn("'ANGLED PAN · ILLUSTRATIVE'", js)
        self.assertNotIn("'⚠ model boundary'", js)
        self.assertIn('.scene-readouts', css)

    def test_no_floating_oven_halo_in_browser_artwork(self):
        js = (HERE / 'app.js').read_text()
        css = (HERE / 'style.css').read_text()
        # Two layers previously produced the same floating semicircle:
        # the decorative SVG ellipse and the CSS radial background.
        self.assertNotIn("cx:380,cy:46,rx:228,ry:34", js)
        self.assertNotIn("0.15*ovenGlow", js)
        self.assertNotIn("radial-gradient(circle at 50% 8%", css)
        self.assertIn("linear-gradient(180deg,#1a2529", css)

    def test_svg_text_helper_avoids_invalid_append_return(self):
        js=(HERE/'app.js').read_text()
        self.assertNotIn(')).textContent=', js)
        self.assertIn('function svgText(', js)

if __name__ == '__main__': unittest.main()
