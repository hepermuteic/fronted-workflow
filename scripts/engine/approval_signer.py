"""Run manually under a separate reviewer account. Never give the agent the private key."""
import argparse
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

DOMAIN = b'codex-frontend-visual-approval-v1\0'


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def secure_directory(directory):
    directory = directory.resolve()
    if not directory.is_relative_to(Path.home().resolve()) or directory.exists():
        raise ValueError('Choose a new private directory inside the reviewer profile')
    directory.mkdir(mode=0o700)
    if os.name == 'nt':
        identity = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True)
        import csv
        sid = next(csv.reader([identity.strip()]))[1]
        subprocess.run(['icacls.exe', str(directory), '/inheritance:r', '/grant:r',
                        '*' + sid + ':(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'], check=True,
                       stdout=subprocess.DEVNULL)
    return directory


def freeze_for_reviewer(request_path, request):
    request_path = Path(request_path).resolve()
    stage = secure_directory(Path.home() / ('.frontend-review-' + uuid.uuid4().hex)).resolve()
    for item in request['review_files']:
        source = (request_path.parent / item['path']).resolve()
        destination = (stage / item['path']).resolve()
        if not source.is_relative_to(request_path.parent) or not destination.is_relative_to(stage):
            raise ValueError('Review file escapes bundle')
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Review bundle changed')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    (stage / 'request.json').write_bytes(canonical(request))
    return stage


def sign(request_path, private_path, issuer, reviewer, decision, hours):
    if not sys.stdin.isatty():
        raise ValueError('Run interactively under the approval account')
    request_path = Path(request_path).resolve()
    request = json.loads(request_path.read_text(encoding='utf-8-sig'))
    if request.get('schema') != 1 or request.get('audience') != 'codex-frontend-visual-v1' or not request.get('review_files'):
        raise ValueError('Invalid visual approval request')
    stage = freeze_for_reviewer(request_path, request)
    request_hash = hashlib.sha256(canonical(request)).hexdigest()
    print('Review screenshots, requirements and report in the private snapshot', stage / 'review')
    print('Task', request['task_id'], '\nRequest', request_hash, '\nDecision', decision)
    if input('After reviewing, type the full request hash to confirm: ').strip() != request_hash:
        raise ValueError('Approval cancelled')
    password = getpass.getpass('Private-key password: ').encode('utf-8')
    key = serialization.load_pem_private_key(Path(private_path).read_bytes(), password=password)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError('Ed25519 key required')
    now = int(time.time())
    payload = {'schema': 1, 'request_sha256': request_hash, 'issuer': issuer, 'reviewer': reviewer,
               'decision': decision, 'issued_at': now, 'expires_at': now + int(hours * 3600)}
    return {'payload': payload, 'signature': base64.b64encode(key.sign(DOMAIN + canonical(payload))).decode('ascii')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['keygen', 'sign'])
    parser.add_argument('--private-key', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--request')
    parser.add_argument('--issuer', default='local-review')
    parser.add_argument('--reviewer', default=getpass.getuser())
    parser.add_argument('--decision', choices=['approve', 'reject'], default='approve')
    parser.add_argument('--hours', type=float, default=24)
    args = parser.parse_args()
    if not sys.stdin.isatty() or not 0 < args.hours <= 24:
        parser.error('Interactive reviewer terminal required; validity must be within 24 hours')
    if Path(args.output).exists():
        parser.error('Output already exists')
    if args.command == 'keygen':
        if Path(args.private_key).exists():
            parser.error('Private key already exists')
        password = getpass.getpass('New private-key password: ')
        if not password or password != getpass.getpass('Repeat password: '):
            parser.error('Passwords must match and be nonempty')
        key = Ed25519PrivateKey.generate()
        private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.BestAvailableEncryption(password.encode('utf-8')))
        public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        result = {'schema': 1, 'issuer': args.issuer, 'reviewers': [args.reviewer],
                  'public_key': base64.b64encode(public).decode('ascii')}
        secure_directory(Path(args.private_key).resolve().parent)
        with Path(args.private_key).open('xb') as stream:
            stream.write(private)
    else:
        result = sign(args.request, args.private_key, args.issuer, args.reviewer, args.decision, args.hours)
    with Path(args.output).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(args.output)


if __name__ == '__main__':
    main()
