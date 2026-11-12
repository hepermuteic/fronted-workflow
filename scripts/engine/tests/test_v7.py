"""Portable installation, safe scaffolding and actual command reuse regressions."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_verify as verify_tests

p = verify_tests.p

SCRIPTS = Path(__file__).resolve().parents[2]


def helper(name):
    spec = importlib.util.spec_from_file_location('v7_' + name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = helper('install')
scaffold = helper('scaffold')
cycle = helper('cycle')


class PackageTests(unittest.TestCase):
    def test_install_in_clean_user_path_and_repeat_without_changes(self):
        with tempfile.TemporaryDirectory(prefix='skill user space ') as temporary:
            user = Path(temporary)
            codex = user / '.codex'
            codex.mkdir()
            (codex / 'AGENTS.md').write_text('# Existing\n\nKeep my independent instructions.\n')
            (codex / 'hooks.json').write_text(json.dumps({'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'unrelated-command'}]}]}}))
            result = installer.install(installer.PACKAGE, user)
            again = installer.install(installer.PACKAGE, user)
            self.assertEqual(again['changed_files'], 0)
            self.assertIn('Keep my independent instructions.', (codex / 'AGENTS.md').read_text(encoding='utf-8'))
            self.assertIn('unrelated-command', (codex / 'hooks.json').read_text())
            target = Path(result['skill'])
            self.assertFalse((target / 'outputs').exists())
            self.assertFalse(any(target.rglob('__pycache__')))
            environment = {**os.environ, 'CODEX_HOME': str(codex), 'USERPROFILE': str(user), 'HOME': str(user), 'PYTHONUTF8': '1'}
            for entry in [target / 'scripts/verify.py', codex / 'frontend-policy/verify.py']:
                process = subprocess.run([sys.executable, str(entry), 'probe'], capture_output=True, text=True, encoding='utf-8', env=environment, check=True)
                probe = json.loads(process.stdout)
                self.assertEqual(Path(probe['skill']), target / 'SKILL.md')
                self.assertEqual(probe['version'], '7.0.0')
            catalog = subprocess.run([sys.executable, str(target / 'scripts/verify.py'), 'catalog'], capture_output=True, text=True, encoding='utf-8', env=environment, check=True)
            self.assertEqual(len(json.loads(catalog.stdout)), 111)
            script = "import sys;sys.path.insert(0,sys.argv[1]);import verify;print(verify.config()['version'])"
            imported = subprocess.run([sys.executable, '-c', script, str(codex / 'frontend-policy')], capture_output=True, text=True, encoding='utf-8', env=environment, check=True)
            self.assertEqual(imported.stdout.strip(), '7.0.0')


class WorkfileTests(unittest.TestCase):
    def setUp(self):
        self.fixture = verify_tests.PolicyTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        self.task = self.fixture.task('L2', visual=True, pages=['login'], widths=[390, 1280])
        self.scaffold_policy = patch.object(scaffold, 'policy', p)
        self.scaffold_policy.start()
        self.addCleanup(self.scaffold_policy.stop)
        self.cycle_policy = patch.object(cycle, 'policy', p)
        self.cycle_policy.start()
        self.addCleanup(self.cycle_policy.stop)

    def test_scope_templates_are_incomplete_and_existing_edits_survive(self):
        result = scaffold.scaffold(self.root)
        self.assertEqual(result['status'], 'DRAFT')
        spec = p.load(self.root / 'work/frontend-policy/browser-spec.json')
        self.assertEqual([row['width'] for row in spec['cases']], [390, 1280])
        self.assertTrue(all(row['page'] == 'login' and not row['steps'] for row in spec['cases']))
        observations = p.load(self.root / 'work/frontend-policy/review-observations.json')
        self.assertTrue(all(row['status'] == 'BLOCKED' and not row['observed'] for row in observations))
        target = self.root / 'work/frontend-policy/project-adaptation.md'
        target.write_text('My completed design content', encoding='utf-8')
        again = scaffold.scaffold(self.root)
        self.assertEqual(again['created'], [])
        self.assertEqual(target.read_text(), 'My completed design content')
        self.assertNotEqual(p.preflight_check(self.root, self.task)['status'], 'PASS')

    def test_complete_contract_keeps_exact_text_and_existing_design(self):
        source = self.root / 'source.md'
        adaptation = self.root / 'adaptation.md'
        original = '# Style\n\n## Implementation Contract\nFull contract text.\n'
        source.write_text(original)
        adaptation.write_text('# Project\nActual project detail.\n')
        scaffold.scaffold(self.root, source, adaptation)
        design = self.root / 'design.md'
        self.assertTrue(design.read_text().startswith(original))
        design.write_text('Existing user design')
        scaffold.scaffold(self.root, source, adaptation)
        self.assertEqual(design.read_text(), 'Existing user design')

    def test_scaffold_rejects_plan_outside_project(self):
        self.task['checklist_plan'] = '../escaped.json'
        p.save(self.root / p.TASK_PATH, self.task)
        with self.assertRaises(ValueError):
            scaffold.scaffold(self.root)
        self.assertFalse((self.root.parent / 'escaped.json').exists())

    def command_task(self):
        self.task = self.fixture.task('L2', visual=False, replace=True)
        argv = [sys.executable, '-c', 'print("executed check")']
        p.run_check(self.root, 'project-check', argv)
        self.task = p.load(self.root / p.TASK_PATH)
        return argv

    def test_command_reuse_binds_bytes_command_receipt_and_artifacts(self):
        argv = self.command_task()
        self.assertTrue(cycle.reusable_command(self.root, self.task, 'project-check', argv))
        self.assertFalse(cycle.reusable_command(self.root, self.task, 'project-check', argv + ['different']))
        (self.root / 'app.css').write_text('body {color:#1a4d3d}')
        self.assertFalse(cycle.reusable_command(self.root, self.task, 'project-check', argv))
        p.run_check(self.root, 'project-check', argv)
        self.task = p.load(self.root / p.TASK_PATH)
        record = p.load(self.root / self.task['evidence']['project-check'])
        (self.root / record['log']).write_text('edited output')
        self.assertFalse(cycle.reusable_command(self.root, self.task, 'project-check', argv))

    def test_cycle_reuses_valid_command_with_no_subprocess(self):
        argv = self.command_task()
        plan = 'run.json'
        p.save(self.root / plan, {'commands': [{'id': 'project-check', 'argv': argv}]})
        with patch.object(p, 'run_check', side_effect=AssertionError('Unnecessary command process')):
            result = cycle.run(self.root, plan)
        self.assertEqual(result['status'], 'READY_FOR_REVIEW')
        self.assertTrue(result['stages'][0]['reused'])

    def test_failed_command_stops_before_browser_and_model(self):
        self.task['checks'].append({'id': 'project-check', 'type': 'command', 'required': True})
        p.save(self.root / p.TASK_PATH, self.task)
        p.save(self.root / 'run.json', {'commands': [{'id': 'project-check', 'argv': [sys.executable, '-c', 'raise SystemExit(3)']}], 'browser_spec': 'missing.json', 'critic': True})
        with patch.object(p, 'run_browser', side_effect=AssertionError('Premature browser execution')):
            result = cycle.run(self.root, 'run.json')
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(len(result['stages']), 1)


if __name__ == '__main__':
    unittest.main()
