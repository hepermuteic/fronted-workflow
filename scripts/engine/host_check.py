"""Operational host lifecycle probe, not a security boundary against the same OS user."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from contextlib import nullcontext
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import threading

import paths
CENTER=paths.STATE_DIR
CODE_DIR=paths.CODE_DIR

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def record_event(event,output=None,policy_digest=None):
    nonce=os.environ.get('FRONTEND_POLICY_HOST_PROBE','')
    if not re.fullmatch('[0-9a-f]{32}',nonce):return
    lineage=[]
    try:
        import psutil
        for process in [psutil.Process(),*psutil.Process().parents()]:
            lineage.append({'pid':process.pid,'name':process.name()})
    except (ImportError,OSError):
        lineage=[{'pid':os.getpid(),'name':'python'},{'pid':os.getppid(),'name':'parent'}]
    record={'nonce':nonce,'time':time.time(),'event':event.get('hook_event_name'),'session_id':event.get('session_id'),
            'lineage':lineage,'verifier_sha256':digest(CODE_DIR/'verify.py'),'helper_sha256':digest(__file__),
            'hooks_sha256':digest(CENTER.parent/'hooks.json'),'policy_hash':policy_digest,
            'decision':(output or {}).get('decision'),'continue':(output or {}).get('continue'),
            'injected_context':bool((output or {}).get('hookSpecificOutput',{}).get('additionalContext'))}
    folder=CENTER/'host-probes'/nonce;folder.mkdir(parents=True,exist_ok=True)
    with (folder/'events.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(record,ensure_ascii=False)+'\n')

def run(cli=None,timeout=45,expected_policy=None):
    binary=cli or os.environ.get('CODEX_CLI_PATH') or shutil.which('codex')
    if not binary:raise ValueError('Codex executable unavailable; host activation is unverified')
    nonce=uuid.uuid4().hex;folder=CENTER/'host-probes'/nonce;folder.mkdir(parents=True)
    environment=dict(os.environ,FRONTEND_POLICY_HOST_PROBE=nonce)
    started=time.time()
    requests=[];tool_inventory=[]
    class Fixture(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            request=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
            requests.append(self.path)
            offered=None
            for tool in request.get('tools',[]):
                tool_inventory.append({'type':tool.get('type'),'name':tool.get('name'),'child_names':[child.get('name') for child in tool.get('tools',[])]})
                if tool.get('name','').split('.')[-1]=='apply_patch':offered=tool
                for child in tool.get('tools',[]):
                    if child.get('name')=='apply_patch':offered={**child,'name':tool['name']+'.apply_patch'}
            # Some installed models transport native tool definitions in their
            # prompt rather than Responses.tools. Ask the host to execute the
            # known native tool; success still requires its real event + marker.
            if not offered:offered={'type':'custom','name':'apply_patch'}
            if len(requests)==1 and offered:
                patch='*** Begin Patch\n*** Add File: lifecycle-marker.txt\n+Isolated frontend lifecycle fixture.\n*** End Patch'
                if offered.get('type')=='custom':
                    message={'id':'ctc_fixture','type':'custom_tool_call','call_id':'call_frontend_fixture','name':offered['name'],'input':patch}
                else:
                    message={'id':'fc_fixture','type':'function_call','call_id':'call_frontend_fixture','name':offered['name'],'arguments':json.dumps({'input':patch})}
            else:message={'id':'msg_fixture','type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':'HOST_PROBE_OK','annotations':[]}]}
            response={'id':'resp_fixture','object':'response','created_at':int(time.time()),'status':'completed','output':[message],
                      'usage':{'input_tokens':0,'output_tokens':0,'total_tokens':0}}
            events=[{'type':'response.created','response':{**response,'status':'in_progress','output':[]}},
                    {'type':'response.output_item.added','output_index':0,'item':{**message,'status':'in_progress','content':[]}},
                    {'type':'response.content_part.added','item_id':message['id'],'output_index':0,'content_index':0,'part':{'type':'output_text','text':'','annotations':[]}},
                    {'type':'response.output_text.delta','item_id':message['id'],'output_index':0,'content_index':0,'delta':'HOST_PROBE_OK'},
                    {'type':'response.output_text.done','item_id':message['id'],'output_index':0,'content_index':0,'text':'HOST_PROBE_OK'},
                    {'type':'response.output_item.done','output_index':0,'item':message},{'type':'response.completed','response':response}]
            if message['type']!='message':
                events=[events[0],{'type':'response.output_item.added','output_index':0,'item':message},events[-2],events[-1]]
            body=''.join('event: '+item['type']+'\ndata: '+json.dumps(item)+'\n\n' for item in events).encode()
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',0),Fixture);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    # Retain this tiny isolated workspace as probe evidence. Windows can keep a
    # newly patched file locked briefly after the sandbox helper exits; automatic
    # recursive cleanup must not discard a successfully observed lifecycle.
    with nullcontext(tempfile.mkdtemp(prefix='frontend-host-probe-')) as root:
        command=[str(binary),'exec','--skip-git-repo-check','--ephemeral','--sandbox','workspace-write','--json','--cd',root,
                 '-c','model_provider="frontend_lifecycle_fixture"',
                 '-c','model_providers.frontend_lifecycle_fixture.name="Local lifecycle fixture"',
                 '-c',f'model_providers.frontend_lifecycle_fixture.base_url="http://127.0.0.1:{server.server_port}/v1"',
                 '-c','model_providers.frontend_lifecycle_fixture.wire_api="responses"',
                 '-c','model_providers.frontend_lifecycle_fixture.requires_openai_auth=false',
                 '-c','model_providers.frontend_lifecycle_fixture.supports_websockets=false',
                 '使用 frontend-workflow for this synthetic lifecycle validation task. Create only lifecycle-marker.txt in this isolated temporary directory using apply_patch, then output HOST_PROBE_OK. Do not create UI or modify any other file.']
        process=subprocess.Popen(command,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:stdout,stderr=process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill();stdout,stderr=process.communicate()
        (folder/'stdout.jsonl').write_text(stdout,encoding='utf-8');(folder/'stderr.log').write_text(stderr,encoding='utf-8')
        marker=Path(root)/'lifecycle-marker.txt'
        marker_created=marker.is_file() and marker.stat().st_size>0
        marker_content='UNAVAILABLE'
        try:
            marker_content='MATCH' if marker.read_text(encoding='utf-8').strip()=='Isolated frontend lifecycle fixture.' else 'MISMATCH'
        except PermissionError:marker_content='OS_ACCESS_DENIED'
        except OSError:pass
        completed_write=False
        for line in stdout.splitlines():
            try:item=json.loads(line)
            except ValueError:continue
            change=item.get('item',{})
            if item.get('type')=='item.completed' and change.get('type')=='file_change' and change.get('status')=='completed':
                completed_write=completed_write or any(Path(entry.get('path','')).resolve()==marker.resolve() and entry.get('kind')=='add' for entry in change.get('changes',[]))
    server.shutdown();server.server_close()
    events=[]
    if (folder/'events.jsonl').exists():
        events=[json.loads(line) for line in (folder/'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    accepted=[item for item in events if item.get('nonce')==nonce and item.get('time',0)>=started and any(parent['pid']==process.pid for parent in item['lineage'])
              and item['verifier_sha256']==digest(CODE_DIR/'verify.py') and item['helper_sha256']==digest(__file__) and item['hooks_sha256']==digest(CENTER.parent/'hooks.json') and (expected_policy is None or item.get('policy_hash')==expected_policy)]
    required={'SessionStart','UserPromptSubmit','PostToolUse','Stop'};seen={item['event'] for item in accepted}
    stops=[item for item in accepted if item['event']=='Stop']
    enforced=any(item.get('decision')=='block' for item in stops) and any(item.get('continue') is False for item in stops)
    result={'schema':1,'status':'PASS' if required<=seen and process.returncode==0 and enforced and marker_created and completed_write and marker_content!='MISMATCH' else 'BLOCKED','nonce':nonce,'runner_pid':process.pid,
            'exit_code':process.returncode,'observed_events':sorted(seen),'missing_events':sorted(required-seen),'artifact_dir':str(folder),'policy_hash':expected_policy,
            'stop_enforcement_observed':enforced,'isolated_marker_created':marker_created,'native_write_completed':completed_write,'marker_content_read':marker_content,'fixture_workspace':root,'fixture_responses':len(requests),'actual_model_calls':0,'offered_tools':tool_inventory[:30],
            'scope':'Actual installed Codex CLI lifecycle with deterministic local response fixture; not a model or desktop task certification.',
            'qualification':'Parent lineage and actual lifecycle execution, not hostile same-user tamper protection. No hook trust bypass flag is used.'}
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
