"""Verify a reviewer signature against an administrator-protected public key."""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

DOMAIN = b'codex-frontend-visual-approval-v1\0'
TRUST_FILE = Path('C:/ProgramData/CodexFrontendApproval/trust.json')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def request_body(api, root, task):
    independent = task.get('independent_review', {})
    packet_path = api.local(root, independent.get('packet'))
    report_path = api.local(root, independent.get('report'))
    packet = api.review_packet.validate(packet_path, root)
    if not packet.get('captures') or any(not x.get('source_matches') for x in packet['captures']):
        raise ValueError('Approval requires current browser captures')
    artifacts = {}
    for record_name in task.get('evidence', {}).values():
        record_path = api.local(root, record_name)
        artifacts[record_name] = api.sha(record_path)
        record = api.load(record_path)
        for name in record.get('artifact_hashes', {}):
            artifacts[name] = api.sha(api.local(root, name))
    artifacts[independent['packet']] = api.sha(packet_path)
    artifacts[independent['report']] = api.sha(report_path)
    review_files = [{'path': 'review/' + item['path'], 'sha256': item['sha256']} for item in packet['files']]
    review_files.append({'path': 'review/manifest.json', 'sha256': api.sha(packet_path)})
    review_files.append({'path': 'review/report.json', 'sha256': api.sha(report_path)})
    if task.get('checklist_plan'):
        checklist_path=api.local(root,task.get('implementation_checklist'))
        artifacts[task['implementation_checklist']]=api.sha(checklist_path)
        review_files.append({'path':'review/checklist.md','sha256':api.sha(checklist_path)})
    if api.delivery_review.required(task):
        name=api.delivery_review.report_path(task)
        artifacts[name]=api.sha(api.local(root,name))
        review_files.append({'path':'review/delivery-review.json','sha256':artifacts[name]})
    if api.critic.required(task):
        for index,(name,value) in enumerate(api.critic.artifacts(api,root,task).items()):
            artifacts[name]=value
            if 'project/'+name.replace('\\','/') not in {item['path'] for item in packet['files']}:
                review_files.append({'path':'review/critic/'+str(index)+'-'+Path(name).name,'sha256':value})
    return {'schema': 1, 'audience': 'codex-frontend-visual-v1', 'task_id': task['task_id'],
            'policy_hash': api.policy_hash(), 'contract_hash': api.contract_hash(task),
            'source_hashes': api.hashes(root, task), 'evidence_hashes': artifacts,
            'packet_id': packet['packet_id'], 'review_files': review_files}


def export(api, root, output):
    task = api.load(root / api.TASK_PATH)
    result = api.verify(root, task)
    remaining = [x for x in result['blockers'] if not x.startswith('Visual approval:')]
    if task.get('phase') != 'implementation' or result['failures'] or remaining or result['automated_status'] != 'PASS':
        raise ValueError('Resolve implementation checks before approval export: ' + '; '.join(result['failures'] + remaining))
    body = request_body(api, root, task)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Use a new approval bundle directory')
    output.mkdir(parents=True)
    packet = api.local(root, task['independent_review']['packet'])
    shutil.copytree(packet.parent, output / 'review')
    shutil.copyfile(api.local(root, task['independent_review']['report']), output / 'review/report.json')
    if task.get('checklist_plan'):
        shutil.copyfile(api.local(root,task['implementation_checklist']),output/'review/checklist.md')
    if api.delivery_review.required(task):
        shutil.copyfile(api.local(root,api.delivery_review.report_path(task)),output/'review/delivery-review.json')
    if api.critic.required(task):
        folder=output/'review/critic'
        extras={item['path'] for item in body['review_files'] if item['path'].startswith('review/critic/')}
        for index,name in enumerate(api.critic.artifacts(api,root,task)):
            target='review/critic/'+str(index)+'-'+Path(name).name
            if target in extras:
                folder.mkdir(exist_ok=True)
                shutil.copyfile(api.local(root,name),folder/(str(index)+'-'+Path(name).name))
    api.save(output / 'request.json', body)
    return {'status': 'PASS', 'scope': 'Approval bundle export', 'request': str(output / 'request.json'),
            'request_sha256': digest(body), 'next': 'Review and sign under the separate approval account'}


def load_trust():
    if os.name != 'nt':
        raise ValueError('This installation requires the Windows protected trust store')
    # Fail closed for writable trust stores, including ownership/DACL rights.
    # The check is conservative for filtered administrator tokens.
    script = r'''
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$identities = @($identity.User.Value) + @($identity.Groups | ForEach-Object { $_.Value })
$target = 'C:\ProgramData\CodexFrontendApproval\trust.json'
foreach ($path in @($target, (Split-Path $target), 'C:\ProgramData')) {
    $acl = Get-Acl -LiteralPath $path
    $owner = $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
    if ($identities -contains $owner) { throw "Agent can control trust-store owner: $path" }
    $mask = 0xD0040
    if ($path -ne 'C:\ProgramData') { $mask = 0xD0156 }
    foreach ($rule in $acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
        if ($rule.AccessControlType -eq 'Allow' -and $identities -contains $rule.IdentityReference.Value -and (([int]$rule.FileSystemRights -band $mask) -ne 0)) {
            throw "Agent can change trust store: $path"
        }
    }
}
'''
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    process = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                             capture_output=True, timeout=20)
    if process.returncode:
        raise ValueError('Protected public-key store missing or writable by agent account')
    trust = json.loads(TRUST_FILE.read_text(encoding='utf-8-sig'))
    if trust.get('schema') != 1 or not isinstance(trust.get('issuer'), str) or not trust['issuer'] or not isinstance(trust.get('reviewers'), list) or not trust['reviewers'] or not all(isinstance(x,str) and x for x in trust['reviewers']):
        raise ValueError('Protected trust configuration is incomplete')
    return trust


def verify(api, root, task):
    try:
        trust = load_trust()
        approval = task.get('visual_approval', {})
        body = api.load(api.local(root, approval.get('request')))
        if body != request_body(api, root, task):
            raise ValueError('Request is stale relative to source, policy or evidence')
        envelope = api.load(api.local(root, approval.get('receipt')))
        payload = envelope['payload']
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(trust['public_key'], validate=True))
        key.verify(base64.b64decode(envelope['signature'], validate=True), DOMAIN + canonical(payload))
        if payload.get('schema') != 1 or payload.get('request_sha256') != digest(body):
            raise ValueError('Signature belongs to another request')
        if payload.get('issuer') != trust['issuer'] or payload.get('reviewer') not in trust['reviewers']:
            raise ValueError('Reviewer is outside the protected allowlist')
        issued, expires = payload['issued_at'], payload['expires_at']
        if not isinstance(issued, (int, float)) or not isinstance(expires, (int, float)):
            raise ValueError('Invalid approval timestamps')
        if not issued <= time.time() < expires or not 0 < expires - issued <= 86400:
            raise ValueError('Approval expired, future-dated or exceeds 24 hours')
        if payload.get('decision') == 'reject':
            return {'status': 'REJECTED', 'failures': ['Visual approval: reviewer rejected this revision']}
        if payload.get('decision') != 'approve':
            raise ValueError('Approval decision is invalid')
        return {'status': 'APPROVED', 'reviewer': payload['reviewer'], 'expires_at': expires}
    except Exception as exc:
        return {'status': 'BLOCKED', 'blockers': ['Visual approval: ' + (str(exc) or type(exc).__name__)]}


if __name__ == '__main__':
    import argparse
    from types import SimpleNamespace
    import verify as policy
    parser = argparse.ArgumentParser(description='Export an immutable visual approval request')
    parser.add_argument('--root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(export(SimpleNamespace(**vars(policy)), Path(args.root).resolve(), args.output), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'status': 'BLOCKED', 'error': str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
