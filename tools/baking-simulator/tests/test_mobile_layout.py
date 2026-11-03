"""No browser dependency in CI: verify stable preview and accessible tab structure."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class Structure(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.elements={};self.tabs=[];self.panels=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);self.stack.append((tag,a))
        if a.get('id'):self.elements.setdefault(a['id'],[]).append((tag,a,[x[1].get('id') for x in self.stack]))
        if a.get('role')=='tab':self.tabs.append(a)
        if a.get('role')=='tabpanel':self.panels.append(a)
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs);self.stack.pop()
    def handle_endtag(self,tag):
        # HTML source uses balanced tags for structural elements.
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                self.stack=self.stack[:i];break

class TestMobileWorkspace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(ROOT/'index.html').read_text()
        cls.css=(ROOT/'style.css').read_text()
        cls.js=(ROOT/'app.js').read_text()
        cls.structure=Structure();cls.structure.feed(cls.html)

    def test_four_accessible_tabs_with_unique_targets(self):
        expected=['ingredients','process','results','compare']
        self.assertEqual([t['data-tab'] for t in self.structure.tabs],expected)
        self.assertEqual([p['id'] for p in self.structure.panels],['panel-'+x for x in expected])
        for name in expected:
            self.assertEqual(len(self.structure.elements['tab-'+name]),1)
            self.assertEqual(len(self.structure.elements['panel-'+name]),1)
        self.assertEqual(self.structure.tabs[0]['aria-selected'],'true')
        self.assertEqual([p.get('hidden') for p in self.structure.panels],[None,'','',''])

    def test_viewport_outside_all_switchable_panels(self):
        scene=self.structure.elements['bake-scene']
        self.assertEqual(len(scene),1)
        ancestors=scene[0][2]
        self.assertFalse(any(x and x.startswith('panel-') for x in ancestors))
        for n in ('scene-play','scene-reset','scrub-scene','run','run-indicator'):
            self.assertEqual(len(self.structure.elements[n]),1)
        self.assertIn('position:sticky',self.css)
        self.assertIn('.preview-dock',self.css)

    def test_tab_switch_preserves_scenario_and_scene(self):
        self.assertIn('function setupTabs()',self.js)
        self.assertIn('panel.hidden=!on',self.js)
        self.assertIn("tab.addEventListener('keydown'",self.js)
        self.assertIn('ArrowRight',self.js)
        self.assertIn('compactScene',self.js)
        self.assertIn('updateScrub(playValue)',self.js)
        self.assertNotIn('queueRun();\n function activate(',self.js)

if __name__=='__main__':unittest.main()
