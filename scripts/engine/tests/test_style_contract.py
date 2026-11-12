import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_release import p,plan

spec=importlib.util.spec_from_file_location('stylekit_reader',p.SKILL/'scripts/stylekit.py')
reader=importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)

class StyleContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'index.html').write_text('Synthetic fixture')
        self.task=plan(self.root,level='L3')
        self.task['design_plan']['selected_style']='A'

    def test_matching_complete_document_is_accepted(self):
        self.assertEqual(p.preflight.style_contract_gaps(p,self.root,self.task),[])

    def test_source_hash_change_blocks(self):
        (self.root/'style-source.md').write_text('Changed source')
        self.assertTrue(p.preflight.style_contract_gaps(p,self.root,self.task))

    def test_summary_cannot_replace_complete_document(self):
        (self.root/'design.md').write_text('Summary only')
        self.assertTrue(any('complete StyleKit' in x for x in p.preflight.style_contract_gaps(p,self.root,self.task)))

    def test_selected_slug_and_language_are_bound(self):
        for field in ('style_slug','document_locale'):
            original=self.task['design_plan'][field]
            self.task['design_plan'][field]='another'
            self.assertTrue(p.preflight.style_contract_gaps(p,self.root,self.task))
            self.task['design_plan'][field]=original
        self.task['design_plan']['selected_style']='B'
        self.assertTrue(p.preflight.style_contract_gaps(p,self.root,self.task))

    def test_contract_document_changes_preflight_fingerprint(self):
        before=p.preflight.contract(self.task,self.root)
        (self.root/'style-source.md').write_text('Changed')
        self.assertNotEqual(before,p.preflight.contract(self.task,self.root))

    def test_downloads_requested_chinese_document(self):
        content='# 中文风格\n### Implementation Contract\n按范围制作。\n'
        with patch.object(reader.urllib.request,'urlopen',return_value=io.BytesIO(content.encode('utf-8'))) as request:
            text,metadata=reader.fetch_document('editorial','zh-CN')
        self.assertEqual(text,content)
        self.assertEqual(metadata['locale'],'zh')
        self.assertIn('locale=zh',request.call_args.args[0].full_url)

    def test_wrong_language_and_incomplete_response_are_rejected(self):
        for content in ('<html>Error</html>','# English\n### Implementation Contract\nKeep scope.','# 中文摘要'):
            with patch.object(reader.urllib.request,'urlopen',return_value=io.BytesIO(content.encode('utf-8'))):
                with self.assertRaises(ValueError):reader.fetch_document('editorial','zh')

    def test_invalid_slug_and_unsupported_locale_are_rejected(self):
        for slug,locale in (('../other','zh'),('editorial','unknown')):
            with self.assertRaises(ValueError):reader.fetch_document(slug,locale)

if __name__=='__main__':unittest.main()
