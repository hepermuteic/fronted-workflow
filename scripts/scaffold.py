"""Create missing work files from the actual task scope, preserving existing content."""
import argparse
import json
from pathlib import Path
import sys

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / 'scripts/engine'))
import verify as policy


def scaffold(root, style_document=None, adaptation=None):
    root = Path(root).resolve()
    task = policy.load(root / policy.TASK_PATH)
    templates = SKILL / 'assets/templates'
    created, preserved = [], []

    def create(name, value):
        path = policy.local(root, name, must_exist=False)
        if path.exists():
            preserved.append(name)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
        created.append(name)

    if bool(style_document) != bool(adaptation):
        raise ValueError('Provide both the complete style document and the project adaptation')
    if style_document:
        # External inputs are read-only. All generated files stay inside the project.
        source = Path(style_document).read_text(encoding='utf-8-sig')
        project = Path(adaptation).read_text(encoding='utf-8-sig')
        if 'Implementation Contract' not in source or not project.strip():
            raise ValueError('Complete Implementation Contract and project adaptation are required')
        create('design.md', source + '\n\n' + project)
    else:
        create('work/frontend-policy/project-adaptation.md', (templates / 'project-adaptation.md').read_text(encoding='utf-8'))
    create('work/frontend-policy/delivery-reflection.json', policy.load(templates / 'delivery-reflection.json'))
    cases = []
    for view in task.get('scope', []):
        case = policy.load(templates / 'browser-case.json')
        case.update({key: view[key] for key in ('page', 'width', 'state')})
        if view.get('root_selector'):
            case['root_selector'] = view['root_selector']
        cases.append(case)
    if task.get('visual'):
        create('work/frontend-policy/browser-spec.json', {'cases': cases})
    catalog = {item['id']: item for item in policy.rule_catalog()}
    applicable = [row['id'] for row in task.get('rule_application', []) if row.get('applicability') == 'applicable']
    entries = []
    for rule_id in applicable:
        entries.append({'id': 'rule:' + rule_id, 'source': catalog[rule_id]['text'], 'decision': '', 'implementation': [], 'condition': '',
                        'verification': {'check_id': 'visual', 'criterion': 'rule:' + rule_id}})
    for item in task.get('project_requirements', []):
        entries.append({'id': 'project:' + item['id'], 'decision': '', 'implementation': item.get('implementation', []), 'condition': '',
                        'verification': {'check_id': 'visual', 'criterion': 'project:' + item['id']}})
    create(task.get('checklist_plan') or 'work/frontend-policy/checklist-plan.json', {'schema': 1, 'entries': entries})
    criteria = list(dict.fromkeys(task.get('review_criteria', []) + [item['id'] for item in entries]))
    create('work/frontend-policy/review-observations.json', [{'criterion': criterion, 'location': '', 'observed': '', 'status': 'BLOCKED', 'evidence': [], 'implementation': [], 'condition': ''} for criterion in criteria])
    run = policy.load(templates / 'verification-run.json')
    run['commands'] = [{'id': item['id'], 'argv': item.get('command', [])} for item in task.get('checks', []) if item.get('type') == 'command' and item.get('required')]
    if not task.get('visual'):
        run.update(browser_spec=None, critic=False)
    create('work/frontend-policy/verification-run.json', run)
    return {'status': 'DRAFT', 'created': created, 'preserved': preserved,
            'pending_rule_ids': [row['id'] for row in task.get('rule_application', []) if row.get('applicability') == 'pending'],
            'next': 'Fill actual design decisions, applicability, commands, URLs and assertions; then run preflight.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--style-document', type=Path)
    parser.add_argument('--adaptation', type=Path)
    args = parser.parse_args()
    print(json.dumps(scaffold(args.root, args.style_document, args.adaptation), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
