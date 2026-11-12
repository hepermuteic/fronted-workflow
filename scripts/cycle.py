"""Run one implementation batch through commands, browser capture and Critic."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent / 'engine'))
import verify as policy


def reusable_command(root, task, check_id, argv):
    try:
        item = policy.load(policy.local(root, task['evidence'][check_id]))
        if item.get('status') != 'PASS' or item.get('exit_code') != 0 or item.get('command') != argv:
            return False
        if not policy.execution_valid(root, task, item, 'command-process'):
            return False
        if item['source_hashes'] != policy.hashes(root, task, include_runtime=False):
            return False
        return bool(item.get('artifact_hashes')) and all(policy.sha(policy.local(root, name)) == value for name, value in item['artifact_hashes'].items())
    except (KeyError, ValueError, OSError, TypeError):
        return False


def run(root, plan_path, cli=None):
    root = Path(root).resolve()
    plan_file = policy.local(root, plan_path)
    plan = policy.load(plan_file)
    plan_hash = policy.sha(plan_file)
    task = policy.load(root / policy.TASK_PATH)
    required = {item['id'] for item in task['checks'] if item.get('required') and item['type'] == 'command'}
    commands = plan.get('commands', [])
    ids = [item['id'] for item in commands]
    if len(ids) != len(set(ids)) or set(ids) != required:
        raise ValueError('The run plan must cover each required command exactly once')
    if any(not isinstance(item.get('argv'), list) or not item['argv'] or any(not isinstance(arg, str) for arg in item['argv']) for item in commands):
        raise ValueError('Fill the actual command argument vectors before execution')
    build_id = task.get('deployment', {}).get('check_id')
    commands = sorted(commands, key=lambda item: item['id'] != build_id)
    initial_task_id = task['task_id']
    stages = []
    for command in commands:
        task = policy.load(root / policy.TASK_PATH)
        if task['task_id'] != initial_task_id or policy.sha(plan_file) != plan_hash:
            raise ValueError('Task or execution plan changed during the batch')
        reused = reusable_command(root, task, command['id'], command['argv'])
        record = {'status': 'PASS'} if reused else policy.run_check(root, command['id'], command['argv'])
        stages.append({'stage': command['id'], 'status': record['status'], 'reused': reused})
        if record['status'] != 'PASS':
            return {'status': record['status'], 'stages': stages, 'next': 'Repair the failed command before browser and Critic execution'}
    task = policy.load(root / policy.TASK_PATH)
    if task.get('visual'):
        if not plan.get('browser_spec'):
            raise ValueError('Visual tasks require the actual browser specification')
        browser = policy.run_browser(root, plan['browser_spec'])
        stages.append({'stage': 'browser', 'status': browser['status']})
        if browser['status'] != 'PASS':
            return {'status': browser['status'], 'stages': stages, 'next': 'Repair browser failures before Critic execution'}
        if plan.get('critic') is not True:
            raise ValueError('Visual implementation requires Critic')
        task = policy.load(root / policy.TASK_PATH)
        result = policy.critic.run(SimpleNamespace(**vars(policy)), root, task, cli)
        stages.append(result)
        if result['status'] != 'PASS':
            return {'status': result['status'], 'stages': stages, 'next': 'Implement the concrete Critic feedback as one revision'}
    if policy.load(root / policy.TASK_PATH)['task_id'] != initial_task_id or policy.sha(plan_file) != plan_hash:
        raise ValueError('Task or execution plan changed during the batch')
    return {'status': 'READY_FOR_REVIEW', 'stages': stages, 'next': 'Complete applicable independent review, final reflection, finalize and protected approval'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--plan', default='work/frontend-policy/verification-run.json')
    parser.add_argument('--cli')
    args = parser.parse_args()
    task_id = None
    try:
        task_id = policy.load(args.root / policy.TASK_PATH)['task_id']
        policy.save(args.root / policy.RESULT_PATH, {'status': 'BLOCKED', 'stage': 'cycle', 'task_id': task_id, 'blockers': ['Current execution batch has not completed']})
        result = run(args.root, args.plan, args.cli)
    except Exception as exc:
        result = {'status': 'BLOCKED', 'error': str(exc)}
    try:
        if task_id and policy.load(args.root / policy.TASK_PATH)['task_id'] == task_id:
            saved = {**result, 'task_id': task_id, 'stage': 'cycle'}
            if result['status'] == 'READY_FOR_REVIEW':
                saved['status'] = 'BLOCKED'
            policy.save(args.root / policy.RESULT_PATH, saved)
    except (OSError, ValueError, KeyError):
        pass
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return {'FAIL': 1, 'BLOCKED': 2}.get(result['status'], 0)


if __name__ == '__main__':
    raise SystemExit(main())
