"""Real browser adversarial probes for captured state, media and materials."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from test_release import p, plan


class Engine43Tests(unittest.TestCase):
    def run_probe(self, body, steps, css='', region=None):
        temporary=tempfile.TemporaryDirectory(prefix='frontend-43-engine-')
        self.addCleanup(temporary.cleanup)
        root=Path(temporary.name)
        (root/'index.html').write_text('<meta charset="utf-8"><style>html{font-family:Arial,SimSun,serif}body,input,button,textarea,select{font-family:inherit}body{min-height:100vh;background:linear-gradient(20deg,#f4f1e7,#ede8dc)}'+css+'</style>'+body,encoding='utf-8')
        task=plan(root)
        if region:task['scope'][0]['root_selector']=region
        task['assets']=[{'path':'asset.svg','render_check':{'page':'main','width':390,'state':'default','selector':'#art'}}]
        (root/'asset.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><rect width="20" height="20" fill="red"/></svg>')
        p.save(root/p.TASK_PATH,task)
        p.save(root/'spec.json',{'cases':[{'page':'main','width':390,'state':'default','url':(root/'index.html').as_uri(),'steps':steps}]})
        result=subprocess.run([shutil.which('node'),str(Path(__file__).resolve().parents[1]/'browser-run.cjs'),str(root),str(root/'spec.json'),str(root/'result.json')],capture_output=True,text=True,encoding='utf-8',timeout=40)
        output=p.load(root/'result.json')
        snapshot=p.load(root/output['captures'][0]) if result.returncode==0 else None
        return result,output,snapshot

    def test_noop_button_cannot_claim_changed_state(self):
        result,output,_=self.run_probe('<button id="action">Try</button><output id="result">ready</output>',[
            {'action':'remember_state','selector':'#result','property':'text','name':'result'},
            {'action':'click','selector':'#action'},
            {'action':'expect_state_changed','name':'result','timeout_ms':100}])
        self.assertNotEqual(result.returncode,0)
        self.assertIn('State did not change',output['error'])

    def test_async_result_and_text_assertion_are_measured(self):
        result,output,_=self.run_probe('<button id="action" onclick="setTimeout(()=>document.querySelector(\'#result\').textContent=\'done\',350)">Try</button><output id="result">ready</output>',[
            {'action':'remember_state','selector':'#result','property':'text','name':'result','value':'ready'},
            {'action':'click','selector':'#action'},
            {'action':'expect_state_changed','name':'result','value':'done'},
            {'action':'expect_text','selector':'#result','value':'done'}])
        self.assertEqual(result.returncode,0,result.stderr)
        change=output['assertions'][0]['state_changes'][0]
        self.assertEqual((change['before'],change['after']),('ready','done'))
        self.assertEqual(change['trigger_steps'],[{'action':'click','selector':'#action'}])

    def test_async_expect_text_waits_without_state_capture(self):
        result,_,_=self.run_probe('<button id="action" onclick="setTimeout(()=>document.querySelector(\'#result\').textContent=\'done\',350)">Try</button><output id="result">ready</output>',[
            {'action':'click','selector':'#action'},{'action':'expect_text','selector':'#result','value':'done'}])
        self.assertEqual(result.returncode,0,result.stderr)

    def test_changed_state_requires_intervening_input(self):
        result,output,_=self.run_probe('<output id="result">ready</output>',[
            {'action':'remember_state','selector':'#result','property':'text','name':'result'},
            {'action':'expect_state_changed','name':'result','timeout_ms':100}])
        self.assertNotEqual(result.returncode,0)
        self.assertIn('intervening input',output['error'])

    def test_visible_media_binding_excludes_transparent_ancestor(self):
        for transparent in (False,True):
            with self.subTest(transparent=transparent):
                result,_,snapshot=self.run_probe('<main><div style="opacity:'+('0' if transparent else '1')+'"><img id="art" src="asset.svg"></div></main>',[{'action':'expect_visible','selector':'main'}])
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(len(snapshot['images']),0 if transparent else 1)
                if not transparent:self.assertIn('#art',snapshot['images'][0]['selectors'])

    def test_expect_visible_rejects_zero_opacity(self):
        result,output,_=self.run_probe('<div style="opacity:0"><button id="action">Try</button></div>',[{'action':'expect_visible','selector':'#action','timeout_ms':100}])
        self.assertNotEqual(result.returncode,0)
        self.assertIn('not visibly painted',output['error'])

    def test_material_candidates_reject_flat_or_transparent_gradients(self):
        for declaration in ('linear-gradient(#eee,#eee)','linear-gradient(transparent,transparent)'):
            with self.subTest(declaration=declaration):
                result,_,snapshot=self.run_probe('<main>Probe</main>',[{'action':'expect_visible','selector':'main'}],'body{background:'+declaration+'}')
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertFalse(snapshot['surface']['material_candidates'])
                self.assertTrue(snapshot['surface']['rejected_material_layers'])
                self.assertTrue(p.quality_checks.rendered_candidates(snapshot)[1])

    def test_local_component_does_not_need_its_own_material(self):
        result,_,snapshot=self.run_probe('<button id="action">Try</button>',[{'action':'expect_visible','selector':'#action'}],region='#action')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(snapshot['surface']['scope'],'region')
        self.assertFalse(p.quality_checks.rendered_candidates(snapshot)[1])

    def test_button_hover_records_actual_style_change(self):
        result,output,_=self.run_probe('<button id="action">Try</button>',[
            {'action':'remember_style','selector':'#action','property':'transform','name':'hover'},
            {'action':'hover','selector':'#action'},
            {'action':'expect_style_changed','name':'hover'}],'#action:hover{transform:translateY(-3px)}')
        self.assertEqual(result.returncode,0,result.stderr)
        change=output['assertions'][0]['style_changes'][0]
        self.assertNotEqual(change['before'],change['after'])
        self.assertTrue(change['trigger_steps'])

    def test_changed_style_requires_intervening_input(self):
        result,output,_=self.run_probe('<button id="action">Try</button>',[
            {'action':'remember_style','selector':'#action','property':'transform','name':'hover'},
            {'action':'expect_style_changed','name':'hover','timeout_ms':100}])
        self.assertNotEqual(result.returncode,0)
        self.assertIn('intervening input',output['error'])

    def test_async_url_transition_and_url_assertion(self):
        result,output,_=self.run_probe('<button id="action" onclick="setTimeout(()=>location.hash=\'done\',350)">Try</button>',[
            {'action':'remember_state','property':'url','name':'navigation'},
            {'action':'click','selector':'#action'},
            {'action':'expect_state_changed','name':'navigation'}])
        self.assertEqual(result.returncode,0,result.stderr)
        change=output['assertions'][0]['state_changes'][0]
        self.assertTrue(change['after'].endswith('#done'))

    def test_form_state_properties(self):
        cases=[
            ('value','<input id="field" value="before">',{'action':'fill','selector':'#field','value':'after'},'after'),
            ('checked','<input id="field" type="checkbox">',{'action':'check','selector':'#field'},True),
            ('disabled','<button id="field" disabled>Try</button><button id="action" onclick="document.querySelector(\'#field\').disabled=false">Enable</button>',{'action':'click','selector':'#action'},False),
            ('attribute','<button id="field" aria-expanded="false" onclick="this.setAttribute(\'aria-expanded\',\'true\')">Open</button>',{'action':'click','selector':'#field'},'true'),
            ('visible','<div id="field" hidden>Details</div><button id="action" onclick="document.querySelector(\'#field\').hidden=false">Open</button>',{'action':'click','selector':'#action'},True),
        ]
        for property,body,trigger,expected in cases:
            with self.subTest(property=property):
                baseline={'action':'remember_state','name':'state','selector':'#field','property':property}
                if property=='attribute':baseline['attribute']='aria-expanded'
                result,output,_=self.run_probe(body,[baseline,trigger,{'action':'expect_state_changed','name':'state','value':expected}])
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(output['assertions'][0]['state_changes'][0]['after'],expected)

    def test_fully_clipped_image_is_not_visible(self):
        result,output,_=self.run_probe('<div style="width:0;height:0;overflow:hidden"><img id="art" src="asset.svg"></div>',[{'action':'expect_visible','selector':'#art','timeout_ms':100}])
        self.assertNotEqual(result.returncode,0)
        self.assertIn('not visibly painted',output['error'])


if __name__=='__main__':unittest.main()
