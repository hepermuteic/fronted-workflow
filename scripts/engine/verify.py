"""Task-scoped frontend policy. Hooks never launch project commands or models."""
from __future__ import annotations
import argparse
import difflib
import hashlib
import colorsys
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import sys
import time
import unicodedata
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parent))
import host_check
import review_packet
import quality_checks
import preflight
import visual_approval
import checklist
import typography
import delivery_review
import critic
import paths
from types import SimpleNamespace

CODE_DIR = paths.CODE_DIR
CENTER = paths.STATE_DIR
SKILL = paths.SKILL_ROOT
TASK_PATH = Path('work/frontend-policy/task.json')
RESULT_PATH = Path('work/frontend-policy/result.json')
SOURCE_EXT = {'.html', '.css', '.scss', '.sass', '.less', '.vue', '.svelte', '.tsx', '.jsx', '.js', '.ts', '.mjs', '.mts', '.cjs', '.cts'}

def load(path):
    path = Path(path)
    if path.stat().st_size > 15_000_000:
        raise ValueError('Evidence JSON exceeds size limit')
    return json.loads(path.read_text(encoding='utf-8-sig'))

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def image_artifact(path):
    with Path(path).open('rb') as stream:
        prefix = stream.read(32)
    return len(prefix) >= 16 and (prefix.startswith((b'\x89PNG\r\n\x1a\n',b'\xff\xd8\xff')) or (prefix[:4] == b'RIFF' and prefix[8:12] == b'WEBP'))

def config():
    return load(SKILL / 'references/policy.json')

def original_rules():
    return (SKILL / config()['source_rules']).resolve()

def active_rules(task):
    if task['profile'] not in config()['profiles']:
        raise ValueError('Unknown rule profile')
    return config()['strict_rules']

def rule_catalog():
    section='';items=[]
    for line_number,line in enumerate(original_rules().read_text(encoding='utf-8-sig').splitlines(),1):
        if line.startswith('## '):section=line[3:].strip()
        if not line.startswith('- '):continue
        text=line[2:].strip()
        identifier=hashlib.sha256((section+'\n'+text).encode()).hexdigest()[:16]
        items.append({'id':identifier,'section':section,'line':line_number,'text':text})
    return items

def validate_rule_binding():
    catalog=rule_catalog()
    mapping=load(SKILL/'references/original-rule-map.json')
    by_id={item['id']:item for item in mapping['rules']}
    allowed={'visual_review','tool_provenance','automated','advisory','workflow'}
    if len(by_id)!=len(mapping['rules']) or any(item.get('method') not in allowed or not item.get('route') or not item.get('limitation') for item in by_id.values()):
        raise ValueError('Invalid or duplicate original rule routes')
    missing=[item['id'] for item in catalog if item['id'] not in by_id or not by_id[item['id']].get('method')]
    if missing:raise ValueError('Original requirements have no enforcement route: '+','.join(missing))
    if set(by_id)!={item['id'] for item in catalog}:raise ValueError('Rule map is stale; reconcile it with the original document')
    return catalog

def forbidden_hue(value):
    return quality_checks.forbidden_color(value)

def preflight_check(root,task,issue=False):
    return preflight.check(SimpleNamespace(**globals()),root,task,issue)


def policy_hash():
    parts = [original_rules(),Path(__file__),Path(__file__).with_name('host_check.py'),Path(__file__).with_name('review_packet.py'),Path(__file__).with_name('preflight.py'),Path(__file__).with_name('quality_checks.py'),Path(__file__).with_name('doctor.py'),Path(__file__).with_name('browser-run.cjs'),Path(__file__).with_name('visual_approval.py'),Path(__file__).with_name('approval_signer.py'),Path(__file__).with_name('checklist.py'), SKILL / 'SKILL.md', SKILL/'agents/openai.yaml', *sorted((SKILL / 'references').glob('*')), *sorted((SKILL / 'scripts').glob('*'))]
    parts.extend(Path(__file__).with_name(name) for name in ('typography.py','font_capture.cjs','delivery_review.py','critic.py'))
    parts.extend(sorted(CODE_DIR.glob('*.py')))
    parts.extend(sorted(CODE_DIR.glob('*.cjs')))
    parts.append(critic.AGENT_FILE)
    if not original_rules().is_file():raise ValueError('Original rules are unavailable; verification is blocked')
    return hashlib.sha256(''.join(sha(path) for path in parts if path.is_file()).encode()).hexdigest()

def local(root, value, must_exist=True):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('An evidence/source path is missing')
    root = Path(root).resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Path escapes the task project: ' + value)
    if must_exist and (not path.is_file() or path.stat().st_size == 0):
        raise ValueError('Missing/empty file: ' + value)
    return path

def discover(root):
    root = Path(root).resolve()
    package = load(root / 'package.json') if (root / 'package.json').is_file() else {}
    deps = {**package.get('dependencies', {}), **package.get('devDependencies', {})}
    framework = next((name for dep, name in [('next','Next/React'),('nuxt','Nuxt/Vue'),('vue','Vue'),('react','React'),('@angular/core','Angular'),('svelte','Svelte')] if dep in deps), 'HTML/other')
    manager = next((manager for filename, manager in [('pnpm-lock.yaml','pnpm'),('yarn.lock','yarn'),('bun.lockb','bun'),('bun.lock','bun')] if (root / filename).exists()), 'npm')
    scripts = package.get('scripts', {})
    return {'root': str(root), 'framework': framework, 'package_manager': manager,
            'scripts': scripts, 'start_candidates': [key for key in ('dev','start','serve','preview') if key in scripts],
            'check_candidates': [key for key in ('test','test:unit','typecheck','lint','build') if key in scripts]}

def input_paths(task, include_runtime=True):
    runtime=list(task.get('runtime_sources', {}).values()) if include_runtime else []
    if include_runtime and task.get('deployment',{}).get('mode')=='build':
        runtime.extend(name for check in task.get('checks',[]) if check['id']==task['deployment'].get('check_id') for name in check.get('outputs',[]))
    paths = list(dict.fromkeys(list(task.get('baseline',{}).values()) + task.get('files', []) + runtime + [item['path'] for item in task.get('assets', [])] + [item['path'] for item in task.get('references', [])]))
    if task.get('reference_gallery'):
        paths.append(task['reference_gallery'])
    for asset in task.get('assets',[]):
        paths.extend(asset.get('usage',[]))
        if asset.get('generation_evidence'):paths.append(asset['generation_evidence'])
    for field in ('selection_evidence','style_summary','asset_plan','implementation_checklist','checklist_plan','design_document','style_discovery','selected_reference'):
        if field=='implementation_checklist' and task.get('checklist_plan'):
            continue
        if task.get(field):paths.append(task[field])
    for library in task.get('component_libraries',{}).get('items',[]):
        paths.extend(library.get('usage',[]))
        if library.get('docs_evidence'):paths.append(library['docs_evidence'])
        if library.get('source_evidence'):paths.append(library['source_evidence'])
    motion_docs=task.get('design_plan',{}).get('motion_plan',{}).get('docs_evidence')
    if motion_docs:paths.append(motion_docs)
    resource_search=task.get('component_libraries',{}).get('stylekit_priority',{}).get('search_evidence')
    if resource_search:paths.append(resource_search)
    if task.get('style_contract',{}).get('path'):paths.append(task['style_contract']['path'])
    for requirement in task.get('project_requirements',[]):
        if requirement.get('source'):paths.append(requirement['source'])
        paths.extend(requirement.get('implementation',[]))
    for effect in task.get('space_effects',{}).values():
        if effect.get('decision')=='used':
            paths.extend(effect.get('usage',[]))
            for key in ('path','generation_evidence'):
                if effect.get(key):paths.append(effect[key])
    return list(dict.fromkeys(paths))

def hashes(root, task, include_runtime=True):
    return {name: sha(local(root, name)) for name in input_paths(task,include_runtime)}

def review_criteria(level,profile,phase,interactive):
    if phase == 'reference':
        return []  # Mood references are shown directly; formal UI review starts after selection.
    criteria = ['changed_region'] if level == 'L1' else ['changed_component','readability','responsive'] if level == 'L2' else ['composition','typography','readability','responsive']
    if level != 'L1':
        criteria += ['copy_tone_and_facts','copy_necessity','layout_regions','component_customization']
    if level == 'L3':
        criteria += ['materials','assets','reference_fidelity']
    if interactive:
        criteria.append('interaction_states')
    return criteria

def init_task(root, level, summary, files, profile='strict', phase='implementation', visual=None, interactive=False, pages=None, widths=None, states=None, replace=False):
    validate_rule_binding()
    root = Path(root).resolve()
    dest = root / TASK_PATH
    if dest.exists() and not replace:
        raise ValueError('A task exists. Use --replace for a new task; old records will be archived.')
    if dest.exists():
        previous = load(dest)
        save(root / 'work/frontend-policy/history' / (previous['task_id'] + '.json'), previous)
    visual = level != 'L1' if visual is None else visual
    task_id = uuid.uuid4().hex
    checks = [{'id': 'source', 'type': 'source', 'required': True}]
    project = discover(root)
    if phase == 'reference':
        checks = [{'id':'references', 'type':'references', 'required':True}]
    else:
        if level in ('L2','L3') and (project['check_candidates'] or not visual):
            checks.append({'id':'project-check', 'type':'command', 'required':True})
        if visual:
            checks += [{'id':'browser', 'type':'browser', 'required':True}, {'id':'visual', 'type':'review', 'required':True}]
        if interactive:
            checks.append({'id':'interaction', 'type':'command', 'required':True})
        if level == 'L3':
            checks.append({'id':'assets', 'type':'assets', 'required':True})
    baseline = {}
    for filename in files:
        path = local(root, filename, must_exist=False)
        if path.is_file():
            snapshot = f'work/frontend-policy/evidence/{task_id}/baseline/{hashlib.sha256(filename.encode()).hexdigest()[:16]}.txt'
            local(root, snapshot, False).parent.mkdir(parents=True, exist_ok=True)
            local(root, snapshot, False).write_text(path.read_text(encoding='utf-8-sig'), encoding='utf-8')
            baseline[filename] = snapshot
    task = {'schema':2,'task_id':task_id,'created_at':time.time(),'summary':summary,'level':level,'profile':profile,
            'phase':phase,'policy_version':config()['version'],'policy_hash':policy_hash(),'discovery':project,
            'files':files,'baseline':baseline,'visual':visual,'interactive':interactive,'checks':checks,
            'scope':[{'page':page,'width':width,'state':state} for page in (pages or ['main']) for width in (widths or [390,1280]) for state in (states or ['default'])],
            'runtime_sources':{},'assets':[],'references':[],'evidence':{},'visual_reason':'',
            'review_criteria':review_criteria(level,profile,phase,interactive),
            'original_rules_sha256':sha(original_rules()),'rule_application':[
                {'id':item['id'],'applicability':'pending','reason':''} for item in rule_catalog()]}
    task['component_libraries']={'decision':'pending','reason':'','items':[]}
    task['project_requirements']=[]
    task['space_effects']={name:{'decision':'pending','reason':''} for name in ('shader','model')}
    save(dest, task)
    save(CENTER/'initializations'/(task_id+'.json'),{'root':str(root),'task_id':task_id,'level':level,'phase':phase,'files':files,'baseline':baseline,'baseline_hashes':{name:sha(local(root,name)) for name in baseline.values()}})
    return task

def initialization_gaps(root,task):
    identifier=task.get('task_id','')
    if not re.fullmatch('[0-9a-f]{32}',identifier):return ['Invalid initialized task identity']
    receipt=load(CENTER/'initializations'/(identifier+'.json'))
    if receipt.get('root')!=str(Path(root).resolve()) or receipt.get('task_id')!=identifier:return ['Initialization does not belong to this task/root']
    ranks={'L1':1,'L2':2,'L3':3}
    if ranks.get(task.get('level'),0)<ranks.get(receipt.get('level'),0) or receipt.get('phase')!=task.get('phase'):return ['Task level/phase changed to a weaker scope after initialization; do not downgrade acceptance']
    if not set(receipt.get('files',[]))<=set(task.get('files',[])):return ['Initially declared implementation files were removed from acceptance scope']
    if receipt.get('baseline')!=task.get('baseline') or any(sha(local(root,name))!=digest for name,digest in receipt.get('baseline_hashes',{}).items()):return ['Initialization baseline was changed; it cannot hide newly introduced violations']
    return []

def record(root, task, check_id, body):
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,50}',check_id):
        raise ValueError('Invalid check identifier')
    check = next((item for item in task['checks'] if item['id'] == check_id), None)
    if not check:
        raise ValueError('Unknown planned check: ' + check_id)
    artifacts = list(body.get('captures', []))
    for name in body.get('captures', []):
        snapshot=load(local(root,name))
        artifacts.append(snapshot['screenshot'])
        if snapshot.get('region_screenshot'):
            artifacts.append(snapshot['region_screenshot'])
    for observation in body.get('observations', []):
        artifacts.extend(observation.get('evidence', []))
        artifacts.extend(observation.get('implementation', []))
        if observation.get('reference_file'):artifacts.append(observation['reference_file'])
    if body.get('log'):
        artifacts.append(body['log'])
    if body.get('diagnostic_screenshot'):artifacts.append(body['diagnostic_screenshot'])
    artifacts.extend(body.get('output_paths',[]))
    item = {'schema':2,'task_id':task['task_id'],'check_id':check_id,'type':check['type'],
            'recorded_at':time.time(),'source_hashes':hashes(root, task,include_runtime=check['type']!='command'),**body}
    item['artifact_hashes'] = {name:sha(local(root,name)) for name in artifacts}
    relative = f'work/frontend-policy/evidence/{task["task_id"]}/{check_id}.json'
    save(local(root, relative, False), item)
    task['evidence'][check_id] = relative
    save(Path(root) / TASK_PATH, task)
    return item

def seal_execution(root, task, item, runner, process_id):
    """Receipt registry is outside project evidence. Not an OS security boundary."""
    receipt_id = uuid.uuid4().hex
    receipt = {'schema':1,'id':receipt_id,'root':str(Path(root).resolve()),'task_id':task['task_id'],
               'check_id':item['check_id'],'record_hash':hashlib.sha256(json.dumps(item,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
               'policy_hash':policy_hash(),'contract_hash':contract_hash(task),'runner':runner,'process_id':process_id,'time':time.time()}
    save(CENTER / 'receipts' / (receipt_id+'.json'),receipt)
    item['execution_receipt'] = receipt_id
    save(local(root,task['evidence'][item['check_id']]),item)
    return item

def execution_valid(root, task, item, expected_runner):
    identifier = item.get('execution_receipt','')
    if not re.fullmatch(r'[0-9a-f]{32}',identifier):
        return False
    receipt = load(CENTER / 'receipts' / (identifier+'.json'))
    body = {key:value for key,value in item.items() if key!='execution_receipt'}
    return (receipt.get('root')==str(Path(root).resolve()) and receipt.get('task_id')==task['task_id'] and
            receipt.get('check_id')==item['check_id'] and receipt.get('policy_hash')==policy_hash() and
            receipt.get('contract_hash')==contract_hash(task) and receipt.get('runner')==expected_runner and receipt.get('record_hash')==hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False).encode()).hexdigest())

def contract_hash(task):
    fields=('task_id','level','profile','phase','files','scope','checks','review_criteria','interactive','visual','summary','rule_application','original_rules_sha256','selection_evidence','style_summary','asset_plan','implementation_checklist','component_libraries','space_effects','project_requirements','assets','references','reference_gallery','baseline','visual_reason','design_plan','deployment')
    return hashlib.sha256(json.dumps({**{key:task.get(key) for key in fields},'checklist_plan':task.get('checklist_plan'),'design_document':task.get('design_document'),'style_discovery':task.get('style_discovery'),'style_contract':task.get('style_contract'),'selected_reference':task.get('selected_reference'),'reference_kind':task.get('reference_kind','image')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def run_check(root, check_id, command):
    task = load(Path(root) / TASK_PATH)
    check = next(item for item in task['checks'] if item['id'] == check_id)
    if check['type'] != 'command' or not command:
        raise ValueError('run needs a planned command check and an argument vector after --')
    task['evidence'].pop(check_id,None)
    save(Path(root) / TASK_PATH,task)
    started = time.time()
    initial_hashes=hashes(root,task,include_runtime=False)
    initial_contract=contract_hash(task)
    process = subprocess.Popen(command, cwd=root, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False)
    try:
        stdout,stderr=process.communicate(timeout=300)
    except BaseException:
        process.kill();process.communicate();raise
    log_path = f'work/frontend-policy/evidence/{task["task_id"]}/{check_id}.log'
    path = local(root, log_path, False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('STDOUT\n' + stdout + '\nSTDERR\n' + stderr, encoding='utf-8')
    current_task=load(Path(root)/TASK_PATH)
    if hashes(root,current_task,include_runtime=False)!=initial_hashes or contract_hash(current_task)!=initial_contract:
        raise ValueError('Sources or task contract changed during the command; rerun the check against the resulting revision')
    item=record(root, task, check_id, {'status':'PASS' if process.returncode == 0 else 'FAIL','command':command,
                  'exit_code':process.returncode,'started_at':started,'log':log_path,'log_sha256':sha(path),'output_paths':check.get('outputs',[]) if process.returncode==0 else []})
    return seal_execution(root,task,item,'command-process',process.pid)

def run_browser(root, spec_path):
    task=load(Path(root)/TASK_PATH)
    deployment=task.get('deployment',{})
    if deployment.get('mode')=='build':
        build_id=deployment.get('check_id')
        build=next((item for item in task['checks'] if item['id']==build_id and item['type']=='command'),None)
        if not build or not build.get('outputs'):raise ValueError('Built UI needs a declared build command and its real output files')
        evidence=load(local(root,task['evidence'][build_id]))
        if not execution_valid(root,task,evidence,'command-process') or evidence.get('exit_code')!=0 or evidence.get('source_hashes')!=hashes(root,task,include_runtime=False):raise ValueError('Build execution is missing or stale for current application sources')
        if any(evidence.get('artifact_hashes',{}).get(name)!=sha(local(root,name)) for name in build['outputs']):raise ValueError('Build outputs changed after the actual build execution')
    elif not any(Path(name).suffix.lower() in ('.html','.htm') for name in task['files']):
        raise ValueError('Declare a source-bound build and its output files for a compiled UI; a screenshot cannot bind a deployed bundle to current sources')
    check=next(item for item in task['checks'] if item['type']=='browser' and item.get('required'))
    task['evidence'].pop(check['id'],None);save(Path(root)/TASK_PATH,task)
    spec=local(root,spec_path)
    output=f'work/frontend-policy/evidence/{task["task_id"]}/browser-execution.json'
    command=[shutil.which('node') or 'node',str(CODE_DIR/'browser-run.cjs'),str(Path(root).resolve()),str(spec),str(local(root,output,False))]
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace')
    try:
        stdout,stderr=process.communicate(timeout=180)
    except BaseException:
        process.kill();process.communicate();raise
    if process.returncode:
        diagnostic=load(local(root,output)).get('diagnostic_screenshot') if local(root,output,False).is_file() else None
        item=record(root,task,check['id'],{'status':'FAIL','runner_error':stderr[-4000:] or stdout[-4000:],'captures':[],'diagnostic_screenshot':diagnostic})
    else:
        report=load(local(root,output))
        task=load(Path(root)/TASK_PATH)
        data=browser_findings(root,task,report['captures'])
        item=record(root,task,check['id'],{'status':'FAIL' if data['findings'] else 'BLOCKED' if data['blockers'] else 'PASS',
                    'captures':report['captures'],'assertions':report['assertions'],'execution_report':output})
    return seal_execution(root,task,item,'fixed-browser-process',process.pid)

class Node:
    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs or []), parent, []
    def text(self):
        if self.tag in ('script','style','template','noscript','svg') or 'hidden' in self.attrs:
            return ''
        return ''.join(child.text() if isinstance(child, Node) else child for child in self.children)
    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

class Tree(HTMLParser):
    void = {'input','img','br','hr','meta','link','source','wbr','area','base','embed','track'}
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node('root')
        self.stack = [self.root]
        self.feed(html)
    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag == 'br':
            node.children.append(' ')
        if tag not in self.void:
            self.stack.append(node)
    def handle_endtag(self, tag):
        for index in range(len(self.stack)-1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                break
    def handle_data(self, text):
        self.stack[-1].children.append(text)

def copy_units(html):
    nodes = list(Tree(html).root.walk())
    def visible(node):
        while node:
            if node.tag in ('script','style','template','noscript','svg') or 'hidden' in node.attrs:
                return False
            node = node.parent
        return True
    nodes = [node for node in nodes if visible(node)]
    primary = {'p','h1','h2','h3','h4','h5','h6','label','legend','figcaption','td','th','dt','dd','output','summary','caption','blockquote','pre','address'}
    def has_ancestor(node, tags):
        node = node.parent
        while node:
            if node.tag in tags or 'data-copy-unit' in node.attrs:
                return True
            node = node.parent
        return False
    units = []
    for node in nodes:
        descendants = list(node.walk())[1:]
        chosen = node.tag in primary or 'data-copy-unit' in node.attrs
        if node.tag in ('button','a','li') and not any(child.tag in primary for child in descendants):
            chosen = True
        if node.tag not in ('root','script','style','template','noscript','svg','input','textarea','select') and not any(child.tag in primary | {'button','a','li','div','section','article','main','header','footer','nav','form','input'} for child in descendants):
            chosen = True
        if chosen and node.text().strip() and not has_ancestor(node, primary):
            units.append({'selector':node.attrs.get('id') or node.tag,'text':node.text()})
        if node.attrs.get('placeholder'):
            units.append({'selector':node.attrs.get('id') or 'placeholder','text':node.attrs['placeholder']})
        if node.tag=='input' and node.attrs.get('type') in ('submit','button','reset') and node.attrs.get('value'):
            units.append({'selector':node.attrs.get('id') or 'input-action','text':node.attrs['value']})
    checkbox_ids = {node.attrs['id'] for node in nodes if node.tag == 'input' and node.attrs.get('type') == 'checkbox' and node.attrs.get('id')}
    for label in (node for node in nodes if node.tag == 'label' and node.attrs.get('for') in checkbox_ids):
        parent = label.parent
        if parent and parent.tag in ('div','span','p','label'):
            descendants = list(parent.walk())
            unrelated = any(node.tag in ('input','textarea','select') and node.attrs.get('type') != 'checkbox' for node in descendants)
            if not unrelated and any(node.tag in ('button','a') for node in descendants):
                units.append({'selector':parent.attrs.get('id') or 'checkbox-sentence','text':parent.text()})
    # Inline containers remain one sentence even when spans are labelled as units.
    for node in nodes:
        if node.tag not in ('div','section','span'):continue
        descendants=list(node.walk())[1:]
        if descendants and not any(child.tag in primary|{'div','section','article','ul','ol','li','input','textarea','select'} for child in descendants):
            if node.text().strip():units.append({'selector':node.attrs.get('id') or node.tag,'text':node.text()})
    return units

def text_findings(html, limit):
    findings = []
    for unit in copy_units(html):
        if re.search(r'lorem\s+ipsum',unit['text'],re.I):findings.append('placeholder copy '+unit['selector'])
        for sentence in re.split(r'[。！？!?]+|\.(?=\s|$)', unit['text']):
            count = sum(unicodedata.category(char)[0] in ('L','N') for char in sentence)
            if limit is not None and count > limit:
                findings.append(f'copy_length {unit["selector"]}: {count}>{limit}: {sentence.strip()[:100]}')
    return findings

def component_findings(root,task,required=False):
    """Validate required records only. This cannot authenticate a Context7 query."""
    gaps=[];plan=task.get('component_libraries',{})
    if not required and plan.get('decision','pending')=='pending':return gaps
    if plan.get('decision') not in ('used','none') or not str(plan.get('reason','')).strip():
        return ['Component-library selection and concrete reason missing']
    items=plan.get('items',[])
    primary_required=required and task.get('visual') and task.get('phase')=='implementation' and task.get('level')!='L1'
    if primary_required and plan.get('decision')=='none':gaps.append('A primary UI library from the user list is required; native HTML or no suitable library is not an exemption')
    primary=[]
    if plan['decision']=='used' and not items:gaps.append('Used component libraries need actual version/docs/usage records')
    if plan['decision']=='none' and items:gaps.append('Component-library decision conflicts with registered libraries')
    for item in items:
        if primary_required and item.get('role')=='primary_ui':
            allowed=('StyleKit','Magic UI','Aceternity UI','DaisyUI','Brutalist UI','Glass UI','Radix UI','Mantine')
            normalize=lambda value:re.sub(r'[\s_-]','',value).lower()
            canonical=next((name for name in allowed if normalize(name)==normalize(str(item.get('name','')))),None)
            if canonical is None:gaps.append('Primary UI library is outside the user list; helpers do not qualify')
            else:
                primary.append(item)
                modules=item.get('imports',[])
                families={'Mantine':('@mantine/',),'Radix UI':('@radix-ui/','radix-ui'),'DaisyUI':('daisyui',)}
                if canonical in families:
                    if not any(module.startswith(families[canonical]) for module in modules):gaps.append('Library identity does not match declared imports: '+canonical)
                else:
                    if item.get('distribution')!='vendored':gaps.append('Registry/copied UI components need their actual vendored source record')
                    try:local(root,item.get('source_evidence'))
                    except ValueError as exc:gaps.append(str(exc))
                if not item.get('render_checks'):gaps.append('Primary UI library needs actual page component render checks')
        if not all(str(item.get(key,'')).strip() for key in ('name','version','customization')):gaps.append('Library name/version/customization missing')
        if str(item.get('version','')).lower() in ('latest','unknown','default','current'):gaps.append('Library record needs an actual version or source revision')
        if item.get('docs_provider') not in ('context7','official'):gaps.append('Library docs must use Context7 or explicit official fallback')
        if item.get('name')!='StyleKit' and item.get('docs_provider')=='official' and not str(item.get('context7_limitation','')).strip():gaps.append('Official docs fallback needs the actual Context7 limitation')
        try:
            local(root,item.get('docs_evidence'))
            if not item.get('usage'):gaps.append('Library actual usage locations missing')
            sources='\n'.join(local(root,name).read_text(encoding='utf-8-sig') for name in item.get('usage',[]))
            sources=re.sub(r'/\*.*?\*/|(?m:^\s*//[^\n]*)','',sources,flags=re.S)
            imports=item.get('imports',[])
            vendored_stylekit=False
            if item.get('name')=='StyleKit' and item.get('distribution')=='vendored':
                acquisition=load(local(root,item.get('source_evidence')))
                bindings=acquisition.get('files',[])
                bound_paths={binding.get('path') for binding in bindings}
                render_paths={check.get('implementation') for check in item.get('render_checks',[])}
                vendored_stylekit=bool(acquisition.get('source_url') and acquisition.get('asset_id') and bindings and bound_paths==set(item['usage']) and render_paths<=bound_paths and all(sha(local(root,binding['path']))==binding.get('sha256') for binding in bindings))
                if not vendored_stylekit:gaps.append('StyleKit source record needs actual asset identity and current vendored file hashes')
            has_import=bool(imports) and any(re.search(r'''(?:\bfrom\s*|\bimport\s*(?:\(\s*)?|@plugin\s*|\brequire\s*\(\s*|\b(?:src|href)\s*=\s*)["']'''+re.escape(module)+r'''["']''',sources) for module in imports)
            if not has_import and not vendored_stylekit:
                gaps.append('No declared library import/use found in registered implementation files')
        except ValueError as exc:gaps.append(str(exc))
    if primary_required and not primary:gaps.append('No qualifying primary UI library; a dialog/icon/animation helper cannot replace it')
    if primary_required and primary and task.get('level')=='L3':
        components=[str(check.get('component','')) for item in primary for check in item.get('render_checks',[])]
        if components and all(re.search(r'dialog|modal|tooltip|popover|icon|animation|弹层|弹窗|图标',name,re.I) for name in components):
            gaps.append('Full-page UI adoption cannot consist only of overlays/icons/animation components')
    return gaps

def component_render_findings(task,browser_result,required=False):
    if not required:return []
    gaps=[];actual=(browser_result or {}).get('assertions',[])
    for library in task.get('component_libraries',{}).get('items',[]):
        if library.get('role')!='primary_ui':continue
        for check in library.get('render_checks',[]):
            if not check.get('component') or check.get('implementation') not in library.get('usage',[]):gaps.append('UI render evidence must identify its component and implementation file')
            if not check.get('selector') or not any(all(result.get(key)==check.get(key) for key in ('page','width','state')) and any(step.get('selector')==check['selector'] and step.get('action')=='expect_visible' for step in result.get('checks',[])) for result in actual):
                gaps.append('Primary UI component lacks the matching executed browser assertion')
    return gaps

def project_findings(root,task,browser_result):
    gaps=[];requirements=task.get('project_requirements',[])
    if task.get('level')=='L3' and task.get('phase')=='implementation' and not requirements:gaps.append('Project-specific requirements missing; global rules do not replace the actual brief')
    seen=set()
    for item in requirements:
        identifier=item.get('id','')
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,60}',identifier) or identifier in seen:gaps.append('Project requirement ID missing/duplicate')
        seen.add(identifier)
        if not item.get('expected') or not item.get('implementation'):gaps.append('Project requirement needs its concrete expected condition and implementation')
        local(root,item.get('source'))
        for name in item.get('implementation',[]):local(root,name)
        verification=item.get('verification',{})
        if verification.get('mode')=='visual_review':
            if not task.get('visual'):gaps.append('Project visual requirements need actual visual review scope')
        elif verification.get('mode')=='browser':
            assertion=verification.get('assertion',{})
            if not str(assertion.get('action','')).startswith('expect_') or not assertion.get('selector'):gaps.append('Project requirement needs a real expected-result assertion')
            if not any(all(result.get(key)==verification.get(key) for key in ('page','width','state')) and any(all(step.get(key)==value for key,value in assertion.items()) for step in result.get('checks',[])) for result in (browser_result or {}).get('assertions',[])):
                gaps.append('Project requirement has no matching executed assertion: '+identifier)
        else:gaps.append('Project requirement verification mode missing: '+identifier)
    return gaps

def spatial_findings(root,task,browser_result=None,required=False):
    failures,gaps=[],[]
    for kind in ('shader','model'):
        item=task.get('space_effects',{}).get(kind,{})
        if not required and item.get('decision','pending')=='pending':continue
        if item.get('decision') not in ('used','omitted') or not str(item.get('reason','')).strip():
            gaps.append(kind+': record whether to use it and why');continue
        if item['decision']=='omitted':continue
        for field in ('usage','render_check'):
            if not item.get(field):gaps.append(kind+': missing '+field)
        for name in item.get('usage',[]):local(root,name)
        if kind=='model':
            if item.get('origin','generated')=='generated':
                if item.get('generator')!='tripo':failures.append('Generated 3D models must use the selected Tripo workflow')
                local(root,item.get('generation_evidence'))
            elif item.get('origin') not in ('existing','user_provided'):failures.append('Unknown model origin')
            path=local(root,item.get('path'))
            if image_artifact(path):failures.append('A raster image cannot count as a generated 3D model')
            if path.suffix.lower()=='.glb' and path.read_bytes()[:4]!=b'glTF':failures.append('Invalid GLB model file')
            if not browser_result or browser_result.get('media_hashes',{}).get(item.get('url'))!=sha(path):gaps.append('Actual loaded model bytes not demonstrated')
        check=item.get('render_check',{})
        actual=(browser_result or {}).get('assertions',[])
        if not any(all(result.get(key)==check.get(key) for key in ('page','width','state')) and any(step.get('selector')==check.get('selector') and step.get('action')=='expect_visible' for step in result.get('checks',[])) for result in actual):
            gaps.append(kind+': fixed browser must execute the declared visible-render assertion')
    return failures,gaps

def asset_findings(root,task,browser_result,require_content=True):
    failures,gaps=[],[]
    roles={'main_visual','scene_illustration','character','object_cutout','state_illustration','editorial_image','ornament'}
    assets=task.get('assets',[])
    candidates=[item for item in assets if item.get('origin')=='builtin_image' and item.get('role') in roles]
    if require_content and not candidates:gaps.append('Generated non-background content assets missing')
    references={sha(local(root,item['path'])) for item in task.get('references',[])}
    if task.get('selected_reference') and task.get('reference_kind','image')=='image':
        references.add(sha(local(root,task['selected_reference'])))
    for item in assets:
        if item.get('origin') not in ('builtin_image','user_provided','existing'):failures.append('Unsupported generated-image origin; use built-in Image')
    for asset in candidates:
        path=local(root,asset['path'])
        if not image_artifact(path):failures.append('Invalid image asset: '+asset['path'])
        if sha(path) in references:failures.append('Style-reference image cannot count as a production content asset')
        local(root,asset.get('generation_evidence'))
        if not asset.get('purpose') or not asset.get('usage'):gaps.append('Asset purpose and actual code usage locations required: '+asset['path'])
        for name in asset.get('usage',[]):local(root,name)
        if not browser_result or asset.get('url') not in browser_result.get('image_urls',[]):gaps.append('Asset usage not demonstrated: '+asset['path'])
        if not browser_result or browser_result.get('media_hashes',{}).get(asset.get('url'))!=sha(path):gaps.append('Loaded image bytes do not match registered asset: '+asset['path'])
    for planned in task.get('design_plan',{}).get('asset_coverage',[]):
        if planned.get('decision')!='generate':continue
        matching=[asset for asset in candidates if asset.get('id')==planned.get('id') and asset.get('role')==planned.get('role')]
        if len(matching)!=1:
            gaps.append('Planned generated asset lacks a unique actual file/role binding: '+str(planned.get('id')));continue
        asset=matching[0];check=asset.get('render_check',{})
        if check.get('page')!=planned.get('page') or check.get('selector')!=planned.get('selector') or not any(all(view.get(key)==check.get(key) for key in ('page','width','state')) for view in task.get('scope',[])):
            gaps.append('Asset render_check differs from planned placement or declared scope: '+str(planned.get('id')));continue
        if not any(all(image.get(key)==check.get(key) for key in ('page','width','state')) and check.get('selector') in image.get('selectors',[]) and image.get('url')==asset.get('url') for image in (browser_result or {}).get('rendered_images',[])):
            gaps.append('Planned asset is not visibly rendered at its declared image selector: '+str(planned.get('id')))
    return failures,gaps

def surface_review_gaps(task,observation):
    """Check comparison coverage only; the reviewer must judge actual fidelity."""
    if task.get('level')!='L3':return []
    comparisons=observation.get('surface_comparisons',[])
    expected={item.get('selector') for item in task.get('design_plan',{}).get('visual_surfaces',[])}
    covered={item.get('selector') for item in comparisons if all(item.get(key) for key in ('selector','expected','observed','deviation','decision'))}
    return ['reference_fidelity: compare expected/observed color and material, deviation and repair/adaptation for '+str(selector) for selector in sorted(expected-covered)]

def source_findings(root, task):
    findings = []
    profile = active_rules(task)
    for name in task['files']:
        path = local(root, name)
        text = path.read_text(encoding='utf-8-sig')
        text=re.sub(r'<!--.*?-->|/\*.*?\*/','',text,flags=re.S)
        copy_issues=text_findings(text,profile['copy_limit']) if path.suffix=='.html' else []
        if task['level'] != 'L3' and name in task.get('baseline', {}):
            before = local(root, task['baseline'][name]).read_text(encoding='utf-8')
            before=re.sub(r'<!--.*?-->|/\*.*?\*/','',before,flags=re.S)
            old_copy=text_findings(before,profile['copy_limit']) if path.suffix=='.html' else []
            copy_issues=[issue for issue in copy_issues if issue not in old_copy]
            text = '\n'.join(line[1:] for line in difflib.unified_diff(before.splitlines(), text.splitlines()) if line.startswith('+') and not line.startswith('+++'))
        findings.extend(name+': '+issue for issue in copy_issues)
        if path.suffix.lower() in SOURCE_EXT:
            findings.extend(name+': '+issue for issue in typography.source_findings(text))
        if re.search(r'lorem\s+ipsum', text, re.I):
            findings.append(name + ': placeholder copy')
        for color in profile['forbidden_hex']:
            if color.lower() in text.lower():
                findings.append(name + ': forbidden color ' + color)
        if forbidden_hue(text):findings.append(name+': forbidden purple/indigo color candidate')
        if re.search(r'(?:transition|animation|easing|ease)[^;\n]{0,160}(?:ease-in-out|\blinear\b(?!-))',text,re.I):findings.append(name+': forbidden easing candidate')
        if profile['default_palette'] and re.search(r'\b(?:bg|text|border|from|via|to|ring|fill|stroke)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b', text):
            findings.append(name + ': default palette token candidate')
    return findings

def browser_findings(root, task, paths):
    problems, gaps, seen, screenshots, image_urls, media_hashes = [], [], set(), [], set(), {}
    rendered_images=[]
    current = hashes(root, task)
    core_files=task.get('files',[])+[item['path'] for item in task.get('assets',[])]
    latest = max((local(root, name).stat().st_mtime for name in core_files), default=0)
    profile = active_rules(task)
    for name in paths:
        path = local(root, name)
        snapshot = load(path)
        if snapshot.get('schema') != 'frontend-policy/browser-v1' or not snapshot.get('url'):
            raise ValueError('Current real-browser snapshot format required')
        screenshot = local(root, snapshot.get('screenshot'))
        if screenshot.read_bytes()[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError('A real PNG screenshot artifact is required')
        if snapshot.get('source_hashes') != current or min(path.stat().st_mtime, screenshot.stat().st_mtime) < latest:
            gaps.append('stale browser evidence: ' + name)
        if not snapshot.get('html') or not snapshot.get('styles'):
            raise ValueError('Rendered DOM and computed styles required')
        page, width, state = snapshot['page'], snapshot['viewport']['width'], snapshot['state']
        seen.add((page, width, state))
        if snapshot.get('horizontal_overflow'):
            problems.append('horizontal overflow: ' + name)
        problems.extend(text_findings(snapshot['html'], profile['copy_limit']))
        for shadow in snapshot.get('shadow_html', []):
            problems.extend(text_findings(shadow['html'],profile['copy_limit']))
        styles = json.dumps(snapshot['styles']).lower()
        if forbidden_hue(styles):problems.append('rendered purple/indigo color candidate')
        for color in profile['forbidden_hex']:
            rgb = ', '.join(str(int(color[index:index+2],16)) for index in (1,3,5))
            if color in styles or 'rgb(' + rgb + ')' in styles:
                problems.append('rendered forbidden color: ' + color)
        candidates,unverified=quality_checks.rendered_candidates(snapshot)
        problems.extend(candidates);gaps.extend(unverified)
        font_failures,font_gaps=typography.findings(snapshot)
        problems.extend(font_failures);gaps.extend(font_gaps)
        for pseudo in snapshot.get('generated_text',[]):
            problems.extend(text_findings('<p>'+__import__('html').escape(pseudo['text'])+'</p>',profile['copy_limit']))
        for animation in snapshot.get('animations', []):
            if quality_checks.forbidden_easing(animation.get('easing')):
                problems.append('rendered forbidden easing: ' + animation['easing'])
        for icon in snapshot.get('functional_icons',[]):
            if re.search('[\U0001F300-\U0001FAFF\u2600-\u27BF]',str(icon)):problems.append('functional Emoji icon')
        for resource in snapshot.get('resources', []):
            if resource['url'] not in task['runtime_sources']:
                gaps.append('unmapped runtime source: ' + resource['url'])
        screenshots.append(snapshot['screenshot'])
        visible_images=[image for image in snapshot.get('images', []) if image.get('loaded') and image.get('visible') is True and image.get('effective_opacity',0)>0 and image.get('width',0)>0 and image.get('height',0)>0]
        image_urls.update(image['url'] for image in visible_images)
        rendered_images.extend({**image,'page':page,'width':width,'state':state} for image in visible_images)
        for item in snapshot.get('media_responses',[]):
            if item['url'] in media_hashes and media_hashes[item['url']]!=item['sha256']:gaps.append('Media changed between captured states: '+item['url'])
            media_hashes[item['url']]=item['sha256']
    for view in task['scope']:
        if (view['page'],view['width'],view['state']) not in seen:
            gaps.append('missing browser scope: ' + json.dumps(view))
    return {'findings':problems,'blockers':gaps,'screenshots':screenshots,'image_urls':sorted(image_urls),'media_hashes':media_hashes,'rendered_images':rendered_images,'captures':paths}

def verify(root, task=None, *, include_delivery_review=True, _defer_completion=False):
    root = Path(root).resolve()
    task_from_disk = task is None
    failed, blocked, automated, attestations = [], [], [], []
    separate_model_review='NOT_REQUIRED_OR_MISSING'
    auto_failed,auto_blocked=[],[]
    try:
        task = task if task is not None else load(root / TASK_PATH)
        if not isinstance(task,dict):
            raise ValueError('Task plan must be a JSON object')
        if task.get('schema') != 2 or task.get('level') not in ('L1','L2','L3') or task.get('phase') not in ('implementation','reference'):
            raise ValueError('Current task schema/level required')
        blocked.extend(initialization_gaps(root,task))
        if task.get('policy_hash') != policy_hash():
            blocked.append('Policy changed; reread and re-plan applicable requirements')
        catalog=validate_rule_binding()
        if task.get('original_rules_sha256')!=sha(original_rules()):blocked.append('Original rules snapshot missing or changed; hash binding does not prove reading')
        applications={item['id']:item for item in task.get('rule_application',[])}
        if len(applications)!=len(task.get('rule_application',[])):blocked.append('Duplicate rule applicability entries')
        for requirement in catalog:
            application=applications.get(requirement['id'],{})
            if task['phase'] != 'reference' and (application.get('applicability') not in ('applicable','out_of_scope','conditional') or not str(application.get('reason','')).strip()):
                blocked.append('Rule applicability not established: '+requirement['id'])
        routes={item['id']:item for item in load(SKILL/'references/original-rule-map.json')['rules']}
        for identifier,application in applications.items():
            if identifier not in routes:blocked.append('Unknown rule applicability entry: '+identifier)
            elif application.get('applicability')=='conditional' and not routes[identifier].get('conditional_allowed'):
                blocked.append('Mandatory source clause cannot become conditional: '+identifier)
        if task['phase'] != 'reference' and any(item.get('applicability')=='applicable' and routes.get(item['id'],{}).get('method')=='visual_review' for item in applications.values()):
            if not task.get('visual') or not any(item.get('required') and item.get('type')=='review' for item in task.get('checks',[])):
                blocked.append('Applicable visual requirements need browser/review scope, including L1')
        active_rules(task)
        component_required=task['phase']=='implementation' and (task['level']=='L3' or any(applications.get(item['id'],{}).get('applicability')=='applicable' and ('Context7' in item['text'] or '组件库' in item['text']) for item in catalog))
        blocked.extend(component_findings(root,task,required=component_required))
        if task['level']=='L3' and task['phase']=='implementation':
            for field in ('selection_evidence','style_summary','asset_plan','implementation_checklist'):
                try:local(root,task.get(field))
                except ValueError:blocked.append('Original workflow evidence missing: '+field)
        planning=preflight_check(root,task)
        blocked.extend(planning.get('blockers',[]))
        blocked.extend(preflight.receipt_gaps(SimpleNamespace(**globals()),root,task))
        current = hashes(root, task)
        if task['phase'] == 'implementation' and not task.get('files'):
            blocked.append('Declare the actual changed source files')
        if task['level'] == 'L3' and task['phase'] == 'implementation' and not task.get('visual'):
            blocked.append('L3 interface work requires visual verification; use L2 for nonvisual utilities')
        checks = task.get('checks', [])
        types = {item['type'] for item in checks if item.get('required')}
        if len({item['id'] for item in checks}) != len(checks):
            blocked.append('Duplicate check identifiers')
        if task['phase'] == 'implementation' and 'source' not in types:
            blocked.append('Required source check removed')
        if task['phase'] == 'reference' and 'references' not in types:
            blocked.append('Four actual reference image files are required')
        if task.get('visual') and task['phase'] == 'implementation' and not {'browser','review'}.issubset(types):
            blocked.append('Required browser/visual checks removed')
        if task['level'] in ('L2','L3') and task['phase'] == 'implementation' and discover(root)['check_candidates'] and 'command' not in types:
            blocked.append('Available project checks require command evidence')
        if task['level'] in ('L2','L3') and task['phase'] == 'implementation' and not task.get('visual') and 'command' not in types:
            blocked.append('Nonvisual component/utility work requires a relevant automated check')
        if task['level'] == 'L3' and task['phase'] == 'implementation' and 'assets' not in types:
            blocked.append('L3 requires asset evidence under the original rules')
        if not task.get('visual') and task['level'] != 'L1' and not task.get('visual_reason'):
            blocked.append('Nonvisual scope needs a concrete reason')
        auto_failed=list(failed);auto_blocked=list(blocked)
        browser_result = None
        for check in sorted(checks,key=lambda check:{'source':0,'references':0,'command':1,'browser':2,'assets':3,'review':4}.get(check.get('type'),5)):
            if not check.get('required'):
                if not check.get('reason'):
                    blocked.append(check['id'] + ': skipped check has no scope reason')
                continue
            identifier, kind = check['id'], check['type']
            before_failed,before_blocked=len(failed),len(blocked)
            try:
                if kind == 'source':
                    failed.extend(source_findings(root, task))
                    automated.append(identifier)
                    continue
                if kind == 'references':
                    refs = task.get('references', [])
                    if len(refs) != 4 or {ref.get('id') for ref in refs} != set('ABCD') or len({sha(local(root,ref['path'])) for ref in refs}) != 4:
                        blocked.append('Four distinct A/B/C/D reference files required')
                    for ref in refs:
                        if not image_artifact(local(root,ref['path'])):
                            blocked.append('Reference is not an image artifact: '+ref['path'])
                    if task.get('reference_gallery'):local(root, task['reference_gallery'])
                    attestations.append('reference-style-differences')
                    continue
                if kind == 'assets':
                    if browser_result is None:
                        browser_check = next((item for item in checks if item['type']=='browser'),None)
                        if browser_check:
                            rec = load(local(root, task['evidence'][browser_check['id']]))
                            browser_result = browser_findings(root,task,rec['captures'])
                    asset_failed,asset_blocked=asset_findings(root,task,browser_result)
                    failed.extend(asset_failed);blocked.extend(asset_blocked)
                    attestations.append('asset-origin-and-art-direction')
                    continue
                rec_path = local(root, task['evidence'][identifier])
                rec = load(rec_path)
                expected_hashes=hashes(root,task,include_runtime=False) if kind=='command' else current
                if rec.get('task_id') != task['task_id'] or rec.get('source_hashes') != expected_hashes or rec.get('type') != kind:
                    blocked.append(identifier + ': stale or mismatched evidence')
                    continue
                if any(sha(local(root,name)) != value for name,value in rec.get('artifact_hashes',{}).items()):
                    blocked.append(identifier + ': registered evidence artifact changed')
                    continue
                if kind == 'command':
                    if not execution_valid(root,task,rec,'command-process'):
                        blocked.append(identifier+': no valid process execution receipt');continue
                    log = local(root,rec['log'])
                    if sha(log) != rec.get('log_sha256') or not rec.get('command'):
                        blocked.append(identifier + ': command log missing/changed')
                    elif rec.get('exit_code') != 0:
                        failed.append(identifier + ': command failed')
                    else:
                        automated.append(identifier)
                elif kind == 'browser':
                    if not execution_valid(root,task,rec,'fixed-browser-process'):
                        blocked.append(identifier+': imported/self-written browser evidence is not an executed browser check');continue
                    if rec.get('runner_error'):
                        failed.append(identifier+': '+rec['runner_error']);continue
                    browser_result = browser_findings(root,task,rec['captures'])
                    browser_result['assertions']=rec.get('assertions',[])
                    failed.extend(browser_result['findings'])
                    blocked.extend(browser_result['blockers'])
                    automated.append(identifier)
                elif kind == 'review':
                    observations = rec.get('observations', [])
                    if not observations:
                        blocked.append(identifier + ': actual visual observations required')
                    minimum = set(review_criteria(task['level'],task['profile'],task['phase'],task.get('interactive')))
                    expected_criteria = set(task.get('review_criteria',[])) | minimum
                    expected_criteria.update('project:'+item['id'] for item in task.get('project_requirements',[]) if item.get('verification',{}).get('mode')=='visual_review')
                    routes={item['id']:item for item in load(SKILL/'references/original-rule-map.json')['rules']}
                    for requirement in catalog:
                        if applications.get(requirement['id'],{}).get('applicability')=='applicable' and routes[requirement['id']]['method']=='visual_review':
                            expected_criteria.add('rule:'+requirement['id'])
                    present = {item.get('criterion') for item in observations}
                    for criterion in sorted(expected_criteria-present):
                        blocked.append(identifier + ': missing applicable review criterion '+criterion)
                    if task.get('visual') and task['phase']=='implementation' and browser_result is None:
                        browser_check = next((item for item in checks if item['type']=='browser'),None)
                        if browser_check:
                            browser_rec = load(local(root,task['evidence'][browser_check['id']]))
                            browser_result = browser_findings(root,task,browser_rec['captures'])
                    signatures = set()
                    for observation in observations:
                        if not all(observation.get(key) for key in ('criterion','location','observed','evidence')):
                            blocked.append(identifier + ': incomplete observation')
                        for name in observation.get('evidence', []):
                            local(root,name)
                        signature = (observation.get('location'),observation.get('observed'))
                        if signature in signatures or str(observation.get('observed','')).strip().lower() in {'已验证','通过','符合','正常','looks good','passed','ok'}:
                            blocked.append(identifier + ': generic or duplicated observation')
                        signatures.add(signature)
                        if observation.get('criterion')=='reference_fidelity':
                            blocked.extend(surface_review_gaps(task,observation))
                            reference=observation.get('reference_file')
                            try:
                                path=local(root,reference)
                                if not task.get('selected_reference') or reference!=task['selected_reference']:blocked.append(identifier+': register and compare the actual selected_reference')
                                if task.get('reference_kind','image')=='text':
                                    if task.get('design_plan',{}).get('selected_style')!='user_custom' or not path.read_text(encoding='utf-8-sig').strip():blocked.append(identifier+': text reference requires the actual user_custom direction')
                                elif not image_artifact(path):blocked.append(identifier+': reference_fidelity needs the actual selected reference image')
                            except (OSError,ValueError,TypeError):blocked.append(identifier+': reference_fidelity needs the actual selected reference image')
                        if observation.get('criterion')=='copy_necessity':
                            decisions=observation.get('copy_decisions',[])
                            if not decisions or any(not all(item.get(key) for key in ('text','location','purpose','decision','reason')) or item.get('decision') not in ('keep','removed') for item in decisions):
                                blocked.append(identifier+': copy_necessity needs actual text, location, purpose and keep/removal decisions')
                        if str(observation.get('criterion','')).startswith(('rule:','project:')):
                            if not observation.get('condition') or not observation.get('implementation'):
                                blocked.append(identifier+': rule observation needs its actual implementation and pass condition')
                            for name in observation.get('implementation',[]):local(root,name)
                        if task.get('visual') and task['phase']=='implementation' and (not browser_result or not any(name in browser_result['screenshots'] for name in observation.get('evidence', []))):
                            blocked.append(identifier + ': visual finding needs a current captured screenshot')
                        if observation.get('status') == 'FAIL':
                            failed.append(identifier + ': ' + observation['criterion'])
                        elif observation.get('status') != 'PASS':
                            blocked.append(identifier + ': unverified visual criterion')
                    attestations.append(identifier)
                else:
                    blocked.append('Unsupported check type: ' + kind)
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                blocked.append(identifier + ': ' + str(exc))
            finally:
                if kind!='review':
                    auto_failed.extend(failed[before_failed:]);auto_blocked.extend(blocked[before_blocked:])
        space_failed,space_blocked=spatial_findings(root,task,browser_result,required=task['level']=='L3' and task['phase']=='implementation')
        failed.extend(space_failed);blocked.extend(space_blocked)
        auto_failed.extend(space_failed);auto_blocked.extend(space_blocked)
        component_gaps=component_render_findings(task,browser_result,required=component_required and task.get('visual') and task['phase']=='implementation')
        blocked.extend(component_gaps);auto_blocked.extend(component_gaps)
        project_gaps=project_findings(root,task,browser_result)
        blocked.extend(project_gaps);auto_blocked.extend(project_gaps)
        dynamic_gaps=preflight.dynamic_execution_gaps(task,browser_result)
        blocked.extend(dynamic_gaps);auto_blocked.extend(dynamic_gaps)
        if task.get('assets') and 'assets' not in types and task['phase']=='implementation':
            asset_failed,asset_blocked=asset_findings(root,task,browser_result,require_content=False)
            failed.extend(asset_failed);blocked.extend(asset_blocked)
            auto_failed.extend(asset_failed);auto_blocked.extend(asset_blocked)
        if task.get('visual') and task['phase']=='implementation' and task['level'] in ('L2','L3'):
            independent=task.get('independent_review',{})
            if not independent.get('packet') or not independent.get('report'):
                blocked.append('Separate-context model review missing; export raw inputs and request an independent read-only reviewer')
            else:
                packet=review_packet.validate(local(root,independent['packet']),root)
                if packet.get('task_id')!=task['task_id']:raise ValueError('Independent packet belongs to another task')
                if any(not capture.get('source_matches') for capture in packet.get('captures',[])):raise ValueError('Independent review contains stale browser captures')
                if not packet.get('captures'):raise ValueError('Independent visual review must contain actual browser captures')
                report=review_packet.read_report(local(root,independent['packet']),local(root,independent['report']),root)
                separate_model_review='PACKET_BOUND_REPORT_IDENTITY_NOT_AUTHENTICATED'
                for finding in report['findings']:
                    if finding['status']=='FAIL':failed.append('Independent model finding: '+finding['requirement'])
                    elif finding['status']=='BLOCKED':blocked.append('Independent model finding unverified: '+finding['requirement'])
                if report['verdict']=='FAIL':failed.append('Independent model review reported known failures')
                elif report['verdict']=='BLOCKED':blocked.append('Independent model review remains blocked')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        blocked.append(str(exc))
        auto_blocked.append(str(exc))
    if isinstance(task,dict) and task.get('phase')=='implementation':
        try:
            checklist_gaps=checklist.final_gaps(SimpleNamespace(**globals()),root,task)
            blocked.extend(checklist_gaps)
            auto_blocked.extend(checklist_gaps)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            blocked.append('Checklist reconciliation: '+str(exc))
            auto_blocked.append('Checklist reconciliation: '+str(exc))
    aesthetic = critic.check(SimpleNamespace(**globals()), root, task) if isinstance(task,dict) else {'status':'NOT_REQUIRED','failures':[],'blockers':[]}
    failed.extend(aesthetic['failures'])
    blocked.extend(aesthetic['blockers'])
    automatic_status='FAIL' if auto_failed else 'BLOCKED' if auto_blocked else 'PASS'
    status = 'FAIL' if failed else 'BLOCKED' if blocked else 'PASS'
    metadata = task if isinstance(task,dict) else {}
    result = {'schema':2,'status':status,'checked_at':time.time(),'task_id':metadata.get('task_id'),
            'level':metadata.get('level'),'phase':metadata.get('phase'),
            'failures':failed,'blockers':blocked,'automated_checks':automated,'review_attestations':attestations,
            'automated_status':automatic_status,'visual_acceptance':'NOT_EVALUATED',
            'separate_model_review':separate_model_review,'critic':aesthetic,
            'qualification':'Execution receipts establish runner activity, not meaningful test completeness or aesthetic acceptance. Same-user malicious tampering requires an external protected runner to prevent.'}
    if _defer_completion:
        return result
    result = _complete_verification(root, metadata, result, include_delivery_review)
    if task_from_disk:
        result = _reconcile_task(root, metadata, result)
    return result


def _reconcile_task(root, expected_task, result):
    problem = None
    try:
        if load(root / TASK_PATH) != expected_task:
            problem = (
                "Task plan changed during verification; repeat against the current task"
            )
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        problem = "Task plan unavailable at completion: " + str(exc)
    if problem:
        result["blockers"].append(problem)
        if result["automated_status"] == "PASS":
            result["automated_status"] = "BLOCKED"
        result["status"] = "FAIL" if result["failures"] else "BLOCKED"
    result["checked_at"] = time.time()
    return result


def _complete_verification(root, task, validation, include_delivery_review=True):
    result = {
        **validation,
        "failures": list(validation["failures"]),
        "blockers": list(validation["blockers"]),
    }
    checks = task.get("checks", [])
    if not isinstance(checks, list) or any(
        not isinstance(check, dict) for check in checks
    ):
        result["blockers"].append("Task checks must be a list of check objects")
        if result["automated_status"] == "PASS":
            result["automated_status"] = "BLOCKED"
        checks = []
    api = SimpleNamespace(**globals())
    if include_delivery_review:
        closing = delivery_review.check(api, root, task)
        result["failures"].extend(closing["failures"])
        result["blockers"].extend(closing["blockers"])
        if closing["failures"]:
            result["automated_status"] = "FAIL"
        elif closing["blockers"] and result["automated_status"] == "PASS":
            result["automated_status"] = "BLOCKED"
    visual_needed = (
        task.get("visual")
        or task.get("phase") == "reference"
        or any(
            check.get("required") and check.get("type") == "review" for check in checks
        )
    )
    result["visual_acceptance"] = "NOT_REQUIRED"
    if visual_needed:
        if task.get("phase") == "implementation":
            approval = visual_approval.verify(api, root, task)
            result["visual_acceptance"] = approval["status"]
            result["failures"].extend(approval.get("failures", []))
            result["blockers"].extend(approval.get("blockers", []))
        else:
            result["blockers"].append(
                "Reference images await user selection; no final UI acceptance is claimed"
            )
    result["status"] = (
        "FAIL" if result["failures"] else "BLOCKED" if result["blockers"] else "PASS"
    )
    return result


def finalize(root, reflection_path=None):
    """Sync results, execute one current validation and seal its final review."""
    root = Path(root).resolve()
    pending = {
        "schema": 2,
        "status": "BLOCKED",
        "stage": "finalize",
        "checked_at": time.time(),
        "blockers": ["Finalization is awaiting current checks and completion"],
    }
    save(root / RESULT_PATH, pending)
    try:
        task = load(root / TASK_PATH)
        if not isinstance(task, dict):
            raise ValueError("Task plan must be a JSON object")
        api = SimpleNamespace(**globals())
        if task.get("phase") == "implementation" and task.get("checklist_plan"):
            checklist.sync(api, root, task)
        if not delivery_review.required(task):
            result = verify(root, task)
        else:
            validation = None

            def validate_current(
                project, current_task, *, include_delivery_review=False
            ):
                nonlocal validation
                validation = verify(
                    project,
                    current_task,
                    include_delivery_review=False,
                    _defer_completion=True,
                )
                return validation

            review = delivery_review.record(
                api,
                root,
                task,
                reflection_path=reflection_path,
                validator=validate_current,
            )
            result = _complete_verification(root, task, validation)
            result["delivery_review"] = review["report"]
        result = _reconcile_task(root, task, result)
        save(root / RESULT_PATH, result)
        return result
    except Exception as exc:
        save(
            root / RESULT_PATH,
            {
                **pending,
                "checked_at": time.time(),
                "error": str(exc),
                "blockers": [str(exc)],
            },
        )
        raise


def classify(prompt):
    if re.search(r'规范中心|全局.{0,30}(?:规范|规则|AGENTS|Skill|Hook)|(?:配置|设置|重建|重构).{0,25}(?:工作流|Hook|Skills)|frontend-policy|frontend-workflow',prompt,re.I):
        return 'maintenance'
    audit=re.search(r'是否|有没有|你觉得|审计|复核|评估|只检查|仅检查',prompt)
    explicit_change=re.search(r'(?:请|帮我|现在|直接|立即)\s*(?:检查并|检查后)?(?:修复|修改|重构|实现|制作|开发|搭建)|(?:检查|审计|复核|评估)[^。！？]{0,20}并(?:修复|修改|重构)',prompt)
    if audit and not explicit_change:
        return 'audit'
    frontend = re.search(r'前端|网页|网站|页面|界面|组件|响应式|动效|布局|\b(?:Vue|React|UI|CSS|SCSS|Tailwind|frontend|website|layout)\b',prompt,re.I)
    action = re.search(r'做|制作|设计|开发|搭建|修复|修改|重构|调整|美化|优化|implement|build|fix|redesign|change',prompt,re.I)
    return 'frontend' if frontend and action else 'other'

def workflow_request(prompt):
    """Explicit invocation/opt-out only; mentioning or configuring the skill is not invocation."""
    target=r'(?:\$?frontend-workflow|这个\s*[Ss]kill|这套工作流)'
    if re.search(r'(?:不要|不用|不再|不(?:想|要|再)?(?:使用|启用|调用|采用)|停止|取消|禁用|do\s+not|don\x27t|without|disable|stop).{0,40}'+target,prompt,re.I) or re.search(r'frontend-workflow.{0,20}(?:不要用|不用了|停止使用|禁用)',prompt,re.I):
        return 'disable'
    if not re.search(r'frontend-workflow',prompt,re.I):return None
    if re.search(r'^\s*(?:告诉我|请告诉我|如何|怎么|是否|你会|你是否|会不会|what\s+is|how\s+to|can\s+you)|frontend-workflow\s*(?:是什么|如何使用)|(?:将|把)\s*[`\s]*frontend-workflow.{0,30}(?:改为|设为|仅在|只在)',prompt,re.I):return None
    if re.search(r'(?:使用|启用|调用|采用|按|use\b|enable\b|invoke\b|apply\b)\s*[`\s]*\$?frontend-workflow',prompt,re.I) or re.match(r'^\s*\$frontend-workflow\b',prompt,re.I):
        return 'enable'
    return None

def hook(event):
    try:
        output=_hook_impl(event)
    except Exception as exc:
        # A broken plan/state must not become the documented non-blocking exit 1.
        # Only Stop events that have an explicit active state fail closed.
        state_path=CENTER/'state'/(hashlib.sha256(str(event.get('session_id','unknown')).encode()).hexdigest()[:24]+'.json')
        active=False
        try:
            state=load(state_path)
            active=state.get('explicit_opt_in') and state.get('active') and state.get('root')==str(Path(event.get('cwd') or os.getcwd()).resolve())
        except Exception:pass
        output={'systemMessage':'Frontend verifier unavailable: '+str(exc)}
        if event.get('hook_event_name')=='Stop' and active:
            output={'decision':'block','reason':'Frontend verification is BLOCKED because the current plan could not be checked: '+str(exc)+'. Fix the plan or report 最终状态：BLOCKED; do not claim PASS.'}
            message=str(event.get('last_assistant_message',''))
            if quality_checks.delivery_declarations(message)==['BLOCKED'] and not quality_checks.contradictory_delivery(message,'BLOCKED'):
                output={'systemMessage':output['reason']}
            elif state.get('retries',0)>=2:
                output={'continue':False,'stopReason':'Unreadable frontend task; bounded repair attempts exhausted.','systemMessage':output['reason']}
            else:
                state['retries']=state.get('retries',0)+1;save(state_path,state)
    host_check.record_event(event,output,policy_digest=policy_hash() if os.environ.get('FRONTEND_POLICY_HOST_PROBE') else None)
    return output

def _hook_impl(event):
    session = hashlib.sha256(str(event.get('session_id','unknown')).encode()).hexdigest()[:24]
    state_path = CENTER / 'state' / (session + '.json')
    state = load(state_path) if state_path.exists() else {}
    name, root = event.get('hook_event_name'), Path(event.get('cwd') or os.getcwd()).resolve()
    turn = str(event.get('turn_id','unknown'))
    opted_in=bool(state.get('explicit_opt_in') and state.get('root')==str(root))
    context = f'The user explicitly enabled frontend-workflow for this task. Load {SKILL / "SKILL.md"}. Use scoped checks and actual evidence. This does not enable the skill for unrelated future tasks.'
    if name == 'SessionStart':
        return {'hookSpecificOutput':{'hookEventName':name,'additionalContext':context}} if opted_in and state.get('active') else {}
    if name == 'UserPromptSubmit':
        prompt = str(event.get('prompt',''))
        request=workflow_request(prompt)
        kind = 'explicit-workflow' if request=='enable' else classify(prompt)
        normalized=re.sub(r'^(?:(?:好的|好|行|可以|请|那么|那就|okay|ok|yes)[，,。!！\s]*)+','',prompt.strip(),flags=re.I)
        fresh_task=re.search(r'新任务|另一个|换个项目|另外帮我|new\s+task|another\s+(?:project|task)',prompt,re.I)
        continuation = opted_in and state.get('active') and not fresh_task and (re.match(r'^(?:[ABCDabcd](?:\s|$)|继续|接着|选|采用|修复|调整|把|再|改|增加|减少|continue\b)',normalized,re.I) or re.search(r'同一个.{0,15}(?:页面|任务)|这版|上一版|刚才.{0,10}(?:页面|组件)|当前任务',prompt))
        active = request=='enable' or (request!='disable' and kind not in ('maintenance','audit') and bool(continuation))
        state = {'turn':turn,'root':str(root),'explicit_opt_in':bool(active),'active':bool(active),'started_at':time.time(),'continuation':bool(continuation),'retries':0,'kind':kind}
        save(state_path,state)
        return {'hookSpecificOutput':{'hookEventName':name,'additionalContext':context}} if active else {}
    if name == 'PostToolUse':
        if not opted_in or not state.get('active') or state.get('turn')!=turn:return {}
        arguments = event.get('tool_input',{})
        text = '\n'.join(str(arguments.get(key,'')) for key in ('command','cmd','patch','input')) if isinstance(arguments,dict) else str(arguments)
        paths = re.findall(r'^\*\*\* (?:Add|Update|Delete) File: (.+)$',text,re.M)
        if isinstance(arguments,dict):
            paths += [arguments[key] for key in ('file_path','path','target_file') if isinstance(arguments.get(key),str)]
        paths = [(root / value.strip()).resolve() for value in paths]
        if paths and all(path.is_relative_to(CENTER) or path.is_relative_to(SKILL) for path in paths) and not (root/TASK_PATH).exists():
            state.update(active=False,explicit_opt_in=False,turn=turn,kind='maintenance');save(state_path,state)
            return {}
        application_paths = [path for path in paths if not path.is_relative_to(CENTER) and not path.is_relative_to(SKILL)]
        touched = any(path.suffix.lower() in SOURCE_EXT for path in application_paths)
        if touched:
            state.update(active=True,turn=turn,implementation_touched=True,retries=0 if state.get('turn') != turn else state.get('retries',0))
            save(state_path,state)
            planning_context=''
            if (root/TASK_PATH).is_file():
                try:
                    task=load(root/TASK_PATH)
                    gaps=preflight.receipt_gaps(SimpleNamespace(**globals()),root,task)
                    if gaps:planning_context=' Before further UI implementation, resolve preflight: '+'; '.join(gaps)
                except (OSError,ValueError,TypeError,KeyError):planning_context=' Current task plan is unreadable; repair it before further UI implementation.'
            return {'hookSpecificOutput':{'hookEventName':name,'additionalContext':context+planning_context}}
        return {}
    if name != 'Stop' or not opted_in or not state.get('active') or state.get('turn') != turn:
        return {}
    current_plan = load(root / TASK_PATH) if (root / TASK_PATH).exists() else {}
    if not isinstance(current_plan,dict):
        current_plan = {}
    message = str(event.get('last_assistant_message') or '')
    awaiting_style = '参考' in message and re.search(r'(?:请选择|请选|选定|回复)[^。！？\n]{0,60}(?:[ABCD]|编号|风格|方案)',message)
    if awaiting_style and not state.get('implementation_touched') and (not current_plan or current_plan.get('phase')=='reference') and not quality_checks.delivery_declarations(message) and not quality_checks.contradictory_delivery(message,'BLOCKED'):
        return {'systemMessage':'Style references await user selection. No implementation or final UI acceptance is claimed; no gallery or formal review is required.'}
    result = verify(root)
    if (root / TASK_PATH).exists() and not state.get('continuation') and current_plan.get('created_at',0) < state.get('started_at',0):
        result['blockers'].append('This is an earlier task plan; initialize the current task before delivery')
        result['status'] = 'FAIL' if result['failures'] else 'BLOCKED'
    save(root / RESULT_PATH,result)
    message = str(event.get('last_assistant_message') or '')
    declared = quality_checks.delivery_declarations(message)
    if len(declared)==1 and declared[0] == result['status'] and not quality_checks.contradictory_delivery(message,result['status']):
        if result['status']=='PASS':
            state.update(active=False,explicit_opt_in=False);save(state_path,state)
        return {} if result['status'] == 'PASS' else {'systemMessage':'Frontend task '+result['status']+'. See '+str(root / RESULT_PATH)}
    if state.get('retries',0) >= config()['repair_continuations']:
        return {'continue':False,'stopReason':'Delivery verification failed; repair continuation limit reached.',
                'systemMessage':f'Frontend delivery is {result["status"]}; no verified PASS. See {root / RESULT_PATH}'}
    state['retries'] = state.get('retries',0) + 1
    save(state_path,state)
    return {'decision':'block','reason':f'Frontend delivery check: {result["status"]}. '+ '; '.join((result['failures']+result['blockers'])[:5]) +
            f'. Fix applicable issues or report actual blockers; finish with 最终状态：{result["status"]}. Use {SKILL / "SKILL.md"}. No invented evidence.'}

def main():
    for stream in (sys.stdin,sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('command',choices=['discover','init','fingerprint','run','browser-run','capture','review','check','hook','probe','host-probe','review-packet','catalog','preflight','doctor','checklist-sync','delivery-review','finalize','critic-run'])
    parser.add_argument('--cli')
    parser.add_argument('--output-dir')
    parser.add_argument('--brief',nargs='*',default=[])
    parser.add_argument('--root',default=os.getcwd())
    parser.add_argument('--level',choices=['L1','L2','L3'],default='L2')
    parser.add_argument('--summary',default='Frontend task')
    parser.add_argument('--files',nargs='+',default=[])
    parser.add_argument('--profile',choices=['strict','project','expressive'],default='strict')
    parser.add_argument('--phase',choices=['implementation','reference'],default='implementation')
    parser.add_argument('--visual',action=argparse.BooleanOptionalAction,default=None)
    parser.add_argument('--interactive',action='store_true')
    parser.add_argument('--replace',action='store_true')
    parser.add_argument('--pages',nargs='+',default=['main'])
    parser.add_argument('--widths',nargs='+',type=int,default=[390,1280])
    parser.add_argument('--states',nargs='+',default=['default'])
    parser.add_argument('--check-id',default='project-check')
    parser.add_argument('--captures',nargs='+',default=[])
    parser.add_argument('--observations')
    parser.add_argument('--spec')
    argv = sys.argv[1:]
    split = argv.index('--') if '--' in argv else len(argv)
    args = parser.parse_args(argv[:split])
    root = Path(args.root).resolve()
    try:
        if args.command == 'hook':
            result = hook(json.load(sys.stdin))
        elif args.command=='preflight':
            result=preflight_check(root,load(root/TASK_PATH),issue=True)
        elif args.command=='doctor':
            import doctor
            result=doctor.run(SimpleNamespace(**globals()))
        elif args.command == 'probe':
            result = {'version':config()['version'],'skill':str(SKILL / 'SKILL.md'),'policy_hash':policy_hash()}
        elif args.command=='host-probe':
            result=host_check.run(args.cli,expected_policy=policy_hash())
        elif args.command=='review-packet':
            result=review_packet.create(root,load(root/TASK_PATH),args.output_dir or root/'work/frontend-policy/review-packets',args.brief)
        elif args.command=='catalog':
            result=validate_rule_binding()
        elif args.command=='checklist-sync':
            task=load(root/TASK_PATH)
            report=checklist.sync(SimpleNamespace(**globals()),root,task)
            result={'status':report['status'],'report':task.get('implementation_checklist'),
                    'counts':{state:sum(row['status']==state for row in report['rows']) for state in ('VERIFIED','FAIL','BLOCKED')},
                    'blockers':report['blockers']}
        elif args.command=='delivery-review':
            task=load(root/TASK_PATH)
            result=delivery_review.record(SimpleNamespace(**globals()),root,task,reflection_path=args.observations)
        elif args.command=='finalize':
            result=finalize(root,reflection_path=args.observations)
        elif args.command=='critic-run':
            task=load(root/TASK_PATH)
            critic.report_path(task)
            critic_invoked=True
            result=critic.run(SimpleNamespace(**globals()),root,task,cli=args.cli)
        elif args.command == 'discover':
            result = discover(root)
        elif args.command == 'init':
            result = init_task(root,args.level,args.summary,args.files,args.profile,args.phase,args.visual,args.interactive,args.pages,args.widths,args.states,args.replace)
        elif args.command == 'run':
            result = run_check(root,args.check_id,argv[split+1:])
        elif args.command == 'browser-run':
            result=run_browser(root,args.spec)
        elif args.command == 'fingerprint':
            result = hashes(root,load(root / TASK_PATH))
        elif args.command == 'capture':
            task = load(root / TASK_PATH)
            check_id = args.check_id if args.check_id != 'project-check' else 'browser'
            check = next(item for item in task['checks'] if item['id']==check_id)
            if check['type'] != 'browser':
                raise ValueError('capture requires a planned browser check')
            data = browser_findings(root,task,args.captures)
            result = record(root,task,check_id,{'captures':args.captures,'status':'BLOCKED','diagnostic_status':'FAIL' if data['findings'] else 'BLOCKED' if data['blockers'] else 'PASS','findings':data['findings'],'blockers':data['blockers']+['Imported diagnostics are not a fixed-runner execution']})
        elif args.command == 'review':
            task = load(root / TASK_PATH)
            check_id = args.check_id if args.check_id != 'project-check' else 'visual'
            result = record(root,task,check_id,{'observations':load(local(root,args.observations)),'status':'REVIEW_ATTESTATION'})
        else:
            save(root / RESULT_PATH, {'schema':2,'status':'BLOCKED','stage':'check','checked_at':time.time(),'blockers':['Current verification has not completed']})
            result = verify(root)
            save(root / RESULT_PATH,result)
        print(json.dumps(result,ensure_ascii=False))
        return 1 if isinstance(result,dict) and result.get('status') == 'FAIL' else 2 if isinstance(result,dict) and result.get('status') == 'BLOCKED' else 0
    except Exception as exc:
        if args.command == 'hook':
            print(json.dumps({'systemMessage':'Frontend policy verification unavailable: '+str(exc)},ensure_ascii=False))
            return 1
        error_result = {'status':'BLOCKED','error':str(exc)}
        if args.command=='check':
            save(root / RESULT_PATH,error_result)
        elif args.command=='critic-run' and not locals().get('critic_invoked',False):
            save(root / RESULT_PATH,error_result)
        print(json.dumps(error_result,ensure_ascii=False))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
