"""Freeze raw inputs for a separate reviewer. Exclude implementer verdicts by construction."""
import hashlib
import json
from pathlib import Path
import shutil
import time
import uuid
import critic
import paths

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def create(root,task,output_dir,briefs=()):
    root=Path(root).resolve();target=Path(output_dir).resolve()/uuid.uuid4().hex
    target.mkdir(parents=True,exist_ok=False)
    files=[];source_hashes={}
    def copy(path,kind,relative=None):
        path=Path(path).resolve()
        if not path.is_file() or path.stat().st_size>30_000_000:raise ValueError('Missing/oversized review input: '+str(path))
        if relative is not None:
            if not path.is_relative_to(root):raise ValueError('Review source escapes project')
            name='project/'+str(path.relative_to(root)).replace('\\','/')
            source_hashes[str(path.relative_to(root)).replace('\\','/')]=digest(path)
        else:name='requirements/'+str(len(files))+'-'+path.name
        destination=target/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
        files.append({'path':name,'kind':kind,'sha256':digest(destination)})
    for name in task.get('files',[]):
        if Path(name).suffix.lower() in {'.html','.css','.scss','.sass','.less','.vue','.svelte','.tsx','.jsx','.js','.ts'}:
            copy(root/name,'implementation',relative=name)
    sources=list(briefs)+[root/item['source'] for item in task.get('project_requirements',[]) if item.get('source')]
    for source in dict.fromkeys(map(str,sources)):copy(source,'raw_requirement')
    for field in ('style_summary','selected_reference','design_document','style_discovery','checklist_plan'):
        if task.get(field):copy(root/task[field],field,relative=task[field])
    for image in task.get('references',[]):copy(root/image['path'],'style_reference',relative=image['path'])
    if task.get('style_contract',{}).get('path'):
        source=task['style_contract']['path']
        copy(root/source,'complete_style_contract',relative=source)
    copy(paths.original_rules(),'global_requirement')
    if critic.required(task):
        path=root/critic.report_path(task)
        if path.is_file():
            execution=json.loads(path.read_text(encoding='utf-8-sig'))
            copy(path,'critic_execution',relative=critic.report_path(task))
            for name in execution.get('artifact_hashes',{}):
                copy(root/name,'critic_execution',relative=name)
    captures=[];browser_id=next((item['id'] for item in task.get('checks',[]) if item['type']=='browser'),None)
    if browser_id and task.get('evidence',{}).get(browser_id):
        record=json.loads((root/task['evidence'][browser_id]).read_text(encoding='utf-8-sig'))
        for name in record.get('captures',[]):
            path=(root/name).resolve()
            if not path.is_relative_to(root):raise ValueError('Capture escapes project')
            snapshot=json.loads(path.read_text(encoding='utf-8-sig'))
            copy(path,'browser_capture',relative=name);copy(root/snapshot['screenshot'],'screenshot',relative=snapshot['screenshot'])
            if snapshot.get('region_screenshot'):
                copy(root/snapshot['region_screenshot'],'scoped_screenshot',relative=snapshot['region_screenshot'])
            captures.append({'page':snapshot['page'],'width':snapshot['viewport']['width'],'state':snapshot['state'],
                             'source_matches':all(snapshot.get('source_hashes',{}).get(key)==value for key,value in source_hashes.items() if Path(key).suffix.lower() in {'.html','.css','.js','.ts','.jsx','.tsx','.vue','.svelte'})})
    manifest={'schema':1,'created_at':time.time(),'task_id':task.get('task_id'),'summary':task.get('summary'),'source_root':str(root),
              'files':files,'project_hashes':source_hashes,'captures':captures,
              'scope':'Raw source, requirements, browser artifacts and available Critic execution evidence. Export is not execution certification, reviewer execution, or independent approval.'}
    manifest['packet_id']=hashlib.sha256(json.dumps(manifest,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    (target/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (target/'REVIEW.md').write_text('Read manifest.json and raw inputs. Do not read implementer verdicts or prior chat. Actually inspect screenshots. Check source/screenshot identity, original requirements, project-specific layout/readability/library/content constraints, state transitions and missing evidence. Report specific failures and unverified scope, with source/screenshot references. Include packet_id. Do not edit the business project. This is an independent model review, not protected external approval. A copied PASS statement never certifies the UI.',encoding='utf-8')
    return {'status':'PASS','packet':str(target/'manifest.json'),'packet_id':manifest['packet_id'],'files':len(files),'captures':len(captures)}

def validate(path,current_root=None):
    path=Path(path).resolve();data=json.loads(path.read_text(encoding='utf-8-sig'))
    body={key:value for key,value in data.items() if key!='packet_id'}
    if hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False).encode()).hexdigest()!=data.get('packet_id'):raise ValueError('Review manifest changed')
    for item in data['files']:
        artifact=(path.parent/item['path']).resolve()
        if not artifact.is_relative_to(path.parent) or digest(artifact)!=item['sha256']:raise ValueError('Frozen review input changed')
    original=paths.original_rules()
    originals=[item for item in data['files'] if item.get('kind')=='global_requirement']
    if len(originals)!=1 or originals[0]['sha256']!=digest(original):raise ValueError('Review packet uses stale or missing original requirements')
    if current_root is not None:
        current_root=Path(current_root).resolve()
        for name,value in data.get('project_hashes',{}).items():
            artifact=(current_root/name).resolve()
            if not artifact.is_relative_to(current_root) or digest(artifact)!=value:raise ValueError('Review packet is stale relative to project')
    return data

def read_report(packet_path,report_path,current_root):
    packet=validate(packet_path,current_root);report_path=Path(report_path)
    if report_path.stat().st_size>1_000_000:raise ValueError('Independent report exceeds size limit')
    report=json.loads(report_path.read_text(encoding='utf-8-sig'))
    if report.get('schema')!=1 or report.get('packet_id')!=packet['packet_id'] or report.get('reviewer',{}).get('kind')!='separate_model':
        raise ValueError('Independent report needs a matching packet and separate-model reviewer record')
    if report.get('verdict') not in ('PASS','FAIL','BLOCKED') or not report.get('findings'):raise ValueError('Independent review verdict/findings missing')
    artifacts={item['path'] for item in packet['files']}
    for item in report['findings']:
        if not all(item.get(key) for key in ('requirement','location','observed','evidence')) or item.get('status') not in ('PASS','FAIL','BLOCKED'):
            raise ValueError('Independent finding lacks a specific observation/evidence/status')
        if not set(item['evidence'])<=artifacts:raise ValueError('Independent finding cites evidence outside the raw packet')
    if report['verdict']=='PASS' and any(item['status']!='PASS' for item in report['findings']):raise ValueError('Independent PASS contradicts its unresolved findings')
    return report
