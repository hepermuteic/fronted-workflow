"""Read-only installation health check. It never grants Hook trust."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import sys

def run(api):
    failures=[];checks=[]
    try:
        catalog=api.validate_rule_binding();checks.append({'check':'original-rule-routes','count':len(catalog)})
        metadata=(api.SKILL/'agents/openai.yaml').read_text(encoding='utf-8-sig')
        if 'allow_implicit_invocation: false' not in metadata:failures.append('Explicit-only Skill policy missing')
        spec=api.critic.specification()
        checks.append({'check':'critic-agent','path':str(api.critic.AGENT_FILE),'model':spec['model'],'reasoning_effort':spec['model_reasoning_effort'],'scope':'Configuration only; actual model execution is checked separately'})
        for file in api.CODE_DIR.glob('*.py'):ast.parse(file.read_text(encoding='utf-8-sig'),filename=str(file))
        if not (api.SKILL/'scripts/verify.py').is_file():failures.append('Skill executable entry missing')
        hooks=api.load(api.CENTER.parent/'hooks.json')
        for name in ('SessionStart','UserPromptSubmit','PostToolUse','Stop'):
            definitions=hooks.get('hooks',{}).get(name,[])
            if not any(str(api.CENTER/'verify.py').replace('\\','/') in hook.get('command','').replace('\\','/') for group in definitions for hook in group.get('hooks',[])):failures.append('Global hook definition missing: '+name)
        node=shutil.which('node')
        if not node:failures.append('Node executable unavailable')
        else:
            for name in ('browser-run.cjs','font_capture.cjs'):
                script=api.CODE_DIR/name
                result=subprocess.run([node,'--check',str(script)],capture_output=True,text=True,timeout=15)
                if result.returncode:failures.append(name+' syntax error: '+result.stderr[-1000:])
            module_paths=[str(api.CENTER/'tooling'),str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node'),str(Path.cwd())]
            probe="console.log(require.resolve('playwright',{paths:JSON.parse(process.argv[1])}))"
            runtime=subprocess.run([node,'-e',probe,json.dumps(module_paths)],capture_output=True,text=True,timeout=15)
            if runtime.returncode:failures.append('Playwright unavailable; run scripts/install.py --setup-tools or install it in the project')
            else:checks.append({'check':'playwright','path':runtime.stdout.strip()})
        probes=[]
        for candidate in sorted((api.CENTER/'host-probes').glob('*/result.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:8]:
            data=api.load(candidate)
            events=candidate.with_name('events.jsonl')
            if data.get('status')!='PASS' or data.get('policy_hash')!=api.policy_hash() or not events.is_file():continue
            current=[json.loads(line) for line in events.read_text(encoding='utf-8').splitlines() if line.strip()]
            if current and all(event.get('verifier_sha256')==api.sha(api.CODE_DIR/'verify.py') and event.get('helper_sha256')==api.sha(api.CODE_DIR/'host_check.py') and event.get('hooks_sha256')==api.sha(api.CENTER.parent/'hooks.json') for event in current):
                probes.append({'path':str(candidate),'scope':data.get('scope'),'observed_events':data.get('observed_events')});break
        try:
            trust=api.visual_approval.load_trust()
            approval={'status':'CONFIGURED','issuer':trust['issuer'],'scope':'Protected public-key store only; no task approval inferred'}
        except Exception as exc:
            approval={'status':'BLOCKED','reason':str(exc),'scope':'Separate reviewer account and protected runtime/store require provisioning'}
        checks.extend([{'check':'python','executable':sys.executable},{'check':'node','executable':node},{'check':'hook-definitions','trust':'Not inferred from JSON; actual host lifecycle is reported separately'},{'check':'visual-approval','result':approval}])
        return {'status':'BLOCKED' if failures else 'PASS','scope':'Local installation and syntax only','version':api.config()['version'],'policy_hash':api.policy_hash(),'checks':checks,'failures':failures,'host_lifecycle':probes or 'UNVERIFIED_FOR_CURRENT_CODE','visual_certification':'NOT_PROVIDED','security_boundary':'Same OS user; not protected CI'}
    except Exception as exc:return {'status':'BLOCKED','scope':'Local installation','failures':[str(exc)]}
