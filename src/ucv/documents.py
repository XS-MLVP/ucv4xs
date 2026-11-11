"""Design-independent issue records and generated documentation indexes. MPL-2.0."""
import json
from contextlib import nullcontext
from pathlib import Path
import re

from .common import UcvError, contained, file_hash, lock

START = '<!-- ucv:bugs:start -->'
END = '<!-- ucv:bugs:end -->'
BLOCK = re.compile(r'^```ucv-bug[ \t]*\n(.*?)^```[ \t]*$', re.M | re.S)


def strings(value):
    return isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)


def issues(suite):
    """One Markdown record per stable ID; the directory owns current state."""
    root = suite.path / 'docs/bugs'
    rows, seen = [], set()
    for state in ('open', 'closed'):
        for path in sorted((root / state).rglob('*.md')):
            if path.name == 'README.md':
                continue
            contained(suite.path,str(path.relative_to(suite.path)))
            blocks = BLOCK.findall(path.read_text())
            if len(blocks) != 1:
                raise UcvError(f'{path}: expected exactly one ucv-bug JSON block')
            try:
                row = json.loads(blocks[0])
            except ValueError as error:
                raise UcvError(f'{path}: invalid ucv-bug JSON: {error}') from error
            if (not isinstance(row, dict)
                    or not isinstance(row.get('id'), str)
                    or not re.fullmatch(r'[A-Za-z0-9][\w.-]*', row['id'])
                    or not isinstance(row.get('title'), str) or not row['title'].strip()
                    or not isinstance(row.get('kind'),str)
                    or row.get('kind') not in {'rtl', 'verification', 'spec', 'investigation'}):
                raise UcvError(f'{path}: bug needs id, title and kind (rtl/verification/spec/investigation)')
            if row['id'] in seen:
                raise UcvError(f'{suite.name}: duplicate bug ID: {row["id"]}')
            seen.add(row['id'])
            if 'state' in row or 'status' in row:
                raise UcvError(f'{path}: current state belongs to the open/closed directory')
            versions = row.get('versions', [])
            if not isinstance(versions, list):
                raise UcvError(f'{path}: versions must be a list')
            for version in versions:
                if (not isinstance(version, dict) or not isinstance(version.get('baseline'), str)
                        or not version['baseline'].strip()
                        or not isinstance(version.get('status'),str)
                        or version.get('status') not in {'open', 'closed', 'unverified'}
                        or not strings(version.get('evidence', []))):
                    raise UcvError(f'{path}: invalid baseline status/evidence')
                if version['status'] == 'closed' and not version.get('evidence'):
                    raise UcvError(f'{path}: a closed baseline needs verification evidence')
            if state == 'closed':
                resolution = row.get('resolution', {})
                if (not isinstance(resolution, dict)
                        or not isinstance(resolution.get('reason'),str)
                        or resolution.get('reason') not in {'fixed', 'invalid', 'duplicate', 'retired'}
                        or not strings(resolution.get('evidence')) or not resolution['evidence']
                        or not isinstance(resolution.get('note'), str) or not resolution['note'].strip()):
                    raise UcvError(f'{path}: closed bug needs resolution reason, evidence and note')
            rows.append({**row, 'state': state, 'path': str(path.relative_to(suite.path)),
                         'sha256': file_hash(path)})
    return sorted(rows, key=lambda r: r['id'])


def issue_index(rows, baseline=None):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')

    lines = [START, '', '由 `ucv docs --write` 生成；目录表示当前处理状态，版本结论见各记录。', '']
    if rows and baseline:
        lines += [f'当前工程基线：`{baseline}`。未复验项不继承历史通过结论。', '']
    for state, title in (('open', '未解决'), ('closed', '已关闭')):
        selected = [r for r in rows if r['state'] == state]
        lines += [f'## {title}（{len(selected)}）', '']
        if not selected:
            lines += ['暂无登记条目。', '']
            continue
        lines += ['| ID | 问题 | 类型 | 本基线结论 | 关闭原因 |', '|---|---|---|---|---|']
        for row in selected:
            link = Path(row['path']).relative_to('docs/bugs').as_posix()
            version=next((v for v in reversed(row.get('versions',[])) if v['baseline']==baseline),None)
            verdict={'open':'未解决','closed':'已处置','unverified':'未复验'}.get(
                version['status'] if version else None, '未登记复验')
            lines.append(f"| [{row['id']}]({link}) | {cell(row['title'])} | {row['kind']} | "
                         f"{verdict} | "
                         f"{cell(row.get('resolution', {}).get('reason', '—')) if state == 'closed' else '—'} |")
        lines.append('')
    return '\n'.join([*lines, END])


def refresh_index(project, suite, write=False):
    path = suite.path / 'docs/bugs/README.md'
    with lock(project.root / '.cache/locks' / ('documents-' + suite.name)) if write else nullcontext():
        rows = issues(suite)
        block = issue_index(rows,suite.baseline['name'])
        original = path.read_text() if path.is_file() else '# 问题汇总\n\n'
        if START in original or END in original:
            if original.count(START) != 1 or original.count(END) != 1 or original.index(END) < original.index(START):
                raise UcvError(f'{path}: invalid generated index markers')
            before, rest = original.split(START)
            _, after = rest.split(END)
            expected = before + block + after
        else:
            expected = original.rstrip() + '\n\n' + block + '\n'
        changed = expected != original
        if write and changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.md.tmp')
            temporary.write_text(expected)
            temporary.replace(path)
        return {'suite': suite.name, 'path': str(path), 'issues': rows,
                'index_current': not changed or write, 'updated': changed and write,
                'markdown': expected}


def compare_issues(previous, current):
    """Compare frozen run declarations, never infer a hardware fix from a PASS."""
    before = {s['suite']: s for s in previous}
    after = {s['suite']: s for s in current}
    old, new, unavailable = {}, {}, []
    for name in sorted(before.keys() | after.keys()):
        if 'bugs' not in before.get(name, {}) or 'bugs' not in after.get(name, {}):
            unavailable.append(name)
            continue
        old.update({name + '::' + r['id']: r for r in before[name]['bugs']})
        new.update({name + '::' + r['id']: r for r in after[name]['bugs']})
    common = old.keys() & new.keys()
    return {'unavailable_suites': unavailable, 'added': sorted(new.keys() - old.keys()),
            'removed': sorted(old.keys() - new.keys()),
            'closed': sorted(k for k in common if old[k]['state'] == 'open' and new[k]['state'] == 'closed'),
            'reopened': sorted(k for k in common if old[k]['state'] == 'closed' and new[k]['state'] == 'open'),
            'updated': sorted(k for k in common if old[k] != new[k]),
            'scope': 'record changes only; consult baseline, verification source and run selection'}
