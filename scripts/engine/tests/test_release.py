"""Release regressions: real browser, hostile records and preflight. No UI certification."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('release_policy',Path(__file__).resolve().parents[1]/'verify.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

def plan(root,level='L2',visual=True):
    task=p.init_task(root,level,'Controlled verification fixture',['index.html'],visual=visual,pages=['main'],widths=[390],replace=True)
    for item in task['rule_application']:item.update(applicability='out_of_scope',reason='Executable checker fixture only; no business UI acceptance.')
    task['design_plan']={'layout_regions':[{'selector':'main','decision':'Controlled diagnostic region'}],'typography':'Fixture type','material':'Fixture gradient','copy':'Short factual fixture strings','motion':'Fixture motion assertions'}
    task['design_document']='design.md'
    (root/'design.md').write_text('\n'.join('## '+section+'\nControlled '+section+' planning fixture for this diagnostic scope.\n' for section in p.preflight.DESIGN_SECTIONS),encoding='utf-8')
    task['design_plan'].update(scene='Diagnostic fixture',style_direction='Custom paper fixture',tokens={'ink':'#254c40'},dynamic_scope_reason='Local diagnostic fixture preserves existing interaction scope')
    if level=='L3':
        import base64
        (root/'reference.png').write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/58HAAMBAQDJ/pLvAAAAAElFTkSuQmCC'))
        task['selected_reference']='reference.png'
        task['design_plan']['dynamic_components']=[dynamic_component()]
        task['design_plan'].update(
            visual_surfaces=[{'selector':'body','color_roles':{'canvas':'#f4f1e7','ink':'#254c40'},'material':'Fixture two-color gradient','reference_features':'Synthetic fixture only; no visual fidelity certification'}],
            asset_coverage=[{'id':'fixture-object','role':'object_cutout','page':'main','selector':'#illustration','purpose':'Fixture scenario','decision':'generate','reason':'Synthetic planning-only illustration'}],
            button_feedback=[{'selector':'#target','page':'main','trigger':'Hover fixture button','states':['idle','hover'],'visual_response':'Measured shadow change','motion':'Short ease-out','reduced_motion':'Keep focus and immediate feedback','verification':{'page':'main','width':390,'state':'default','steps':[{'action':'remember_style','selector':'#target','property':'boxShadow','name':'button-shadow'},{'action':'hover','selector':'#target'},{'action':'expect_style_changed','selector':'#target','name':'button-shadow'}]}}])
        contract_text='# Synthetic style fixture\n\n### Implementation Contract\n\nPreserve diagnostic scope and check actual states.\n'
        (root/'style-source.md').write_text(contract_text,encoding='utf-8')
        document=(root/'design.md').read_text(encoding='utf-8')
        (root/'design.md').write_text(contract_text+'\n'+document,encoding='utf-8')
        task['style_contract']={'slug':'A','locale':'zh','path':'style-source.md','sha256':p.sha(root/'style-source.md'),'source_url':'fixture://style/A'}
        task['design_plan'].update(style_slug='A',document_locale='zh')
        task['style_discovery']='discovery.json'
        p.save(root/'discovery.json',{'scene':'Fixture','source':'fixture','queried_at':'test','mode':'new','options':[{'id':key,'style_name':'Style fixture '+key,'style_slug':key,'source':'fixture',**{field:field+' fixture '+key for field in ('layout','typography','components','material','imagery','motion')}} for key in 'ABCD']})
        (root/'motion-docs.md').write_text('Synthetic motion documentation fixture')
        task['design_plan']['motion_plan']={'engine':'fixture','reason':'test','docs_evidence':'motion-docs.md','pointer':{'decision':'omitted',**{key:'Fixture scope' for key in ('reason','touch_fallback','keyboard_fallback','reduced_motion','cleanup')}}}
    p.save(root/p.TASK_PATH,task)
    return task

def dynamic_component():
    return {'id':'practice-toggle','page':'main','selector':'#target','purpose':'Reveal the next practice state','trigger':'Click practice control','states':['ready','done'],'motion':'Short custom nonlinear feedback','reduced_motion':'Immediate state update',
            'verification':{'page':'main','width':390,'state':'default','steps':[{'action':'remember_state','selector':'#result','property':'text','name':'practice-result','value':'准备'},{'action':'click','selector':'#target'},{'action':'expect_state_changed','selector':'#result','name':'practice-result','value':'完成'}]}}

class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='fp-release-');self.root=Path(self.temp.name)
        (self.root/'index.html').write_text('<p>示例</p>',encoding='utf-8')
        self.center=patch.object(p,'CENTER',self.root/'center');self.center.start()
    def tearDown(self):self.center.stop();self.temp.cleanup()
    def test_short_alpha_and_named_colors(self):
        for color in ('#63c','#63cf','#6633ccff','rgb(40% 20% 80% / 1)','hsl(-100 60% 40%)','hsl(.72turn 60% 40%)','rebeccapurple'):
            self.assertTrue(p.forbidden_hue(color),color)
        for color in ('#63c0','#6633cc00','#183d32','rgb(20% 70% 20%)'):self.assertFalse(p.forbidden_hue(color),color)
    def test_split_spans_and_visual_aria_hidden_cannot_hide_long_sentence(self):
        for html in ('<div><span data-copy-unit>我已阅读并同意</span><a>用户协议</a><span>与</span><a>隐私政策</a></div>','<p aria-hidden="true">我已阅读并同意用户协议与隐私政策</p>'):
            self.assertTrue(p.text_findings(html,15),html)
    def test_comments_do_not_count_as_live_color(self):
        task=plan(self.root,level='L1',visual=False)
        (self.root/'index.html').write_text('<!-- #6366f1 Lorem Ipsum --><p>示例</p>',encoding='utf-8')
        self.assertEqual(p.source_findings(self.root,task),[])
    def test_asset_metadata_and_baseline_are_contract_bound(self):
        task=plan(self.root,visual=False);before=p.contract_hash(task)
        task['assets']=[{'path':'a.png','origin':'existing'}];self.assertNotEqual(before,p.contract_hash(task))
        baseline=next(iter(task['baseline'].values()));before=p.hashes(self.root,{**task,'assets':[]})
        (self.root/baseline).write_text('tampered',encoding='utf-8')
        self.assertNotEqual(before,p.hashes(self.root,{**task,'assets':[]}))
        self.assertNotEqual(p.verify(self.root,{**task,'assets':[]})['status'],'PASS')
    def test_edited_baseline_cannot_exempt_a_new_forbidden_color(self):
        task=plan(self.root,level='L1',visual=False)
        (self.root/'index.html').write_text('<p style="color:#6366f1">示例</p>',encoding='utf-8')
        (self.root/task['baseline']['index.html']).write_bytes((self.root/'index.html').read_bytes())
        result=p.verify(self.root)
        self.assertNotEqual(result['status'],'PASS')
        self.assertTrue(any('baseline was changed' in item for item in result['blockers']),result)
    def test_task_level_cannot_be_downgraded_after_init(self):
        task=plan(self.root);task['level']='L1';task['visual']=False;task['checks']=[{'id':'source','type':'source','required':True}]
        result=p.verify(self.root,task)
        self.assertNotEqual(result['status'],'PASS')
        self.assertTrue(any('level/phase changed' in item for item in result['blockers']))
    def test_settings_word_and_polite_continuations_keep_explicit_opt_in(self):
        event={'session_id':'release-settings','turn_id':'1','cwd':str(self.root)}
        for text in ('使用 frontend-workflow 为我制作设置页面','$frontend-workflow 制作账户设置页面'):
            self.assertEqual(p.workflow_request(text),'enable')
            self.assertIn('hookSpecificOutput',p.hook({**event,'hook_event_name':'UserPromptSubmit','prompt':text}))
            self.assertIn('hookSpecificOutput',p.hook({**event,'hook_event_name':'UserPromptSubmit','prompt':'好的，继续完成同一个登录页面。'}))
            self.assertEqual(p.hook({**event,'hook_event_name':'Stop','last_assistant_message':'最终状态：PASS'}).get('decision'),'block')
    def test_real_daisyui_css_plugin_syntax_qualifies_as_use(self):
        task=plan(self.root,level='L3');(self.root/'docs.md').write_text('Controlled static syntax evidence, not a real Context7 call.')
        (self.root/'app.css').write_text('@plugin "daisyui";',encoding='utf-8')
        task['component_libraries']={'decision':'used','reason':'Listed CSS UI library fixture','items':[{'name':'DaisyUI','role':'primary_ui','version':'5.7.50','docs_provider':'official','context7_limitation':'Isolated syntax fixture only','docs_evidence':'docs.md','usage':['app.css'],'imports':['daisyui'],'customization':'Explicit custom design tokens','render_checks':[{'component':'Button','implementation':'app.css','selector':'button'}]}]}
        self.assertEqual(p.component_findings(self.root,task,required=True),[])
    def test_command_cannot_test_one_revision_and_seal_another(self):
        plan(self.root,visual=False)
        with self.assertRaisesRegex(ValueError,'changed during'):
            p.run_check(self.root,'project-check',[sys.executable,'-c',"from pathlib import Path;Path('index.html').write_text('<p>changed</p>')"])
        self.assertNotEqual(p.verify(self.root)['status'],'PASS')
    def test_preflight_before_ui_and_plan_change_invalidates_it(self):
        task=plan(self.root)
        self.assertTrue(p.preflight.receipt_gaps(p,self.root,task))
        self.assertEqual(p.preflight_check(self.root,task,issue=True)['status'],'PASS')
        self.assertEqual(p.preflight.receipt_gaps(p,self.root,task),[])
        task['design_plan']['typography']='Another direction'
        self.assertTrue(p.preflight.receipt_gaps(p,self.root,task))
    def test_full_ui_cannot_scope_out_all_original_rules(self):
        task=plan(self.root,level='L3')
        result=p.preflight_check(self.root,task)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(any('cannot exclude' in item for item in result['blockers']))
        self.assertTrue(any('primary UI' in item for item in result['blockers']))
        self.assertTrue(any('non-background' in item for item in result['blockers']))
    def test_missing_design_document_blocks_preflight(self):
        task=plan(self.root)
        (self.root/'design.md').unlink()
        self.assertEqual(p.preflight_check(self.root,task)['status'],'BLOCKED')
    def test_design_document_change_invalidates_preflight(self):
        task=plan(self.root)
        self.assertEqual(p.preflight_check(self.root,task,issue=True)['status'],'PASS')
        (self.root/'design.md').write_text('Changed current design')
        self.assertTrue(p.preflight.receipt_gaps(p,self.root,task))
    def test_planning_document_content_is_bound(self):
        task=plan(self.root)
        (self.root/'docs.md').write_text('Original planning evidence')
        task['component_libraries']['stylekit_priority']={'decision':'fallback','reason':'Fixture','search_evidence':'docs.md'}
        self.assertEqual(p.preflight_check(self.root,task,issue=True)['status'],'PASS')
        (self.root/'docs.md').write_text('Changed planning evidence')
        self.assertTrue(p.preflight.receipt_gaps(p,self.root,task))
    def test_static_plan_cannot_satisfy_full_page_dynamics(self):
        task=plan(self.root,level='L3')
        task['design_plan']['dynamic_components']=[]
        gaps=p.preflight.design_gaps(p,self.root,task)
        self.assertTrue(any('each declared page' in item for item in gaps))
        task['design_plan']['dynamic_components']=[dynamic_component()]
        task['design_plan']['dynamic_components'][0]['verification']['steps']=[{'action':'expect_visible','selector':'#target'}]
        self.assertTrue(any('real trigger' in item for item in p.preflight.design_gaps(p,self.root,task)))
    def test_complete_l3_plan_can_pass_planning_without_certifying_ui(self):
        task=plan(self.root,level='L3')
        for item in task['rule_application']:item.update(applicability='applicable',reason='Synthetic planning coverage; no product/tool-use certification.')
        for field in ('selection_evidence','style_summary','asset_plan','implementation_checklist'):
            task[field]=field+'.md';(self.root/task[field]).write_text('Synthetic planning record only; no actual user choice or external tool call asserted.')
        task['design_plan'].update(selected_style='A',assets=[{'role':'object_cutout','purpose':'Fixture scenario','placement':'main'}])
        task['space_effects']={key:{'decision':'omitted','reason':'Planning fixture has no spatial effect'} for key in ('shader','model')}
        (self.root/'docs.md').write_text('Synthetic library planning evidence; not a real documentation query.')
        task['component_libraries']={'decision':'used','reason':'Planning fixture','items':[{'name':'Mantine','role':'primary_ui','version':'fixture-revision-1','docs_provider':'context7','docs_evidence':'docs.md','usage':['future.tsx'],'imports':['@mantine/core'],'customization':'Specific planned form tokens','render_checks':[{'component':'TextInput','implementation':'future.tsx','selector':'#form'}]}]}
        task['project_requirements']=[{'id':'scenario','source':'docs.md','expected':'Fixture scenario','implementation':['future.tsx'],'verification':{'mode':'visual_review'}}]
        task['component_libraries']['stylekit_priority']={'decision':'fallback','reason':'Synthetic engine test uses Mantine fixture','search_evidence':'docs.md'}
        task['checklist_plan']='checklist-plan.json'
        entries=[{'id':'rule:'+item['id'],'decision':'Plan the declared scope for source clause '+item['id'],'implementation':['future.tsx'],'condition':'Inspect the specific original requirement '+item['id'],'verification':{'check_id':'visual','criterion':'rule:'+item['id']}} for item in task['rule_application']]
        entries.append({'id':'project:scenario','decision':'Show the scenario in the fixture','implementation':['future.tsx'],'condition':'Fixture presents the requested scenario','verification':{'check_id':'visual','criterion':'project:scenario'}})
        p.save(self.root/'checklist-plan.json',{'schema':1,'entries':entries})
        (self.root/task['implementation_checklist']).unlink()
        result=p.preflight_check(self.root,task,issue=True)
        self.assertEqual(result['status'],'PASS',result)
        self.assertNotEqual(p.verify(self.root,task)['status'],'PASS')
    def test_stop_rejects_conflicting_declarations_and_completion_claims(self):
        event={'session_id':'release-conflict','turn_id':'1','cwd':str(self.root)}
        p.hook({**event,'hook_event_name':'UserPromptSubmit','prompt':'使用 frontend-workflow 制作页面'})
        for text in ('最终状态：BLOCKED\n最终状态：PASS','全部通过。最终状态：BLOCKED'):
            result=p.hook({**event,'hook_event_name':'Stop','last_assistant_message':text})
            self.assertEqual(result.get('decision'),'block',result)
    def test_malformed_task_stop_fails_closed_but_honest_blocker_can_end(self):
        event={'session_id':'release-malformed','turn_id':'1','cwd':str(self.root)}
        p.hook({**event,'hook_event_name':'UserPromptSubmit','prompt':'使用 frontend-workflow 制作页面'})
        (self.root/p.TASK_PATH).parent.mkdir(parents=True,exist_ok=True);(self.root/p.TASK_PATH).write_text('{',encoding='utf-8')
        self.assertEqual(p.hook({**event,'hook_event_name':'Stop','last_assistant_message':'最终状态：PASS'}).get('decision'),'block')
        self.assertNotIn('decision',p.hook({**event,'hook_event_name':'Stop','last_assistant_message':'清单损坏，无法验证。最终状态：BLOCKED'}))

class BrowserReleaseTests(unittest.TestCase):
    def test_real_dynamic_trigger_result_is_recorded(self):
        with tempfile.TemporaryDirectory(prefix='fp-dynamic-') as folder:
            root=Path(folder)
            (root/'index.html').write_text('<meta charset="utf-8"><style>html{font-family:Arial,SimSun,serif}body,input,button,textarea,select{font-family:inherit}body{min-height:100vh;background:linear-gradient(20deg,#f4f1e7,#ede8dc)}</style><button id="target" onclick="document.querySelector(\'#result\').textContent=\'完成\'">开始</button><output id="result">准备</output>',encoding='utf-8')
            task=plan(root)
            task['design_plan']['dynamic_components']=[dynamic_component()]
            p.save(root/p.TASK_PATH,task)
            self.assertEqual(p.preflight_check(root,task,issue=True)['status'],'PASS')
            steps=dynamic_component()['verification']['steps']
            p.save(root/'spec.json',{'cases':[{'page':'main','width':390,'state':'default','url':(root/'index.html').as_uri(),'steps':steps}]})
            record=p.run_browser(root,'spec.json')
            self.assertEqual(record['status'],'PASS',p.browser_findings(root,p.load(root/p.TASK_PATH),record['captures']))
            self.assertEqual(p.preflight.dynamic_execution_gaps(task,record),[])
            record['assertions'][0].pop('steps')
            self.assertTrue(p.preflight.dynamic_execution_gaps(task,record))
    def test_real_rendered_prohibitions_and_positive_controls(self):
        results=[]
        cases=[
            ('modern-css','<p id="target" style="color:oklch(60% .22 290)">示例</p>','forbidden color'),
            ('short-hex','<p id="target" style="border:2px solid #63cf">示例</p>','forbidden color'),
            ('pseudo-copy','<style>#target::after{content:"用户协议与隐私政策"}</style><p id="target">我已阅读并同意</p>',None),
            ('split-copy','<div id="target"><span>我已阅读并同意</span><a>用户协议</a>与<a>隐私政策</a></div>',None),
            ('output-copy','<output id="target">说明登录用途与下一步操作，按表达需要保留完整文字。</output>',None),
            ('pseudo-icon','<style>#target::before{content:"🚀"}</style><button id="target">开始</button>','Emoji'),
            ('even-columns','<nav id="target" style="display:grid;grid-template-columns:1fr 1fr"><a>首页</a><a>记录</a></nav>','equal-width'),
            ('linear-transition','<p id="target" style="transition:opacity 1s cubic-bezier(0,0,1,1)">示例</p>','easing'),
            ('linear-waapi','<p id="target">示例</p><script>target.animate([{opacity:1},{opacity:.5}],{duration:10000,iterations:Infinity})</script>','easing'),
            ('custom-motion','<style>@keyframes pulse{to{opacity:.5}}#target{animation:pulse 2s cubic-bezier(.2,.8,.3,1) infinite}</style><p id="target">示例</p>',None),
            ('asymmetric-layout','<nav id="target" style="display:grid;grid-template-columns:2fr 1fr"><a>首页</a><a>记录</a></nav>',None),
            ('short-copy','<p id="target">先练十分钟。</p>',None),
        ]
        with tempfile.TemporaryDirectory(prefix='fp-browser-') as folder:
            root=Path(folder)
            for label,html,expected in cases:
                (root/'index.html').write_text('<!doctype html><meta charset="utf-8"><style>html{font-family:Arial,SimSun,serif}body,input,button,textarea,select{font-family:inherit}body{color:#254c40;background:linear-gradient(20deg,#f4f1e7,#ede8dc);min-height:100vh}a{color:inherit}</style><body><main>'+html+'</main></body>',encoding='utf-8')
                task=plan(root);self.assertEqual(p.preflight_check(root,task,issue=True)['status'],'PASS')
                p.save(root/'spec.json',{'cases':[{'page':'main','width':390,'state':'default','url':(root/'index.html').as_uri(),'steps':[{'action':'expect_visible','selector':'#target'}]}]})
                record=p.run_browser(root,'spec.json');task=p.load(root/p.TASK_PATH);data=p.browser_findings(root,task,record['captures'])
                if expected:
                    self.assertEqual(record['status'],'FAIL',(label,data));self.assertTrue(any(expected in finding for finding in data['findings']),(label,data))
                else:self.assertEqual(record['status'],'PASS',(label,data))
                results.append({'case':label,'expected':expected or 'mechanical checks pass','actual':record['status'],'receipt':record.get('execution_receipt')})
            output=Path(__file__).parent/'last-browser-release-results.json';p.save(output,{'status':'PASS','scope':'Controlled fixed-browser regressions only','cases':results})
    def test_old_served_document_and_script_cannot_bind_to_current_sources(self):
        with tempfile.TemporaryDirectory(prefix='fp-deploy-') as folder:
            root=Path(folder);old=root/'old';old.mkdir()
            (root/'index.html').write_text('<p id="target">当前</p>',encoding='utf-8');(old/'index.html').write_text('<p id="target">旧版</p>',encoding='utf-8')
            plan(root)
            spec={'cases':[{'page':'main','width':390,'state':'default','url':(old/'index.html').as_uri(),'steps':[{'action':'expect_visible','selector':'#target'}]}]}
            p.save(root/'spec.json',spec);result=p.run_browser(root,'spec.json')
            self.assertEqual(result['status'],'FAIL');self.assertIn('Served HTML',result['runner_error'])
            html='<p id="target">当前</p><script src="app.js"></script>'
            for path in (root/'index.html',old/'index.html'):path.write_text(html,encoding='utf-8')
            (root/'app.js').write_text('document.body.dataset.version="current";');(old/'app.js').write_text('document.body.dataset.version="old";')
            task=plan(root);task['files'].append('app.js');p.save(root/p.TASK_PATH,task)
            result=p.run_browser(root,'spec.json');self.assertEqual(result['status'],'FAIL');self.assertIn('Served runtime',result['runner_error'])
    def test_real_build_output_and_source_receipt_can_bind_compiled_ui(self):
        with tempfile.TemporaryDirectory(prefix='fp-build-') as folder:
            root=Path(folder);(root/'index.html').write_text('<p>Source fixture</p>',encoding='utf-8')
            task=plan(root);task['deployment']={'mode':'build','check_id':'build'}
            task['checks'].append({'id':'build','type':'command','required':True,'outputs':['dist/index.html']})
            p.save(root/p.TASK_PATH,task)
            html='<style>html{font-family:Arial,SimSun,serif}body,input,button,textarea,select{font-family:inherit}body{background:linear-gradient(20deg,#f4f1e7,#ede8dc)}</style><p id="target">示例</p>'
            program="from pathlib import Path;Path('dist').mkdir(exist_ok=True);Path('dist/index.html').write_text("+repr(html)+",encoding='utf-8')"
            p.run_check(root,'build',[sys.executable,'-c',program])
            p.save(root/'spec.json',{'cases':[{'page':'main','width':390,'state':'default','url':(root/'dist/index.html').as_uri(),'steps':[{'action':'expect_visible','selector':'#target'}]}]})
            self.assertEqual(p.run_browser(root,'spec.json')['status'],'PASS')
            (root/'dist/index.html').write_text('<p>tampered</p>')
            with self.assertRaisesRegex(ValueError,'Build outputs changed'):p.run_browser(root,'spec.json')

if __name__=='__main__':unittest.main(verbosity=2)
