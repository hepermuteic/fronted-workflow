"""Behavioral regression tests for task scope and delivery guard; no model calls."""
import base64
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import struct
import zlib
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('policy',Path(__file__).resolve().parents[1] / 'verify.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a8WQAAAAASUVORK5CYII=')

def png(color):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00'+bytes(color)))+chunk(b'IEND',b'')

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.center_patch=patch.object(p,'CENTER',self.root/'runner-center');self.center_patch.start()
        (self.root / 'app.css').write_text('body {color:#183d32; background:#eff3e8;}',encoding='utf-8')
    def tearDown(self):
        self.center_patch.stop()
        self.temp.cleanup()
    def task(self,level='L1',**kwargs):
        task=p.init_task(self.root,level,'Scoped fixture task',['app.css'],**kwargs)
        # Controlled verifier tests only. No business UI or original design is certified.
        for application in task['rule_application']:
            application.update(applicability='out_of_scope',reason='Synthetic verifier fixture; original aesthetic/workflow execution is not being certified.')
        p.save(self.root/p.TASK_PATH,task)
        return task
    def visual_fixture(self):
        task = self.task('L2',pages=['home'],widths=[390],states=['default'])
        (self.root / 'shot.png').write_bytes(PNG)
        snapshot = {'schema':'frontend-policy/browser-v1','url':'http://localhost/fixture','page':'home','state':'default',
                    'screenshot':'shot.png','viewport':{'width':390,'height':844},'source_hashes':p.hashes(self.root,task),
                    'html':'<body><h1>今天，练一点。</h1></body>','styles':[{'color':'rgb(24, 61, 50)'}],
                    'resources':[],'images':[],'animations':[],'horizontal_overflow':False}
        p.save(self.root / 'capture.json',snapshot)
        p.record(self.root,task,'browser',{'captures':['capture.json'],'status':'PASS'})
        observations = [{'criterion':criterion,'location':'h1 in home viewport',
                         'observed':'Synthetic fixture observation for '+criterion+'; not product certification.', 'status':'PASS','evidence':['shot.png']}
                        for criterion in task['review_criteria']]
        p.record(self.root,task,'visual',{'observations':observations,'status':'REVIEW_ATTESTATION'})
        return task,snapshot,observations
    def test_l1_does_not_require_full_design_or_assets(self):
        task=self.task()
        self.assertEqual([check['type'] for check in task['checks']],['source'])
        self.assertEqual(p.verify(self.root)['status'],'PASS')
    def test_missing_source_scope_is_blocked(self):
        task=self.task();task['files']=[]
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
    def test_unmodified_preexisting_violation_is_outside_local_diff(self):
        (self.root/'app.css').write_text('body{color:#6366F1;}',encoding='utf-8')
        self.task()
        self.assertEqual(p.verify(self.root)['status'],'PASS')
    def test_all_profile_aliases_apply_identical_hard_rules(self):
        for profile in ('strict','project','expressive'):
            rules=p.active_rules({'profile':profile})
            self.assertIsNone(rules['copy_limit'])
            self.assertTrue(rules['default_palette'])
            self.assertIn('linear',rules['forbidden_easing'])
            self.assertIn('#6366f1',rules['forbidden_hex'])
    def test_project_label_does_not_exempt_changed_forbidden_styles(self):
        self.task(profile='project')
        (self.root/'app.css').write_text('body{color:rgb(100,50,200);transition:opacity 1s ease-in-out;} .text-zinc-500{}')
        result=p.verify(self.root)
        self.assertEqual(result['status'],'FAIL')
        for expected in ('purple/indigo','easing','palette'):
            self.assertTrue(any(expected in item for item in result['failures']),result)
    def test_hue_scan_catches_rgb_hsl_and_hex_not_neutrals(self):
        for color in ('#6633cc','rgb(100,50,200)','hsl(260,60%,40%)'):
            self.assertTrue(p.forbidden_hue(color),color)
        for color in ('#183d32','#eeeeee','rgba(0,0,0,0)','hsl(260,0%,40%)'):
            self.assertFalse(p.forbidden_hue(color),color)
    def test_original_file_is_part_of_policy_hash(self):
        copied=self.root/'original.md';copied.write_bytes(p.original_rules().read_bytes())
        with patch.object(p,'original_rules',return_value=copied):
            before=p.policy_hash();copied.write_text(copied.read_text(encoding='utf-8')+'\n',encoding='utf-8')
            self.assertNotEqual(before,p.policy_hash())
            copied.unlink()
            with self.assertRaises(ValueError):p.policy_hash()
    def test_new_unmapped_clause_blocks_catalog(self):
        copied=self.root/'original.md';copied.write_text(p.original_rules().read_text(encoding='utf-8')+'\n- New mandatory test clause.\n',encoding='utf-8')
        with patch.object(p,'original_rules',return_value=copied):
            with self.assertRaisesRegex(ValueError,'no enforcement route'):p.validate_rule_binding()
    def test_unresolved_rule_applicability_blocks(self):
        task=self.task();task['rule_application'][0]['applicability']='pending'
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
        task['rule_application']=[]
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
    def test_original_snapshot_mismatch_blocks(self):
        task=self.task();task['original_rules_sha256']='old'
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
    def test_mandatory_clause_cannot_be_marked_conditional(self):
        task=self.task();task['rule_application'][0].update(applicability='conditional',reason='Attempt to weaken a mandatory clause')
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
    def test_applicable_visual_rule_cannot_pass_as_source_only_l1(self):
        task=self.task()
        route=next(x for x in p.load(p.SKILL/'references/original-rule-map.json')['rules'] if x['method']=='visual_review')
        next(x for x in task['rule_application'] if x['id']==route['id']).update(applicability='applicable',reason='Affected visual composition')
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
    def test_necessary_agreement_has_no_fixed_length_limit(self):
        (self.root/'agreement.html').write_text('<p>短句。</p>',encoding='utf-8')
        task=self.task();task['files'].append('agreement.html')
        (self.root/'agreement.html').write_text('<p>我已阅读并同意<a>《用户协议》</a>与<a>《隐私政策》</a></p>',encoding='utf-8')
        self.assertEqual(p.verify(self.root,task)['status'],'PASS')
    def test_l3_aliases_all_require_assets_and_style_records(self):
        for profile in ('strict','project','expressive'):
            task=p.init_task(self.root,'L3','New UI fixture',['app.css'],profile=profile,replace=True)
            self.assertIn('assets',[x['type'] for x in task['checks']])
            result=p.verify(self.root,task)
            self.assertEqual(result['status'],'BLOCKED')
            for field in ('selection_evidence','style_summary','asset_plan','implementation_checklist'):
                self.assertTrue(any(field in item for item in result['blockers']))
    def test_rule_application_and_selection_changes_invalidate_receipt(self):
        task=self.task('L2',visual=False);task['visual_reason']='Nonvisual runner fixture'
        (self.root/'choice.md').write_text('Controlled fixture; no actual design selection asserted.')
        task['selection_evidence']='choice.md';p.save(self.root/p.TASK_PATH,task)
        p.run_check(self.root,'project-check',[sys.executable,'-c','print("real execution")'])
        self.record_final_review()
        self.assertEqual(p.verify(self.root)['status'],'PASS')
        task=p.load(self.root/p.TASK_PATH);task['rule_application'][0]['reason']='Changed declared scope after execution'
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
        (self.root/'choice.md').write_text('Changed choice artifact')
        self.assertEqual(p.verify(self.root)['status'],'BLOCKED')
    def test_l1_expressive_checks_new_diff(self):
        (self.root/'app.css').write_text('body{color:#6366F1;}',encoding='utf-8')
        self.task(profile='expressive')
        self.assertEqual(p.verify(self.root)['status'],'PASS')
        (self.root/'app.css').write_text('body{color:#6366F1;}\np{color:#8B5CF6;}',encoding='utf-8')
        self.assertEqual(p.verify(self.root)['status'],'FAIL')
    def test_framework_and_package_manager_discovery(self):
        for dependency,expected in [('react','React'),('vue','Vue'),('next','Next/React'),('svelte','Svelte')]:
            p.save(self.root/'package.json',{'dependencies':{dependency:'1'},'scripts':{'dev':'actual-dev','build':'actual-build'}})
            (self.root/'pnpm-lock.yaml').write_text('lockfileVersion: 9')
            data=p.discover(self.root)
            self.assertEqual(data['framework'],expected)
            self.assertEqual(data['package_manager'],'pnpm')
            self.assertEqual(data['start_candidates'],['dev'])
            self.assertEqual(data['check_candidates'],['build'])
    def test_l2_visual_missing_browser_evidence_is_blocked(self):
        self.task('L2')
        self.assertEqual(p.verify(self.root)['status'],'BLOCKED')
    def test_command_exit_code_and_real_log(self):
        task=self.task('L2',visual=False)
        task['visual_reason']='Nonvisual utility logic only';p.save(self.root/p.TASK_PATH,task)
        result=p.run_check(self.root,'project-check',[sys.executable,'-c','print("actual process")'])
        self.assertEqual(result['exit_code'],0)
        self.assertIn('actual process',p.local(self.root,result['log']).read_text())
        self.record_final_review()
        self.assertEqual(p.verify(self.root)['status'],'PASS')

    def record_final_review(self):
        from types import SimpleNamespace
        task=p.load(self.root/p.TASK_PATH)
        evidence=list(task['evidence'].values())
        reflection={'schema':1,'rounds':[{'observations':[
            {'area':'rules','observed':'The current diagnostic checks and declared source scope are covered by their recorded process results','evidence':evidence},
            {'area':'quality','observed':'The retained diagnostic inputs and process output match the current fixture fingerprint','evidence':evidence},
            {'area':'scope','observed':'The requested diagnostic process and evidence checks have no remaining identified fixture issue','evidence':evidence}], 'improvements':[]}],
            'remaining_improvements':[],'completion_reason':'The current diagnostic process and evidence binding are checked within their declared fixture scope'}
        result=p.delivery_review.record(SimpleNamespace(**vars(p)),self.root,task,reflection)
        self.assertEqual(result['status'],'READY',result)
    def test_failed_command_is_fail_not_blocked_or_pass(self):
        task=self.task('L2',visual=False);task['visual_reason']='Nonvisual utility check';p.save(self.root/p.TASK_PATH,task)
        p.run_check(self.root,'project-check',[sys.executable,'-c','raise SystemExit(7)'])
        self.assertEqual(p.verify(self.root)['status'],'FAIL')
    def test_changed_log_is_blocked(self):
        task=self.task('L2',visual=False);task['visual_reason']='Nonvisual utility check';p.save(self.root/p.TASK_PATH,task)
        rec=p.run_check(self.root,'project-check',[sys.executable,'-c','print("verified")'])
        p.local(self.root,rec['log']).write_text('fabricated log')
        self.assertEqual(p.verify(self.root)['status'],'BLOCKED')
    def test_command_error_does_not_reuse_old_pass(self):
        task=self.task('L2',visual=False);task['visual_reason']='Nonvisual utility check';p.save(self.root/p.TASK_PATH,task)
        p.run_check(self.root,'project-check',[sys.executable,'-c','print("ok")'])
        with self.assertRaises(OSError):p.run_check(self.root,'project-check',['nonexistent-frontend-test-binary'])
        self.assertEqual(p.verify(self.root)['status'],'BLOCKED')
    def test_changed_sources_invalidate_evidence(self):
        self.visual_fixture()
        (self.root/'app.css').write_text('body{color:#172b21;}')
        self.assertEqual(p.verify(self.root)['status'],'BLOCKED')
    def test_current_visual_evidence_has_scoped_pass(self):
        self.visual_fixture();result=p.verify(self.root)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertIn('visual',result['review_attestations'])
        self.assertEqual(result['visual_acceptance'],'BLOCKED')
    def test_missing_view_is_blocked(self):
        task,_,_=self.visual_fixture()
        task['scope'].append({'page':'home','width':430,'state':'error'})
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
    def test_known_overflow_is_fail(self):
        task,snapshot,_=self.visual_fixture();snapshot['horizontal_overflow']=True
        p.save(self.root/'capture.json',snapshot)
        p.record(self.root,task,'browser',{'captures':['capture.json'],'status':'FAIL'})
        self.assertTrue(p.browser_findings(self.root,task,['capture.json'])['findings'])
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
    def test_unmapped_bundle_is_blocked(self):
        task,snapshot,_=self.visual_fixture();snapshot['resources']=[{'url':'http://localhost/bundle.js'}]
        p.save(self.root/'capture.json',snapshot)
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
    def test_visual_failure_overrides_missing_other_checks(self):
        task,_,observations=self.visual_fixture();observations[0]['status']='FAIL'
        p.record(self.root,task,'visual',{'observations':observations})
        self.assertEqual(p.verify(self.root)['status'],'FAIL')
    def test_generic_observation_is_blocked(self):
        task,_,observations=self.visual_fixture();observations[0]['observed']='looks good'
        p.record(self.root,task,'visual',{'observations':observations})
        self.assertEqual(p.verify(self.root)['status'],'BLOCKED')
    def test_source_file_cannot_replace_visual_screenshot(self):
        task,_,observations=self.visual_fixture();observations[0]['evidence']=['app.css']
        p.record(self.root,task,'visual',{'observations':observations})
        self.assertEqual(p.verify(self.root)['status'],'BLOCKED')
    def test_old_policy_and_wrong_task_records_are_blocked(self):
        task,_,_=self.visual_fixture();task['policy_hash']='old'
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
        task=p.load(self.root/p.TASK_PATH);rec=p.load(p.local(self.root,task['evidence']['browser']));rec['task_id']='another'
        p.save(p.local(self.root,task['evidence']['browser']),rec)
        self.assertEqual(p.verify(self.root)['status'],'BLOCKED')
    def test_essential_checks_cannot_be_removed(self):
        task=self.task('L2');task['checks']=[]
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
    def test_bad_paths_rejected(self):
        with self.assertRaises(ValueError):p.local(self.root,'../outside')
    def test_invalid_phase_does_not_pass(self):
        task=self.task();task['phase']='maintenance'
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
    def test_malformed_task_object_returns_blocked(self):
        self.assertEqual(p.verify(self.root,[])['status'],'BLOCKED')
    def test_changed_screenshot_cannot_reuse_review(self):
        self.visual_fixture()
        (self.root/'shot.png').write_bytes(PNG+b'changed')
        self.assertEqual(p.verify(self.root)['status'],'BLOCKED')
    def test_reference_stage_needs_no_gallery_or_formal_review(self):
        task=self.task('L3',phase='reference',profile='expressive')
        self.assertEqual([x['type'] for x in task['checks']],['references'])
        self.assertEqual(task['review_criteria'],[])
        for application in task['rule_application']:
            application.update(applicability='pending',reason='')
        task['references']=[]
        for index,key in enumerate('ABCD'):
            (self.root/(key+'.png')).write_bytes(png((index*40,110,30)))
            task['references'].append({'id':key,'path':key+'.png','style':key,'palette':key})
        p.save(self.root/p.TASK_PATH,task)
        result=p.verify(self.root)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['automated_status'],'PASS')
        self.assertEqual(result['phase'],'reference')
        self.assertIn('await user selection',' '.join(result['blockers']))
    def test_reference_stage_rejects_duplicate_image_artifacts(self):
        task=self.task('L3',phase='reference')
        task['references']=[]
        for key in 'ABCD':
            (self.root/(key+'.png')).write_bytes(PNG)
            task['references'].append({'id':key,'path':key+'.png'})
        self.assertEqual(p.verify(self.root,task)['automated_status'],'BLOCKED')
    def test_reference_handoff_needs_no_task_or_delivery_verdict(self):
        event={'cwd':str(self.root),'session_id':'style-only','turn_id':'one'}
        p.hook({**event,'hook_event_name':'UserPromptSubmit','prompt':'使用 frontend-workflow 制作面试首页'})
        result=p.hook({**event,'hook_event_name':'Stop','last_assistant_message':'四张风格参考已生成。请选择 A、B、C、D。'})
        self.assertNotEqual(result.get('decision'),'block')
        self.assertFalse((self.root/p.TASK_PATH).exists())
    def test_reference_handoff_does_not_hide_ui_source_edits(self):
        event={'cwd':str(self.root),'session_id':'style-with-ui','turn_id':'one'}
        p.hook({**event,'hook_event_name':'UserPromptSubmit','prompt':'使用 frontend-workflow 制作面试首页'})
        p.hook({**event,'hook_event_name':'PostToolUse','tool_input':{'file_path':'app.css'}})
        result=p.hook({**event,'hook_event_name':'Stop','last_assistant_message':'四张风格参考已生成。请选择 A、B、C、D。'})
        self.assertEqual(result.get('decision'),'block')
    def test_unknown_profile_is_blocked(self):
        task=self.task();task['profile']='bypass'
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
    def test_l3_expressive_requires_assets_instead_of_forcing_them_on_l1(self):
        task=self.task('L3',profile='expressive')
        self.assertIn('assets',[check['type'] for check in task['checks']])
        task['checks']=[check for check in task['checks'] if check['type']!='assets']
        self.assertEqual(p.verify(self.root,task)['status'],'BLOCKED')
    def test_new_task_archives_previous_plan(self):
        previous=self.task()
        newer=p.init_task(self.root,'L1','New scope',['app.css'],replace=True)
        self.assertNotEqual(previous['task_id'],newer['task_id'])
        self.assertTrue((self.root/'work/frontend-policy/history'/f'{previous["task_id"]}.json').is_file())
    def test_copy_joins_links_br_and_checkbox_buttons(self):
        examples=['<p>项目没有那么大，<br><span>也能讲出自己的贡献。</span></p>',
                  '<div><input type="checkbox" id="agree"><div><label for="agree">我已阅读并同意</label><br><button>《用户协议》</button>与<button>《隐私政策》</button></div></div>',
                  '<p>我已阅读并同意<a>《用户协议》</a>与<a>《隐私政策》</a></p>']
        for html in examples:self.assertTrue(any('16>15' in finding for finding in p.text_findings(html,15)))
    def test_independent_card_heading_and_description_not_joined(self):
        html='<button><h3>一分钟自我介绍</h3><p>通用面试，周五练过。</p><span>已完成</span></button>'
        self.assertEqual(p.text_findings(html,15),[])
    def test_sentence_boundary_and_hidden_text(self):
        self.assertEqual(p.text_findings('<p>我已阅读并同意。<a>《用户协议》</a>与<a>《隐私政策》</a></p>',15),[])
        self.assertEqual(p.text_findings('<p>短句。<span hidden>这里有一段本来不应显示的非常长的句子。</span></p>',15),[])
    def test_real_maintenance_prompts_are_not_ui_builds(self):
        for prompt in ('重构全局前端规范中心及 frontend-workflow Skill','设置全局 Hooks 验收规范','请审计 frontend-policy 是否加载'):
            self.assertEqual(p.classify(prompt),'maintenance')
        self.assertEqual(p.classify('制作一个Vue后台页面'),'frontend')
        self.assertEqual(p.classify('修复React组件的CSS样式'),'frontend')
        self.assertEqual(p.classify('修复数据库连接'),'other')
    def event(self,name,**kwargs):
        event=dict(session_id='fixture',turn_id='test',cwd=str(self.root),hook_event_name=name)
        event.update(kwargs)
        return event
    def test_sessionstart_and_compaction_remind_without_model(self):
        with patch.object(p,'CENTER',self.root/'center'):
            for source in ('startup','compact'):
                self.assertEqual(p.hook(self.event('SessionStart',source=source)),{})
            p.hook(self.event('UserPromptSubmit',prompt='使用 frontend-workflow 制作首页'))
            for source in ('resume','compact'):
                result=p.hook(self.event('SessionStart',source=source))
                self.assertIn('SKILL.md',result['hookSpecificOutput']['additionalContext'])
    def test_maintenance_does_not_activate_stop(self):
        with patch.object(p,'CENTER',self.root/'center'):
            self.assertEqual(p.hook(self.event('UserPromptSubmit',prompt='重构全局前端规范中心')), {})
            self.assertEqual(p.hook(self.event('Stop',last_assistant_message='Done')), {})
    def test_read_only_rule_audit_does_not_require_ui_task(self):
        with patch.object(p,'CENTER',self.root/'center'):
            p.hook(self.event('UserPromptSubmit',prompt='使用 frontend-workflow 制作一个React页面'))
            self.assertEqual(p.classify('是否严格按照我一开始的规则制作和检验'),'audit')
            self.assertEqual(p.hook(self.event('UserPromptSubmit',prompt='是否严格按照我一开始的规则制作和检验')), {})
            self.assertEqual(p.hook(self.event('Stop',last_assistant_message='规则不一致')), {})
    def test_audit_and_repair_still_activates_frontend(self):
        self.assertEqual(p.classify('请检查页面并修复问题'),'frontend')
        self.assertEqual(p.classify('帮我修改React组件'),'frontend')
    def test_stop_blocks_unsupported_pass_and_limits_continuations(self):
        with patch.object(p,'CENTER',self.root/'center'):
            p.hook(self.event('UserPromptSubmit',prompt='使用 frontend-workflow 制作一个React页面'))
            for _ in range(2):self.assertEqual(p.hook(self.event('Stop',last_assistant_message='最终状态：PASS'))['decision'],'block')
            self.assertIs(p.hook(self.event('Stop',last_assistant_message='最终状态：PASS'))['continue'],False)
            self.assertEqual(p.load(self.root/p.RESULT_PATH)['status'],'BLOCKED')
    def test_stop_allows_honest_blocked_declaration(self):
        with patch.object(p,'CENTER',self.root/'center'):
            p.hook(self.event('UserPromptSubmit',prompt='使用 frontend-workflow 制作一个React页面'))
            result=p.hook(self.event('Stop',last_assistant_message='工具不可用。最终状态：BLOCKED'))
            self.assertNotIn('decision',result)
    def test_hook_never_executes_project_commands(self):
        with patch.object(p,'CENTER',self.root/'center'),patch.object(p.subprocess,'run',side_effect=AssertionError('Hook executed a command')):
            p.hook(self.event('UserPromptSubmit',prompt='使用 frontend-workflow 制作一个React页面'))
            p.hook(self.event('Stop',last_assistant_message='最终状态：PASS'))

    def test_forged_command_record_without_execution_is_blocked(self):
        task=self.task('L2',visual=False);task['visual_reason']='Nonvisual utility';p.save(self.root/p.TASK_PATH,task)
        (self.root/'fake.log').write_text('all tests passed')
        p.record(self.root,task,'project-check',{'status':'PASS','command':['fake'],'exit_code':0,'log':'fake.log','log_sha256':p.sha(self.root/'fake.log')})
        result=p.verify(self.root)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertTrue(any('receipt' in item for item in result['blockers']))

    def test_ordinary_frontend_prompt_and_ui_edit_do_not_opt_in(self):
        self.assertEqual(p.hook(self.event('UserPromptSubmit',prompt='制作一个React页面')), {})
        self.assertEqual(p.hook(self.event('PostToolUse',tool_input={'file_path':'app.css'})), {})
        self.assertEqual(p.hook(self.event('Stop',last_assistant_message='页面已修改')), {})
        self.assertFalse((self.root/p.RESULT_PATH).exists())

    def test_skill_mentions_questions_and_configuration_do_not_opt_in(self):
        for prompt in ('frontend-workflow 是什么','告诉我怎么使用 frontend-workflow','是否会使用 frontend-workflow','你会使用 frontend-workflow 吗','Can you use frontend-workflow?','将 frontend-workflow 改为仅在我明确要求时使用'):
            self.assertIsNone(p.workflow_request(prompt),prompt)
            self.assertEqual(p.hook(self.event('UserPromptSubmit',prompt=prompt)), {})
            self.assertEqual(p.hook(self.event('Stop',last_assistant_message='说明')), {})

    def test_explicit_dollar_invocation_and_direct_request_opt_in(self):
        for prompt in ('$frontend-workflow 制作首页','使用 frontend-workflow 完成此任务','Use frontend-workflow to build a page'):
            self.assertEqual(p.workflow_request(prompt),'enable')
            result=p.hook(self.event('UserPromptSubmit',prompt=prompt))
            self.assertIn('explicitly enabled',result['hookSpecificOutput']['additionalContext'])
            self.assertEqual(p.hook(self.event('Stop',last_assistant_message='最终状态：PASS'))['decision'],'block')

    def test_explicit_opt_out_cannot_be_reactivated_by_file_edits(self):
        p.hook(self.event('UserPromptSubmit',prompt='使用 frontend-workflow 制作页面'))
        for prompt in ('本次不要使用 frontend-workflow','不使用 frontend-workflow','我不想使用 frontend-workflow','不用这个skill了'):
            self.assertEqual(p.workflow_request(prompt),'disable')
            self.assertEqual(p.hook(self.event('UserPromptSubmit',prompt=prompt)), {})
            self.assertEqual(p.hook(self.event('PostToolUse',tool_input={'file_path':'app.css'})), {})
            self.assertEqual(p.hook(self.event('Stop',last_assistant_message='Done')), {})

    def test_selection_continues_explicit_task_but_new_task_defaults_off(self):
        p.hook(self.event('UserPromptSubmit',prompt='使用 frontend-workflow 制作页面'))
        self.assertIn('hookSpecificOutput',p.hook(self.event('UserPromptSubmit',prompt='选 C，继续制作')))
        self.assertEqual(p.hook(self.event('UserPromptSubmit',prompt='帮我制作另一个React网站')), {})
        self.assertEqual(p.hook(self.event('Stop',last_assistant_message='Done')), {})

    def test_old_auto_activation_state_does_not_opt_in(self):
        session=p.hashlib.sha256(b'fixture').hexdigest()[:24]
        p.save(p.CENTER/'state'/(session+'.json'),{'active':True,'turn':'test','root':str(self.root)})
        self.assertEqual(p.hook(self.event('SessionStart',source='resume')), {})
        self.assertEqual(p.hook(self.event('PostToolUse',tool_input={'file_path':'app.css'})), {})
        self.assertEqual(p.hook(self.event('Stop',last_assistant_message='Done')), {})

    def test_opt_in_does_not_cross_project_roots(self):
        p.hook(self.event('UserPromptSubmit',prompt='使用 frontend-workflow 制作页面'))
        other=self.root/'another-project';other.mkdir()
        self.assertEqual(p.hook(self.event('PostToolUse',cwd=str(other),tool_input={'file_path':'app.css'})), {})
        self.assertEqual(p.hook(self.event('Stop',cwd=str(other),last_assistant_message='Done')), {})

    def test_changed_contract_invalidates_real_execution(self):
        task=self.task('L2',visual=False);task['visual_reason']='Nonvisual utility';p.save(self.root/p.TASK_PATH,task)
        p.run_check(self.root,'project-check',[sys.executable,'-c','print("actual")'])
        task=p.load(self.root/p.TASK_PATH);task['scope']=[];p.save(self.root/p.TASK_PATH,task)
        self.assertEqual(p.verify(self.root)['status'],'BLOCKED')

    def test_component_selection_cannot_be_omitted_for_l3(self):
        task=self.task('L3')
        self.assertTrue(p.component_findings(self.root,task,required=True))
        task['component_libraries']={'decision':'none','reason':'Controlled static fixture, no suitable library is used.','items':[]}
        self.assertTrue(any('not an exemption' in x for x in p.component_findings(self.root,task,required=True)))

    def library_fixture(self):
        task=self.task()
        (self.root/'docs.md').write_text('Synthetic library documentation fixture, not a real Context7 result.')
        (self.root/'usage.ts').write_text("import { Fixture } from 'fixture-lib';")
        item={'name':'fixture-lib','version':'1.2.3','docs_provider':'context7','docs_evidence':'docs.md','usage':['usage.ts'],'imports':['fixture-lib'],'customization':'Fixture-only token/state details, not real product certification.'}
        task['component_libraries']={'decision':'used','reason':'Verifier record fixture','items':[item]}
        return task,item

    def test_component_docs_fallback_requires_real_limitation_record(self):
        task,item=self.library_fixture();item['docs_provider']='official'
        self.assertTrue(any('Context7 limitation' in x for x in p.component_findings(self.root,task)))
        item['context7_limitation']='Synthetic unavailable-tool scenario, not an executed query.'
        self.assertEqual(p.component_findings(self.root,task),[])

    def test_component_records_need_usage_customization_and_actual_version(self):
        task,item=self.library_fixture();item.update(usage=[],customization='',version='latest')
        gaps=p.component_findings(self.root,task)
        for expected in ('usage','customization','actual version'):
            self.assertTrue(any(expected in x for x in gaps),gaps)

    def test_declared_library_usage_cannot_point_to_unrelated_source(self):
        task,item=self.library_fixture();item['usage']=['app.css']
        self.assertTrue(any('import/use' in x for x in p.component_findings(self.root,task)))
        item['usage']=['usage.ts'];(self.root/'usage.ts').write_text("// import { Fixture } from 'fixture-lib';")
        self.assertTrue(any('import/use' in x for x in p.component_findings(self.root,task)))

    def primary_library_fixture(self):
        task,item=self.library_fixture();task.update(level='L2',visual=True)
        (self.root/'usage.ts').write_text("import { Button } from '@mantine/core';")
        check={'page':'home','width':390,'state':'default','selector':'#primary','component':'Button','implementation':'usage.ts'}
        item.update(name='Mantine',imports=['@mantine/core'],role='primary_ui',render_checks=[check])
        return task,item

    def test_dialog_helper_cannot_replace_given_ui_library(self):
        task,item=self.primary_library_fixture()
        (self.root/'usage.ts').write_text("import Dialog from 'a11y-dialog';")
        item.update(name='a11y-dialog',imports=['a11y-dialog'])
        gaps=p.component_findings(self.root,task,required=True)
        self.assertTrue(any('outside the user list' in x for x in gaps))
        item['role']='helper'
        self.assertTrue(any('No qualifying' in x for x in p.component_findings(self.root,task,required=True)))

    def test_fake_library_label_does_not_match_actual_helper_import(self):
        task,item=self.primary_library_fixture()
        (self.root/'usage.ts').write_text("import Dialog from 'a11y-dialog';")
        item['imports']=['a11y-dialog']
        self.assertTrue(any('identity' in x for x in p.component_findings(self.root,task,required=True)))

    def test_primary_library_requires_component_render_scope(self):
        task,item=self.primary_library_fixture()
        self.assertEqual(p.component_findings(self.root,task,required=True),[])
        self.assertTrue(p.component_render_findings(task,None,required=True))
        browser={'assertions':[{'page':'home','width':390,'state':'default','checks':[{'action':'expect_visible','selector':'#primary'}]}]}
        self.assertEqual(p.component_render_findings(task,browser,required=True),[])
        browser['assertions'][0]['width']=1280
        self.assertTrue(p.component_render_findings(task,browser,required=True))
        item['render_checks'][0]['implementation']='unrelated.ts'
        self.assertTrue(any('implementation' in x for x in p.component_render_findings(task,browser,required=True)))

    def test_registry_components_require_source_record(self):
        task,item=self.primary_library_fixture();item.update(name='Aceternity UI',distribution='vendored')
        self.assertTrue(p.component_findings(self.root,task,required=True))
        (self.root/'registry.md').write_text('Synthetic source-acquisition record; no real registry download claimed.')
        item['source_evidence']='registry.md'
        self.assertEqual(p.component_findings(self.root,task,required=True),[])
        before=p.hashes(self.root,task);(self.root/'registry.md').write_text('Changed record')
        self.assertNotEqual(before,p.hashes(self.root,task))

    def stylekit_resource_fixture(self):
        task,item=self.primary_library_fixture()
        (self.root/'usage.ts').write_text('export function StyleButton() { return "Synthetic component fixture"; }')
        p.save(self.root/'stylekit-source.json',{'source_url':'fixture://stylekit/editorial/button','asset_id':'editorial/button','files':[{'path':'usage.ts','sha256':p.sha(self.root/'usage.ts')}]})
        item.update(name='StyleKit',distribution='vendored',imports=[],docs_provider='official',source_evidence='stylekit-source.json')
        return task,item

    def test_stylekit_resource_can_supply_primary_ui(self):
        task,item=self.stylekit_resource_fixture()
        self.assertEqual(p.component_findings(self.root,task,required=True),[])

    def test_stylekit_resource_binding_rejects_changed_usage(self):
        task,item=self.stylekit_resource_fixture()
        (self.root/'usage.ts').write_text('Changed implementation')
        self.assertTrue(any('current vendored file hashes' in x for x in p.component_findings(self.root,task,required=True)))

    def test_stylekit_metadata_only_cannot_supply_primary_ui(self):
        task,item=self.stylekit_resource_fixture()
        p.save(self.root/'stylekit-source.json',{'source_url':'fixture://metadata','asset_id':'metadata'})
        self.assertTrue(p.component_findings(self.root,task,required=True))

    def test_stylekit_binding_must_cover_primary_and_all_usage(self):
        task,item=self.stylekit_resource_fixture()
        (self.root/'unbound.ts').write_text('Synthetic primary implementation')
        item['usage'].append('unbound.ts')
        item['render_checks'][0]['implementation']='unbound.ts'
        self.assertTrue(any('current vendored file hashes' in x for x in p.component_findings(self.root,task,required=True)))

    def test_reference_observation_freezes_reference_artifact(self):
        task,snapshot,observations=self.visual_fixture()
        (self.root/'reference.png').write_bytes(PNG)
        observations.append({'criterion':'reference_fidelity','location':'fixture region','observed':'Fixture comparison scope','status':'PASS','evidence':['shot.png'],'reference_file':'reference.png'})
        record=p.record(self.root,task,'visual',{'observations':observations})
        self.assertIn('reference.png',record['artifact_hashes'])
        before=record['artifact_hashes']['reference.png']
        (self.root/'reference.png').write_bytes(PNG+b'changed')
        self.assertNotEqual(before,p.sha(self.root/'reference.png'))

    def test_text_user_custom_reference_is_not_forced_to_be_an_image(self):
        task,snapshot,observations=self.visual_fixture()
        (self.root/'direction.md').write_text('Explicit synthetic user direction',encoding='utf-8')
        task.update(selected_reference='direction.md',reference_kind='text',design_plan={'selected_style':'user_custom'})
        snapshot['source_hashes']=p.hashes(self.root,task)
        p.save(self.root/'capture.json',snapshot)
        p.record(self.root,task,'browser',{'captures':['capture.json']})
        observations.append({'criterion':'reference_fidelity','location':'fixture direction','observed':'Synthetic text-only direction comparison','status':'PASS','evidence':['shot.png'],'reference_file':'direction.md'})
        p.record(self.root,task,'visual',{'observations':observations})
        result=p.verify(self.root)
        self.assertFalse(any('actual selected reference image' in x for x in result['blockers']),result)
        self.assertFalse(any('actual selected_reference' in x for x in result['blockers']),result)

    def test_full_page_cannot_count_only_a_listed_library_dialog(self):
        task,item=self.primary_library_fixture();task['level']='L3'
        item.update(name='Radix UI',imports=['@radix-ui/react-dialog'])
        (self.root/'usage.ts').write_text("import { Dialog } from '@radix-ui/react-dialog';")
        item['render_checks'][0]['component']='Dialog'
        self.assertTrue(any('only of overlays' in x for x in p.component_findings(self.root,task,required=True)))
        task['level']='L2'
        self.assertEqual(p.component_findings(self.root,task,required=True),[])

    def test_duplicate_observation_across_criteria_is_blocked(self):
        task,_,observations=self.visual_fixture()
        observations[1]['location']=observations[0]['location'];observations[1]['observed']=observations[0]['observed']
        p.record(self.root,task,'visual',{'observations':observations})
        self.assertTrue(any('duplicated observation' in x for x in p.verify(self.root)['blockers']))

    def test_rule_review_needs_condition_and_actual_implementation(self):
        task,_,observations=self.visual_fixture()
        route=next(x for x in p.load(p.SKILL/'references/original-rule-map.json')['rules'] if x['method']=='visual_review')
        entry=next(x for x in task['rule_application'] if x['id']==route['id']);entry.update(applicability='applicable',reason='Controlled review evidence test')
        observation={'criterion':'rule:'+route['id'],'location':'fixture region','observed':'Specific fixture observation, not product acceptance.','status':'PASS','evidence':['shot.png']}
        observations.append(observation);p.record(self.root,task,'visual',{'observations':observations})
        self.assertTrue(any('implementation and pass condition' in x for x in p.verify(self.root)['blockers']))
        (self.root/'reviewed.ts').write_text('Controlled reviewed source fixture')
        observation.update(implementation=['reviewed.ts'],condition='Controlled fixture pass condition, no design certification')
        p.record(self.root,task,'visual',{'observations':observations})
        self.assertFalse(any('implementation and pass condition' in x for x in p.verify(self.root)['blockers']))
        (self.root/'reviewed.ts').write_text('Changed implementation after review')
        self.assertTrue(any('evidence artifact changed' in x for x in p.verify(self.root)['blockers']))

    def test_l3_needs_actual_project_brief_requirements(self):
        task=self.task('L3')
        self.assertTrue(any('Project-specific' in x for x in p.project_findings(self.root,task,None)))

    def test_l1_local_visual_check_does_not_force_separate_review_pipeline(self):
        self.task('L1',visual=True)
        self.assertFalse(any('Separate-context model review missing' in x for x in p.verify(self.root)['blockers']))

    def test_project_requirement_rejects_weaker_or_wrong_scope_assertion(self):
        task=self.task('L2');(self.root/'brief.md').write_text('Controlled project requirement')
        assertion={'action':'expect_css_number','selector':'.meta','property':'fontSize','min':14}
        task['project_requirements']=[{'id':'readability','source':'brief.md','expected':'Fixture minimum 14px','implementation':['app.css'],
            'verification':{'mode':'browser','page':'main','width':390,'state':'default','assertion':assertion}}]
        browser={'assertions':[{'page':'main','width':390,'state':'default','checks':[{**assertion,'min':10}]}]}
        self.assertTrue(p.project_findings(self.root,task,browser))
        browser['assertions'][0]['checks']=[assertion]
        self.assertEqual(p.project_findings(self.root,task,browser),[])
        browser['assertions'][0]['width']=1440
        self.assertTrue(p.project_findings(self.root,task,browser))

    def packet_fixture(self):
        task,_,_=self.visual_fixture()
        (self.root/'brief.md').write_text('Original controlled fixture brief, no implementer verdict')
        result=p.review_packet.create(self.root,task,self.root/'packets',[self.root/'brief.md'])
        packet=Path(result['packet']);manifest=p.review_packet.validate(packet,self.root)
        return task,packet,manifest

    def test_review_packet_excludes_implementer_verdict_and_detects_copy_tamper(self):
        task,packet,manifest=self.packet_fixture()
        self.assertFalse(any(Path(item['path']).name=='visual.json' for item in manifest['files']))
        copied=packet.parent/manifest['files'][0]['path'];copied.write_text('tampered')
        with self.assertRaisesRegex(ValueError,'Frozen review input changed'):p.review_packet.validate(packet,self.root)

    def test_packet_detects_project_change_after_review(self):
        task,packet,manifest=self.packet_fixture()
        (self.root/'app.css').write_text('Changed current implementation')
        with self.assertRaisesRegex(ValueError,'stale relative'):p.review_packet.validate(packet,self.root)

    def independent_fixture(self,verdict):
        task,packet,manifest=self.packet_fixture()
        evidence=manifest['files'][0]['path']
        report={'schema':1,'packet_id':manifest['packet_id'],'reviewer':{'kind':'separate_model','id':'unit-fixture-only'},'verdict':verdict,
                'findings':[{'requirement':'fixture-only','location':'fixture region','observed':'Synthetic report parser test, not actual separate reviewer execution.',
                             'status':verdict,'evidence':[evidence]}]}
        p.save(self.root/'independent.json',report)
        task['independent_review']={'packet':str(packet.relative_to(self.root.resolve())),'report':'independent.json'}
        p.save(self.root/p.TASK_PATH,task)
        return task,packet,report

    def test_independent_known_failures_propagate(self):
        self.independent_fixture('FAIL')
        result=p.verify(self.root)
        self.assertEqual(result['status'],'FAIL')
        self.assertTrue(any('Independent model finding' in x for x in result['failures']))

    def test_independent_pass_cannot_unlock_protected_acceptance(self):
        self.independent_fixture('PASS');result=p.verify(self.root)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['visual_acceptance'],'BLOCKED')
    def test_approval_request_binds_actual_review_and_source(self):
        from types import SimpleNamespace
        task,packet,report=self.independent_fixture('PASS')
        api=SimpleNamespace(**vars(p))
        p.save(self.root/p.delivery_review.report_path(task),{'fixture':'Final review byte-binding input'})
        before=p.visual_approval.request_body(api,self.root,task)
        (self.root/'independent.json').write_text(json.dumps({**report,'note':'changed report'}))
        after=p.visual_approval.request_body(api,self.root,task)
        self.assertNotEqual(p.visual_approval.digest(before),p.visual_approval.digest(after))
        (self.root/'app.css').write_text('body{color:#6366F1;}')
        with self.assertRaises(ValueError):p.visual_approval.request_body(api,self.root,task)
    def test_visual_approval_cannot_override_other_failures(self):
        self.independent_fixture('PASS')
        (self.root/'app.css').write_text('body{color:#6366F1;}')
        with patch.object(p.visual_approval,'verify',return_value={'status':'APPROVED'}):
            self.assertEqual(p.verify(self.root)['status'],'FAIL')
    def test_copy_necessity_requires_concrete_decisions(self):
        task,snapshot,observations=self.visual_fixture()
        criterion=next(x for x in observations if x['criterion']=='copy_necessity')
        criterion.update(observed='Actual paragraph checked for operation value')
        p.record(self.root,task,'visual',{'observations':observations})
        self.assertTrue(any('copy_necessity needs actual text' in x for x in p.verify(self.root)['blockers']))
    def test_placeholder_detection_remains_active_without_length_limit(self):
        self.assertTrue(p.text_findings('<p>Lorem Ipsum</p>',None))
        self.assertEqual(p.text_findings('<p>我已阅读并同意用户协议与隐私政策，继续登录。</p>',None),[])

    def test_independent_report_cannot_reference_unrelated_evidence(self):
        task,packet,report=self.independent_fixture('PASS')
        report['findings'][0]['evidence']=['../arbitrary-file.png'];p.save(self.root/'independent.json',report)
        with self.assertRaisesRegex(ValueError,'outside the raw packet'):p.review_packet.read_report(packet,self.root/'independent.json',self.root)

    def test_component_doc_change_invalidates_execution(self):
        task,item=self.library_fixture();task['level']='L2';task['visual_reason']='Nonvisual fixture'
        task['checks'].append({'id':'project-check','type':'command','required':True});p.save(self.root/p.TASK_PATH,task)
        p.run_check(self.root,'project-check',[sys.executable,'-c','print("fixture")'])
        self.record_final_review()
        self.assertEqual(p.verify(self.root)['status'],'PASS')
        (self.root/'docs.md').write_text('Changed evidence')
        self.assertEqual(p.verify(self.root)['status'],'BLOCKED')

    def test_rendered_placeholder_text_and_exact_character_boundary(self):
        self.assertTrue(any('placeholder' in x for x in p.text_findings('<p>Lorem Ipsum</p>',15)))
        self.assertEqual(p.text_findings('<p>一二三四五，六七八九十，12345。</p>',15),[])
        self.assertTrue(p.text_findings('<p>一二三四五，六七八九十，123456。</p>',15))

    def test_rendered_dynamic_placeholder_and_emoji_are_reported(self):
        task,snapshot,_=self.visual_fixture()
        snapshot['html']='<p>Lorem Ipsum</p>';snapshot['functional_icons']=['🚀']
        p.save(self.root/'capture.json',snapshot)
        findings=p.browser_findings(self.root,task,['capture.json'])['findings']
        for expected in ('placeholder','Emoji'):self.assertTrue(any(expected in x for x in findings),findings)

    def content_asset_fixture(self):
        task=self.task()
        (self.root/'asset.png').write_bytes(png((100,120,20)))
        (self.root/'generation.md').write_text('Synthetic generation-record fixture; no actual image-tool call is claimed.')
        task['assets']=[{'origin':'builtin_image','role':'object_cutout','path':'asset.png','purpose':'Controlled schema fixture only','usage':['app.css'],'generation_evidence':'generation.md','url':'http://fixture/asset.png'}]
        browser={'image_urls':['http://fixture/asset.png'],'media_hashes':{'http://fixture/asset.png':p.sha(self.root/'asset.png')}}
        return task,browser

    def test_image_must_match_loaded_bytes_and_actual_usage(self):
        task,browser=self.content_asset_fixture()
        self.assertEqual(p.asset_findings(self.root,task,browser),([],[]))
        browser['media_hashes']['http://fixture/asset.png']='other'
        self.assertTrue(any('bytes' in x for x in p.asset_findings(self.root,task,browser)[1]))
        browser['image_urls']=[]
        self.assertTrue(any('usage' in x for x in p.asset_findings(self.root,task,browser)[1]))

    def test_reference_file_cannot_count_as_production_image(self):
        task,browser=self.content_asset_fixture();task['references']=[{'path':'asset.png'}]
        self.assertTrue(any('Style-reference' in x for x in p.asset_findings(self.root,task,browser)[0]))

    def test_background_only_and_external_generator_do_not_satisfy_assets(self):
        task,browser=self.content_asset_fixture();task['assets'][0]['role']='background'
        self.assertTrue(p.asset_findings(self.root,task,browser)[1])
        task['assets'][0].update(role='object_cutout',origin='third_party_generator')
        failures,gaps=p.asset_findings(self.root,task,browser)
        self.assertTrue(failures);self.assertTrue(gaps)

    def test_shader_and_model_remain_optional_but_need_decisions(self):
        task=self.task('L3')
        self.assertTrue(p.spatial_findings(self.root,task,required=True)[1])
        task['space_effects']={kind:{'decision':'omitted','reason':'Controlled static fixture does not benefit from spatial effects.'} for kind in ('shader','model')}
        self.assertEqual(p.spatial_findings(self.root,task,required=True),([],[]))

    def test_raster_cannot_be_model_and_visible_render_must_be_executed(self):
        task,browser=self.content_asset_fixture()
        task['space_effects']['model']={'decision':'used','reason':'Synthetic invalid-model scenario','generator':'tripo','path':'asset.png','generation_evidence':'generation.md','usage':['app.css'],'url':'http://fixture/asset.png','render_check':{'page':'home','width':390,'state':'default','selector':'canvas'}}
        failed,gaps=p.spatial_findings(self.root,task,browser)
        self.assertTrue(any('raster' in x for x in failed))
        self.assertTrue(any('render assertion' in x for x in gaps))

    def test_claimed_shader_render_needs_matching_actual_assertion(self):
        task=self.task();task['space_effects']['shader']={'decision':'used','reason':'Test shader record','usage':['app.css'],'render_check':{'page':'home','width':390,'state':'default','selector':'#scene'}}
        browser={'assertions':[{'page':'home','width':390,'state':'default','checks':[{'action':'expect_visible','selector':'#wrong'}]}]}
        self.assertTrue(p.spatial_findings(self.root,task,browser)[1])
        browser['assertions'][0]['checks'][0]['selector']='#scene'
        self.assertEqual(p.spatial_findings(self.root,task,browser),([],[]))

if __name__=='__main__':unittest.main(verbosity=2)
