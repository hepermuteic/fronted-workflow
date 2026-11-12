"""Planning and evidence regressions for regional fidelity and asset coverage."""
import base64
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from test_release import p,plan,dynamic_component


class Planning43Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='frontend-43-plan-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'index.html').write_text('<main>Fixture</main>')
        self.task=plan(self.root,level='L3')

    def test_regional_decisions_are_required_for_full_pages_only(self):
        self.assertEqual(p.preflight.detail_gaps(self.task),[])
        for key in ('visual_surfaces','asset_coverage','button_feedback'):
            task=deepcopy(self.task);task['design_plan'].pop(key)
            self.assertTrue(any(key in gap for gap in p.preflight.detail_gaps(task)),key)
            task['level']='L2'
            self.assertEqual(p.preflight.detail_gaps(task),[])

    def test_coverage_allows_scene_appropriate_omissions_not_duplicate_ids(self):
        self.task['scope'].append({'page':'login','width':390,'state':'default'})
        coverage=self.task['design_plan']['asset_coverage']
        self.assertTrue(p.preflight.detail_gaps(self.task))
        coverage.append({'id':'login-art','role':'scene_illustration','page':'login','purpose':'Login needs a clear form','decision':'omit','reason':'Selected composition uses a compact wordmark here'})
        self.assertEqual(p.preflight.detail_gaps(self.task),[])
        coverage[1]['id']=coverage[0]['id']
        self.assertTrue(p.preflight.detail_gaps(self.task))

    def test_unchanged_visibility_is_not_a_dynamic_plan(self):
        component=self.task['design_plan']['dynamic_components'][0]
        component['verification']['steps']=[{'action':'click','selector':'#target'},{'action':'expect_visible','selector':'#target'}]
        self.assertTrue(any('remember_state' in gap for gap in p.preflight.design_gaps(p,self.root,self.task)))

    def test_text_result_cannot_substitute_for_button_visual_feedback(self):
        button=self.task['design_plan']['button_feedback'][0]
        button['verification']['steps']=dynamic_component()['verification']['steps']
        self.assertTrue(any('remember_style' in gap for gap in p.preflight.detail_gaps(self.task)))

    def test_steps_without_measured_changes_cannot_claim_executed_dynamics(self):
        task=deepcopy(self.task);task['design_plan'].pop('button_feedback')
        check=dynamic_component()['verification'];steps=check['steps']
        record={'assertions':[{**check,'steps':steps}]}
        self.assertTrue(p.preflight.dynamic_execution_gaps(task,record))
        record['assertions'][0]['state_changes']=[{'name':'practice-result','selector':'#result','property':'text','before':'准备','after':'完成','trigger_steps':[steps[1]],'before_step':0,'after_step':2}]
        self.assertEqual(p.preflight.dynamic_execution_gaps(task,record),[])
        record['assertions'][0]['state_changes'][0]['after']='准备'
        self.assertTrue(p.preflight.dynamic_execution_gaps(task,record))

    def test_surface_comparison_needs_each_planned_region(self):
        self.assertTrue(p.surface_review_gaps(self.task,{}))
        record={'surface_comparisons':[{'selector':'body','expected':'Warm light canvas and dark green ink','observed':'Rendered warm canvas and dark ink','deviation':'No observed mismatch in this fixture','decision':'Retain fixture appearance'}]}
        self.assertEqual(p.surface_review_gaps(self.task,record),[])
        self.task['design_plan']['visual_surfaces'].append({'selector':'#focus'})
        self.assertTrue(p.surface_review_gaps(self.task,record))

    def prepare_asset(self):
        asset=self.root/'asset.png'
        asset.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/58HAAMBAQDJ/pLvAAAAAElFTkSuQmCC'))
        # A schema fixture is not an assertion that an image tool was called.
        (self.root/'generation.md').write_text('Synthetic schema-only provenance fixture')
        self.task['selected_reference']='direction.txt';self.task['reference_kind']='text'
        (self.root/'direction.txt').write_text('Controlled custom direction')
        url='http://fixture/asset.png'
        check={'page':'main','width':390,'state':'default','selector':'#illustration'}
        self.task['assets']=[{'id':'fixture-object','origin':'builtin_image','role':'object_cutout','path':'asset.png','purpose':'Schema fixture','usage':['index.html'],'generation_evidence':'generation.md','url':url,'render_check':check}]
        return {'image_urls':[url],'media_hashes':{url:p.sha(asset)},'rendered_images':[{**check,'selectors':['#illustration'],'url':url}]}

    def test_url_baseline_selector_matches_runner_normalization(self):
        task=deepcopy(self.task);task['design_plan'].pop('button_feedback')
        check=task['design_plan']['dynamic_components'][0]['verification']
        check['steps']=[{'action':'remember_state','name':'url','property':'url','selector':'#target'},{'action':'click','selector':'#target'},{'action':'expect_state_changed','name':'url'}]
        record={'assertions':[{**check,'state_changes':[{'name':'url','selector':None,'property':'url','before':'fixture://main','after':'fixture://main#done','trigger_steps':[check['steps'][1]],'before_step':0,'after_step':2}]}]}
        self.assertEqual(p.preflight.dynamic_execution_gaps(task,record),[])

    def test_asset_coverage_binds_actual_role_file_and_rendered_placement(self):
        browser=self.prepare_asset()
        self.assertEqual(p.asset_findings(self.root,self.task,browser),([],[]))
        browser['rendered_images'][0]['selectors']=['#wrong']
        self.assertTrue(any('visibly rendered' in gap for gap in p.asset_findings(self.root,self.task,browser)[1]))
        browser=self.prepare_asset();self.task['assets'][0]['role']='main_visual'
        self.assertTrue(any('role binding' in gap for gap in p.asset_findings(self.root,self.task,browser)[1]))

    def test_selected_reference_cannot_count_as_content_even_without_references_array(self):
        browser=self.prepare_asset()
        self.task['selected_reference']='asset.png';self.task['reference_kind']='image';self.task['references']=[]
        self.assertTrue(any('Style-reference' in failure for failure in p.asset_findings(self.root,self.task,browser)[0]))


if __name__=='__main__':unittest.main()
