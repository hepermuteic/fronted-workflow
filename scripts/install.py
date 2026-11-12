"""Install this self-contained Skill and its user-level integration."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PACKAGE = Path(__file__).resolve().parent.parent
ROOT_ITEMS = ('SKILL.md', 'CHANGELOG.md', 'agents', 'references', 'scripts', 'assets')
BEGIN = '<!-- frontend-workflow managed start -->'
END = '<!-- frontend-workflow managed end -->'


def package_files(source):
    for name in ROOT_ITEMS:
        item = source / name
        candidates = item.rglob('*') if item.is_dir() else [item]
        for path in candidates:
            if '__pycache__' in path.parts or path.suffix == '.pyc':
                continue
            if path.is_symlink():
                raise ValueError('Package symlinks require explicit resolution: ' + str(path))
            if path.is_file():
                yield path, path.relative_to(source)


def managed_agents(text, block):
    if BEGIN in text:
        start = text.index(BEGIN)
        end = text.index(END, start) + len(END)
        return text[:start] + block + text[end:]
    heading = '## Frontend Workflow Policy'
    if heading in text:
        start = text.index(heading)
        next_section = text.find('\n## ', start + len(heading))
        end = len(text) if next_section < 0 else next_section
        return text[:start] + block + text[end:]
    return text.rstrip() + '\n\n' + block + '\n'


def install(source, home, skills_dir=None, codex_dir=None, setup_tools=False):
    source, home = Path(source).resolve(), Path(home).resolve()
    target = (Path(skills_dir) if skills_dir else home / '.agents/skills') / 'frontend-workflow'
    target = target.resolve()
    codex = Path(codex_dir or home / '.codex').resolve()
    state = codex / 'frontend-policy'
    backup = state / 'install-backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    changed = []

    def write(path, data):
        path = Path(path)
        if path.exists() and path.read_bytes() == data:
            return
        if path.exists():
            saved = backup / (str(len(changed)) + '-' + path.name)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.install.tmp')
        temporary.write_bytes(data)
        os.replace(temporary, path)
        changed.append(str(path))

    # Read the complete package before replacing any installed file.
    payload = [(relative, path.read_bytes()) for path, relative in package_files(source)]
    if not any(str(relative) == 'SKILL.md' for relative, _ in payload):
        raise ValueError('Package is missing SKILL.md')
    for relative, data in payload:
        write(target / relative, data)
    write(state / 'installation.json', (json.dumps({'schema': 1, 'skill': str(target)}, indent=2) + '\n').encode())
    write(codex / 'agents/Critic.toml', (target / 'assets/agents/Critic.toml').read_bytes())
    wrapper = '''"""Compatibility entry for the installed frontend-workflow Skill."""
import json
from pathlib import Path
import sys
_installation = Path(__file__).resolve().parent / 'installation.json'
_skill = Path(json.loads(_installation.read_text(encoding='utf-8'))['skill'])
_engine = _skill / 'scripts/engine'
sys.path.insert(0, str(_engine))
__file__ = str(_engine / {name!r})
exec(compile(Path(__file__).read_bytes(), __file__, 'exec'), globals())
'''
    for file in (target / 'scripts/engine').glob('*.py'):
        if file.name not in {'paths.py', '__init__.py'}:
            write(state / file.name, wrapper.format(name=file.name).encode())
    for file in (target / 'scripts/engine').glob('*.cjs'):
        code = "const fs=require('fs'),path=require('path');\nconst skill=JSON.parse(fs.readFileSync(path.join(__dirname,'installation.json'),'utf8')).skill;\nmodule.exports=require(path.join(skill,'scripts/engine'," + json.dumps(file.name) + "));\n"
        write(state / file.name, code.encode())
    rules = target / 'references/frontend-design-rules.md'
    block = '\n'.join([
        BEGIN, '## Frontend Workflow Policy',
        '仅在用户明确调用 frontend-workflow 时启用工程工作流，覆盖当前任务及明确续作。',
        '普通前端任务仍完整读取原设计规则。小修改按影响范围执行，规范维护按维护范围执行。',
        'Skill 入口为 `' + (target / 'SKILL.md').as_posix() + '`。',
        '设计规则唯一来源为 `' + rules.as_posix() + '`。项目文件补充具体需求。',
        '真实检查、Critic 评分和适用批准共同决定交付，未验证内容据实报告。',
        'Hook 只跟随明确启用的任务，宿主信任与实际激活单独核实。', END])
    agents = codex / 'AGENTS.md'
    old = agents.read_text(encoding='utf-8-sig') if agents.exists() else '# Global Codex Instructions\n'
    write(agents, managed_agents(old, block).encode('utf-8'))
    pointer = '# 前端设计规则入口\n\n完整规则与版本维护在 [' + rules.name + '](' + rules.as_posix() + ')。\n开始前端任务时完整读取该文件，按实际版本执行。\n'
    write(codex / 'rules/frontend-design-rules.md', pointer.encode('utf-8'))
    hook_path = codex / 'hooks.json'
    hooks = json.loads(hook_path.read_text(encoding='utf-8-sig')) if hook_path.exists() else {'hooks': {}}
    hooks_changed = not hook_path.exists()
    command = subprocess.list2cmdline([sys.executable, str(state / 'verify.py'), 'hook'])
    for event, matcher in [('SessionStart', 'startup|resume|clear|compact|fork'), ('UserPromptSubmit', None), ('PostToolUse', 'apply_patch|Edit|Write'), ('Stop', None)]:
        groups = hooks.setdefault('hooks', {}).setdefault(event, [])
        owned = [item for group in groups for item in group.get('hooks', []) if 'frontend-policy/verify.py' in item.get('command', '').replace('\\', '/')]
        if owned:
            for item in owned:
                if str(state / 'verify.py').replace('\\', '/').lower() not in item['command'].replace('\\', '/').lower():
                    item.update(command=command, commandWindows=command)
                    hooks_changed = True
            continue
        item = {'type': 'command', 'command': command, 'commandWindows': command, 'timeout': 15}
        if event != 'Stop':
            item['additionalContextLimit'] = 600
        group = {'hooks': [item]}
        if matcher:
            group['matcher'] = matcher
        groups.append(group)
        hooks_changed = True
    if hooks_changed:
        write(hook_path, (json.dumps(hooks, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    if setup_tools:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(target / 'scripts/requirements.txt')], check=True)
        tooling = state / 'tooling'
        tooling.mkdir(parents=True, exist_ok=True)
        npm = shutil.which('npm.cmd') or shutil.which('npm')
        if not npm:
            raise ValueError('Node/npm is required to install the browser runner')
        subprocess.run([npm, 'install', '--prefix', str(tooling), 'playwright'], check=True)
        node = shutil.which('node')
        subprocess.run([node, str(tooling / 'node_modules/playwright/cli.js'), 'install', 'chromium'], check=True)
    return {'status': 'INSTALLED', 'skill': str(target), 'changed_files': len(changed), 'backup': str(backup) if backup.exists() else None,
            'next_check': [sys.executable, str(target / 'scripts/verify.py'), 'doctor'],
            'hook_activation': 'Requires actual host trust and lifecycle verification',
            'protected_approval': 'Use references/visual-approval.md to provision the separate approval identity'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--skills-dir', type=Path)
    parser.add_argument('--codex-dir', type=Path)
    parser.add_argument('--setup-tools', action='store_true')
    args = parser.parse_args()
    codex = args.codex_dir or (os.environ.get('CODEX_HOME') if args.home == Path.home() else None)
    result = install(PACKAGE, args.home, args.skills_dir, codex, args.setup_tools)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
