"""Check the design contract before implementation; no product PASS is issued."""
import hashlib
import json
from pathlib import Path
import time

CORE_SECTIONS={'配色与背景','布局与字体','页面文案','组件与动效','图像与空间效果'}

def contract(task, root=None):
    library=task.get('component_libraries',{})
    body={key:task.get(key) for key in ('task_id','level','phase','visual','files','scope','design_plan','rule_application','project_requirements','selection_evidence','style_summary','asset_plan','implementation_checklist')}
    body['library']={'decision':library.get('decision'),'items':[{key:item.get(key) for key in ('name','role','version','docs_provider','docs_evidence','context7_limitation','imports','usage','customization','render_checks')} for item in library.get('items',[])]}
    body['library']['stylekit_priority']=library.get('stylekit_priority')
    body['selected_reference']=task.get('selected_reference')
    body['reference_kind']=task.get('reference_kind','image')
    body['checklist_plan']=task.get('checklist_plan')
    if root is not None and task.get('checklist_plan'):
        plan=(Path(root)/task['checklist_plan']).resolve()
        if not plan.is_relative_to(Path(root).resolve()):raise ValueError('Checklist plan escapes project')
        body['checklist_plan_hash']=hashlib.sha256(plan.read_bytes()).hexdigest() if plan.is_file() else None
    if root is not None:
        evidence=[task.get('selected_reference'),library.get('stylekit_priority',{}).get('search_evidence'),task.get('design_plan',{}).get('motion_plan',{}).get('docs_evidence')]
        evidence.extend(item.get(key) for item in library.get('items',[]) for key in ('docs_evidence','source_evidence'))
        body['planning_evidence']={}
        for name in filter(None,evidence):
            path=(Path(root)/name).resolve()
            if not path.is_relative_to(Path(root).resolve()):raise ValueError('Planning evidence escapes project')
            body['planning_evidence'][name]=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    body['design_document']=task.get('design_document')
    body['style_discovery']=task.get('style_discovery')
    body['style_contract']=task.get('style_contract')
    if root is not None and task.get('style_contract',{}).get('path'):
        source=(Path(root)/task['style_contract']['path']).resolve()
        if not source.is_relative_to(Path(root).resolve()):raise ValueError('Style contract escapes project')
        body['style_contract_hash']=hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None
    if root is not None and task.get('style_discovery'):
        discovery=(Path(root)/task['style_discovery']).resolve()
        if not discovery.is_relative_to(Path(root).resolve()):raise ValueError('Style discovery escapes project')
        body['style_discovery_hash']=hashlib.sha256(discovery.read_bytes()).hexdigest() if discovery.is_file() else None
    if root is not None and task.get('design_document')=='design.md':
        document=Path(root)/task['design_document']
        body['design_document_hash']=hashlib.sha256(document.read_bytes()).hexdigest() if document.is_file() else None
    return hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def required(task):
    return task.get('phase')=='implementation' and task.get('visual') and task.get('level') in ('L2','L3')

DESIGN_SECTIONS=('场景与目标','风格与依据','设计 Tokens','布局与内容','组件与状态','动态与交互','素材计划','验收计划')
USER_ACTIONS={'click','fill','press','check','hover','move_pointer'}

def change_pairs(steps,kind):
    """Find baseline/input/change sequences; a visible unchanged button is insufficient."""
    baselines={};pairs=[]
    for index,step in enumerate(steps):
        action=step.get('action')
        if action=='remember_'+kind and step.get('name'):
            baseline={**step,'selector':None} if kind=='state' and step.get('property')=='url' else step
            baselines[step['name']]=(index,baseline)
        elif action=='expect_'+kind+'_changed' and step.get('name') in baselines:
            start,baseline=baselines[step['name']]
            triggers=[item for item in steps[start+1:index] if item.get('action') in USER_ACTIONS]
            if triggers and (step.get('selector') is None or step['selector']==baseline.get('selector')):
                pairs.append((start,index,baseline,step,triggers))
    return pairs

def detail_gaps(task):
    """Require regional decisions for full pages, not fixed illustration/animation quotas."""
    if task.get('level')!='L3':return []
    plan=task.get('design_plan',{});gaps=[]
    surfaces=plan.get('visual_surfaces',[])
    if not isinstance(surfaces,list) or not surfaces or any(not all(item.get(key) for key in ('selector','color_roles','material','reference_features')) for item in surfaces):
        gaps.append('Plan visual_surfaces with region selectors, color roles, material parameters and reference features')
    coverage=plan.get('asset_coverage',[])
    if not isinstance(coverage,list):coverage=[]
    identifiers=set();pages={view.get('page') for view in task.get('scope',[])}
    if not coverage or not pages.issubset({item.get('page') for item in coverage}):gaps.append('Plan asset_coverage for each page, including justified omissions')
    for item in coverage:
        if not all(item.get(key) for key in ('id','role','page','purpose','reason')) or item.get('id') in identifiers or item.get('page') not in pages or item.get('decision') not in ('generate','omit') or (item.get('decision')=='generate' and not item.get('selector')):
            gaps.append('Asset coverage needs unique IDs, actual page/role/purpose and generation or omission reasons')
        identifiers.add(item.get('id'))
    buttons=plan.get('button_feedback',[])
    if not isinstance(buttons,list):buttons=[]
    if not buttons and not plan.get('button_feedback_reason'):gaps.append('Plan button_feedback or explain why this interface has no buttons')
    for button in buttons:
        if not all(button.get(key) for key in ('selector','page','trigger','states','visual_response','motion','reduced_motion')) or len(set(button.get('states',[])))<2:
            gaps.append('Button feedback needs actual states, visual response, nonlinear motion and reduced-motion behavior')
        check=button.get('verification',{})
        if check.get('page')!=button.get('page') or not any(all(view.get(key)==check.get(key) for key in ('page','width','state')) for view in task.get('scope',[])):
            gaps.append('Button verification must match a declared page/viewport/state')
        pairs=change_pairs(check.get('steps',[]),'style')
        if not pairs or any(baseline.get('selector')!=button.get('selector') for _,_,baseline,_,_ in pairs):gaps.append('Button visual feedback needs remember_style, real input and expect_style_changed on the actual button')
    return gaps

def discovery_gaps(api,root,task):
    if task.get('level')!='L3':return style_contract_gaps(api,root,task) if task.get('style_contract') else []
    problems=[]
    try:
        discovery=api.load(api.local(root,task.get('style_discovery')))
        if not all(discovery.get(key) for key in ('scene','source','queried_at')):
            problems.append('Record actual scene, StyleKit source and query time')
        mode=discovery.get('mode')
        if mode=='new':
            options=discovery.get('options',[])
            if len(options)!=4 or {item.get('id') for item in options}!=set('ABCD'):
                problems.append('New style discovery requires A/B/C/D directions')
            facets=('layout','typography','components','material','imagery')
            for option in options:
                if not all(option.get(key) for key in (*facets,'style_name','style_slug','source','motion')):
                    problems.append('Each style option needs actual style_name/style_slug, concrete visual facets and motion intent')
            for index,left in enumerate(options):
                for right in options[index+1:]:
                    different=sum(str(left.get(key,'')).strip().lower()!=str(right.get(key,'')).strip().lower() for key in facets)
                    if different<3:problems.append('Style options repeat the same non-color visual language')
        elif mode in ('existing','user_custom'):
            api.local(root,discovery.get('evidence'))
        else:problems.append('Record new, existing or user_custom style discovery mode')
    except (OSError,ValueError,TypeError,KeyError) as exc:problems.append('Style discovery missing or invalid: '+str(exc))
    problems.extend(style_contract_gaps(api,root,task))
    motion=task.get('design_plan',{}).get('motion_plan',{})
    if not motion.get('engine') or not motion.get('reason'):problems.append('Choose and justify the motion engine before coding')
    try:api.local(root,motion.get('docs_evidence'))
    except (OSError,ValueError) as exc:problems.append('Motion documentation evidence missing: '+str(exc))
    pointer=motion.get('pointer',{})
    if pointer.get('decision') not in ('used','omitted') or not all(pointer.get(key) for key in ('reason','touch_fallback','keyboard_fallback','reduced_motion','cleanup')):
        problems.append('Plan pointer adoption, fallbacks, reduced motion and cleanup')
    return problems

def style_contract_gaps(api,root,task):
    contract=task.get('style_contract',{})
    if not contract:
        try:discovery=api.load(api.local(root,task.get('style_discovery')))
        except (OSError,ValueError,TypeError):return ['Complete StyleKit contract and discovery record are missing']
        if discovery.get('mode')=='user_custom':return []
        return ['Fetch the complete selected-language StyleKit design document and register style_contract']
    problems=[]
    try:
        source=api.local(root,contract.get('path'))
        text=source.read_text(encoding='utf-8')
        design=api.local(root,'design.md').read_text(encoding='utf-8')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=contract.get('sha256'):
            problems.append('Style document hash changed; refresh the actual source and affected evidence')
        if 'Implementation Contract' not in text or text not in design:
            problems.append('design.md must preserve the complete StyleKit document and Implementation Contract')
        if not all(contract.get(key) for key in ('slug','locale','source_url')):
            problems.append('Style contract needs selected slug, language and actual URL')
        plan=task.get('design_plan',{})
        if plan.get('style_slug')!=contract.get('slug') or plan.get('document_locale')!=contract.get('locale'):
            problems.append('Style contract differs from the selected style or requested document language')
        discovery=api.load(api.local(root,task.get('style_discovery')))
        if discovery.get('mode')=='new':
            chosen=next((x for x in discovery.get('options',[]) if x.get('id')==plan.get('selected_style')),None)
            if chosen and chosen.get('style_slug')!=contract.get('slug'):problems.append('Style contract slug does not match the chosen A/B/C/D option')
    except (OSError,ValueError,KeyError,TypeError) as exc:problems.append('Style contract missing or invalid: '+str(exc))
    return problems

def design_gaps(api,root,task):
    problems=[]
    if task.get('level')=='L3':
        try:
            reference=api.local(root,task.get('selected_reference'))
            kind=task.get('reference_kind','image')
            if kind=='text':
                if task.get('design_plan',{}).get('selected_style')!='user_custom' or not reference.read_text(encoding='utf-8-sig').strip():problems.append('Text reference must preserve an explicit user_custom direction')
            elif kind!='image' or not api.image_artifact(reference):problems.append('Register the real selected reference image')
        except (OSError,ValueError,TypeError) as exc:problems.append('Selected reference missing: '+str(exc))
    if task.get('design_document')!='design.md':
        problems.append('Write project-root design.md before visual implementation')
    else:
        try:
            text=api.local(root,'design.md').read_text(encoding='utf-8-sig')
            import re
            for section in DESIGN_SECTIONS:
                match=re.search(r'^## '+re.escape(section)+r'\s*\n(.*?)(?=^## |\Z)',text,re.M|re.S)
                if not match or not match.group(1).strip():problems.append('design.md needs actual content under '+section)
        except (OSError,ValueError) as exc:problems.append(str(exc))
    plan=task.get('design_plan',{})
    for key in ('scene','style_direction','tokens'):
        if not plan.get(key):problems.append('Record scene-led design decision: '+key)
    components=plan.get('dynamic_components',[])
    if not isinstance(components,list):return problems+['dynamic_components must be a list']
    pages={view['page'] for view in task.get('scope',[])}
    if task['level']=='L3' and not pages.issubset({item.get('page') for item in components}):
        problems.append('Plan a task-serving dynamic component for each declared page')
    if not components and task['level']=='L2' and not plan.get('dynamic_scope_reason'):
        problems.append('Explain existing interaction scope for this local visual change')
    identifiers=set()
    for component in components:
        fields=('id','page','selector','purpose','trigger','motion','reduced_motion')
        if not all(component.get(key) for key in fields) or component.get('id') in identifiers:
            problems.append('Dynamic components need unique IDs and concrete behavior plans')
        identifiers.add(component.get('id'))
        states=component.get('states',[])
        if not isinstance(states,list) or len(set(states))<2:problems.append('Dynamic component needs distinct before/after states')
        verification=component.get('verification',{})
        if verification.get('page')!=component.get('page') or not any(all(view.get(key)==verification.get(key) for key in ('page','width','state')) for view in task.get('scope',[])):
            problems.append('Dynamic component verification must match declared page/viewport/state')
        steps=verification.get('steps',[])
        if not change_pairs(steps,'state'):
            problems.append('Dynamic verification needs a real trigger between remember_state and expect_state_changed; unchanged visibility is insufficient')
    problems.extend(detail_gaps(task))
    return problems

def dynamic_execution_gaps(task,browser_result):
    if not required(task):return []
    gaps=[]
    plan=task.get('design_plan',{})
    requirements=[(item,'state') for item in plan.get('dynamic_components',[])]+[(item,'style') for item in plan.get('button_feedback',[])]
    for component,kind in requirements:
        expected=component.get('verification',{})
        planned=expected.get('steps',[])
        matched=False
        for result in (browser_result or {}).get('assertions',[]):
            if not all(result.get(key)==expected.get(key) for key in ('page','width','state')):continue
            actual=result.get('steps',[])
            for offset in range(len(actual)-len(planned)+1):
                if not planned or actual[offset:offset+len(planned)]!=planned:continue
                pairs=change_pairs(planned,kind)
                if pairs and all(any(change.get('name')==baseline.get('name') and change.get('selector')==baseline.get('selector') and change.get('property')==baseline.get('property') and change.get('before')!=change.get('after') and change.get('trigger_steps')==triggers and change.get('before_step')==offset+start and change.get('after_step')==offset+end for change in result.get(kind+'_changes',[])) for start,end,baseline,assertion,triggers in pairs):
                    matched=True
        if not matched:gaps.append('Dynamic component lacks executed trigger/result sequence and measured '+kind+' change: '+str(component.get('id') or component.get('selector')))
    return gaps

def check(api,root,task,issue=False):
    problems=[]
    if not required(task):return {'status':'PASS','stage':'preflight','scope':'No new implementation preflight required for this task scope'}
    problems.extend(api.initialization_gaps(root,task))
    problems.extend(api.checklist.planning_gaps(api,root,task))
    problems.extend(design_gaps(api,root,task))
    problems.extend(discovery_gaps(api,root,task))
    if task.get('policy_hash')!=api.policy_hash():problems.append('Preflight requires the current rules and policy snapshot')
    catalog=api.validate_rule_binding();routes={x['id']:x for x in api.load(api.SKILL/'references/original-rule-map.json')['rules']}
    applications={x['id']:x for x in task.get('rule_application',[])}
    for item in catalog:
        application=applications.get(item['id'],{})
        if application.get('applicability') not in ('applicable','out_of_scope','conditional') or not application.get('reason'):problems.append('Resolve rule scope: '+item['id'])
        if task['level']=='L3' and item['section'] in CORE_SECTIONS and not routes[item['id']].get('conditional_allowed') and routes[item['id']]['method']!='advisory' and application.get('applicability')!='applicable':
            problems.append('Full UI cannot exclude original design requirement: '+item['id'])
    plan=task.get('design_plan',{})
    if not plan.get('layout_regions') or not all(item.get('selector') and item.get('decision') for item in plan.get('layout_regions',[])):problems.append('Design actual layout regions and their asymmetric composition before coding')
    for key in ('typography','material','copy','motion'):
        if not str(plan.get(key,'')).strip():problems.append('Design plan missing: '+key)
    library_required=task['level']=='L3' or any(applications.get(x['id'],{}).get('applicability')=='applicable' and ('Context7' in x['text'] or '组件库' in x['text']) for x in catalog)
    if library_required:
        library=task.get('component_libraries',{})
        primary=[x for x in library.get('items',[]) if x.get('role')=='primary_ui']
        if library.get('decision')!='used' or not primary:problems.append('Choose a listed primary UI library before coding; a helper is insufficient')
        if task['level']=='L3':
            priority=library.get('stylekit_priority',{})
            if priority.get('decision') not in ('used','fallback') or not priority.get('reason'):problems.append('Record StyleKit-first component selection and the actual fallback reason')
            try:api.local(root,priority.get('search_evidence'))
            except (OSError,ValueError) as exc:problems.append('StyleKit resource search evidence missing: '+str(exc))
            if priority.get('decision')=='used' and not any(item.get('name')=='StyleKit' for item in primary):problems.append('StyleKit-first adoption needs actual primary resource records')
        for item in primary:
            if item.get('name') not in ('StyleKit','Magic UI','Aceternity UI','DaisyUI','Brutalist UI','Glass UI','Radix UI','Mantine'):problems.append('Primary UI library is outside the user list')
            fields=('version','customization','usage','render_checks') if item.get('name')=='StyleKit' else ('version','customization','imports','usage','render_checks')
            for key in fields:
                if not item.get(key):problems.append('Primary UI adoption plan missing: '+key)
            if item.get('docs_provider') not in ('context7','official'):problems.append('Actual library documentation must be checked before coding')
            if item.get('name')!='StyleKit' and item.get('docs_provider')=='official' and not item.get('context7_limitation'):problems.append('Record the actual Context7 limitation')
            try:api.local(root,item.get('docs_evidence'))
            except (OSError,ValueError) as exc:problems.append(str(exc))
    if task['level']=='L3':
        if plan.get('selected_style') not in list('ABCD')+['user_custom']:problems.append('Record the actual user-selected direction before implementation')
        for field in ('selection_evidence','style_summary','asset_plan','implementation_checklist'):
            try:api.local(root,task.get(field),must_exist=not(field=='implementation_checklist' and task.get('checklist_plan')))
            except (OSError,ValueError):problems.append('Prepare actual workflow input: '+field)
        content=[x for x in plan.get('assets',[]) if x.get('role') in ('main_visual','scene_illustration','character','object_cutout','state_illustration','editorial_image','ornament') and x.get('purpose') and x.get('placement')]
        if not content:problems.append('Plan a generated non-background content asset and its actual placement')
        if not task.get('project_requirements'):problems.append('Translate the actual project brief into acceptance requirements')
        for kind in ('shader','model'):
            effect=task.get('space_effects',{}).get(kind,{})
            if effect.get('decision') not in ('used','omitted') or not effect.get('reason'):problems.append('Decide '+kind+' use or omission and record why')
    if not task.get('scope'):problems.append('Declare actual pages, states and widths before coding')
    if task['level']=='L3' and any(view.get('root_selector','body') not in ('body','html') for view in task.get('scope',[])):
        problems.append('Full-page acceptance cannot narrow the capture root to a small passing component')
    result={'status':'BLOCKED' if problems else 'PASS','stage':'preflight','blockers':problems,'task_id':task['task_id'],'contract_hash':contract(task,root),'policy_hash':api.policy_hash(),'checked_at':time.time(),'scope':'Implementation planning only; no source, tool provenance or visual acceptance is certified'}
    if issue and not problems:
        target=api.CENTER/'preflights'/(task['task_id']+'.json');api.save(target,{**result,'root':str(Path(root).resolve())})
    return result

def receipt_gaps(api,root,task):
    if not required(task):return []
    path=api.CENTER/'preflights'/(task['task_id']+'.json')
    if not path.is_file():return ['Implementation preflight has not run; resolve planning requirements before coding']
    receipt=api.load(path)
    if receipt.get('root')!=str(Path(root).resolve()) or receipt.get('contract_hash')!=contract(task,root) or receipt.get('policy_hash')!=api.policy_hash():return ['Implementation plan/policy changed; rerun preflight and recheck affected work']
    return []
