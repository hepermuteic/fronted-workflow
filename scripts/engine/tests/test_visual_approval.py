"""Signature and revision-binding regressions. Keys are temporary test fixtures."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visual_approval as approval
import approval_signer
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.key=Ed25519PrivateKey.generate()
        public=self.key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self.trust={'schema':1,'issuer':'test-review','reviewers':['test-human'],
                    'public_key':base64.b64encode(public).decode('ascii')}
        self.trust_patch=patch.object(approval,'load_trust',return_value=self.trust)
        self.trust_patch.start()
        self.addCleanup(self.trust_patch.stop)
        self.api=SimpleNamespace(load=lambda p:json.loads(Path(p).read_text()),
                                 local=lambda root,name:Path(root)/name)
        self.current={'schema':1,'audience':'codex-frontend-visual-v1','task_id':'test-task',
                      'policy_hash':'test-policy','source_hashes':{'page.html':'current'},
                      'evidence_hashes':{'screenshot.png':'current'}}
        self.binding_patch=patch.object(approval,'request_body',side_effect=lambda *args:dict(self.current))
        self.binding_patch.start()
        self.addCleanup(self.binding_patch.stop)
        (self.root/'request.json').write_text(json.dumps(self.current))
        self.task={'visual_approval':{'request':'request.json','receipt':'receipt.json'}}
        self.payload={'schema':1,'request_sha256':approval.digest(self.current),
                      'issuer':'test-review','reviewer':'test-human','decision':'approve',
                      'issued_at':int(time.time())-1,'expires_at':int(time.time())+3600}
        self.write_receipt()

    def write_receipt(self,key=None):
        signature=(key or self.key).sign(approval.DOMAIN+approval.canonical(self.payload))
        (self.root/'receipt.json').write_text(json.dumps({'payload':self.payload,'signature':base64.b64encode(signature).decode('ascii')}))

    def result(self):
        return approval.verify(self.api,self.root,self.task)

    def test_valid_signature(self):
        self.assertEqual(self.result()['status'],'APPROVED')

    def test_forged_key(self):
        self.write_receipt(Ed25519PrivateKey.generate())
        self.assertEqual(self.result()['status'],'BLOCKED')

    def test_stale_inputs(self):
        for field in ['policy_hash','source_hashes','evidence_hashes','task_id']:
            with self.subTest(field=field):
                old=self.current[field]
                self.current[field]='changed'
                self.assertEqual(self.result()['status'],'BLOCKED')
                self.current[field]=old

    def test_signature_cannot_be_reused_on_another_request(self):
        self.payload['request_sha256']='another-request'
        self.write_receipt()
        self.assertEqual(self.result()['status'],'BLOCKED')

    def test_expired_future_and_excessive_validity(self):
        now=int(time.time())
        for issued,expires in [(now-200,now-1),(now+100,now+200),(now-1,now+90000)]:
            self.payload.update(issued_at=issued,expires_at=expires)
            self.write_receipt()
            self.assertEqual(self.result()['status'],'BLOCKED')

    def test_wrong_reviewer_or_issuer(self):
        for field in ['reviewer','issuer']:
            previous=self.payload[field]
            self.payload[field]='agent-self-review'
            self.write_receipt()
            self.assertEqual(self.result()['status'],'BLOCKED')
            self.payload[field]=previous

    def test_signed_rejection(self):
        self.payload['decision']='reject'
        self.write_receipt()
        self.assertEqual(self.result()['status'],'REJECTED')

    def test_payload_edit_breaks_signature(self):
        receipt=json.loads((self.root/'receipt.json').read_text())
        receipt['payload']['decision']='reject'
        (self.root/'receipt.json').write_text(json.dumps(receipt))
        self.assertEqual(self.result()['status'],'BLOCKED')

    def test_missing_or_writable_trust_store_blocks(self):
        with patch.object(approval,'load_trust',side_effect=ValueError('Unprotected store')):
            self.assertEqual(self.result()['status'],'BLOCKED')

    def test_signer_rejects_background_execution(self):
        with patch('sys.stdin.isatty',return_value=False):
            with self.assertRaises(ValueError):
                approval_signer.sign('unused','unused','issuer','reviewer','approve',24)

    def test_private_snapshot_preserves_reviewed_bytes(self):
        source=self.root/'source'
        source.mkdir()
        (source/'image.png').write_bytes(b'reviewed image fixture')
        request={'review_files':[{'path':'image.png','sha256':hashlib.sha256(b'reviewed image fixture').hexdigest()}]}
        stage=self.root/'private-snapshot'
        stage.mkdir()
        with patch.object(approval_signer,'secure_directory',return_value=stage):
            approval_signer.freeze_for_reviewer(source/'request.json',request)
        (source/'image.png').write_bytes(b'changed source fixture')
        self.assertEqual((stage/'image.png').read_bytes(),b'reviewed image fixture')
        with patch.object(approval_signer,'secure_directory',return_value=stage):
            with self.assertRaises(ValueError):approval_signer.freeze_for_reviewer(source/'request.json',request)


if __name__=='__main__':
    unittest.main()
