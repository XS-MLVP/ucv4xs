"""Design-independent issue records and generated documentation indexes. MPL-2.0."""
import json
from contextlib import nullcontext
import os
from pathlib import Path
import re

from .common import UcvError, contained, file_hash, lock

START = '<!-- ucv:bugs:start -->'
END = '<!-- ucv:bugs:end -->'
BLOCK = re.compile(r'^```ucv-bug[ \t]*\n(.*?)^```[ \t]*$', re.M | re.S)
WORK_START = '<!-- ucv:work-index:start -->'
WORK_END = '<!-- ucv:work-index:end -->'


def binding_observation(entry, baseline, top):
    """Render a recorded asset observation, never a live acceptance verdict."""
    binding=entry.get('binding',{})
    if not isinstance(binding,dict) or not binding.get('observed_baseline'):
        return '未登记接入观察；查合同与运行证据'
    observed=binding['observed_baseline']
    if observed!=baseline:
        return f'旧基线观察 {observed}；当前需重核'
    if binding.get('observed_top')!=top:
        return '观察 top 与当前配方不符或未登记；需重核'
    if binding.get('availability')=='absent':
        return '当前 top 缺失；历史资产待重新定界'
    return {'scaffold':'骨架；合同与环境待实现',
            'existing-unrevalidated':'已有资产；本基线待复验'}.get(
                binding.get('verification_state'),'接入状态未登记；查合同与运行证据')


def work_index(suite, meta):
    """A generated navigation list inside the existing verification spec."""
    from .layout import testbench_path
    base=suite.path/'docs/spec/verification'

    def link(value, label):
        relative=Path(os.path.relpath(contained(suite.path,value),base)).as_posix()
        return f'[{label}]({relative})'

    lines=[WORK_START, '', '## DUT 工作索引', '',
           '由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。',
           f'当前工程基线：`{suite.baseline["name"]}`。接入观察不代表验证进度或验收结果。', '',
           '负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；',
           ('未认领不推断负责人；各 DUT 独立实现、选跑与验收。' if meta['schema']==2 else
            '未认领不推断负责人，共用 testbench 的 DUT 仍分别验收。'), '',
           '| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |', '|---|---|---|---|']
    for dut,spec in suite.recipe['duts'].items():
        entry=meta['duts'].get(dut,{})
        contracts=entry.get('verification_spec',[])
        contracts=contracts if isinstance(contracts,list) else [contracts]
        contract=link(contracts[0],'范围、工作与完成条件') if contracts else '待登记'
        entrance=link(testbench_path(dut,entry,meta['schema'])+'/README.md','实现、用例与命令')
        state=binding_observation(entry,suite.baseline['name'],spec['top']).replace('|','\\|').replace('\n',' ')
        lines.append(f'| `{dut}` / `{spec["top"]}` | {state} | {contract} | {entrance} |')
    return '\n'.join([*lines,'',WORK_END])


def refresh_work_index(project, suite, meta, write=False):
    path=suite.path/'docs/spec/verification/README.md'
    with lock(project.root/'.cache/locks'/('documents-'+suite.name)) if write else nullcontext():
        original=path.read_text() if path.is_file() else '# 验证规格\n'
        block=work_index(suite,meta)
        if WORK_START in original or WORK_END in original:
            if (original.count(WORK_START)!=1 or original.count(WORK_END)!=1
                    or original.index(WORK_END)<original.index(WORK_START)):
                raise UcvError(f'{path}: invalid generated work index markers')
            before,rest=original.split(WORK_START)
            _,after=rest.split(WORK_END)
            expected=before+block+after
        else:
            if original.startswith('# '):
                title,_,body=original.partition('\n')
                expected=title+'\n\n'+block+'\n'+body
            else:
                expected=block+'\n\n'+original
        changed=expected!=original
        if write and changed:
            path.parent.mkdir(parents=True,exist_ok=True)
            temporary=path.with_suffix('.md.tmp')
            temporary.write_text(expected)
            temporary.replace(path)
        return {'path':str(path),'current':not changed or write,'updated':changed and write,
                'objects':len(suite.recipe['duts']),'markdown':expected}


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
