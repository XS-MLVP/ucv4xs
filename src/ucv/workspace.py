"""Human-readable workspaces derived from recipes, without native imports. MPL-2.0."""
from pathlib import Path
import keyword
import re
import shlex
from urllib.parse import quote, unquote

from .common import UcvError, contained, lock, read, write
from .sources import source_key
from .layout import layout_names, testbench_name, testbench_path, problems, refresh_readmes, relocated


def metadata(suite):
    path = suite.path / 'workspace.json'
    value = read(path) if path.is_file() else {'schema': 1, 'duts': {}}
    if not isinstance(value,dict) or not isinstance(value.get('duts'), dict):
        raise UcvError('Invalid workspace.json: ' + str(path))
    layout_names(value)
    if set(value['duts']) - set(suite.recipe['duts']):
        raise UcvError('workspace.json contains unknown DUTs: ' + suite.name)
    for role in ('fixtures','loader'):
        if role in value and (not isinstance(value[role],str) or not value[role]):
            raise UcvError('Invalid workspace '+role+': '+suite.name)
    for key, row in value['duts'].items():
        if not isinstance(row,dict):
            raise UcvError(f'{suite.name}/{key}: workspace entry must be an object')
        testbench_name(key,row,value['schema'])
        for role in ('design_spec','verification_spec','environment','chisel','tests'):
            if role not in row:continue
            paths = row[role]
            if isinstance(paths,str) and role not in {'chisel','tests'}:paths=[paths]
            if not isinstance(paths,list) or any(not isinstance(p,str) or not p for p in paths):
                raise UcvError(f'{suite.name}/{key}: invalid {role} paths')
        if 'smoke' in row and (not isinstance(row['smoke'],str) or not row['smoke']):
            raise UcvError(f'{suite.name}/{key}: invalid smoke nodeid')
    if value['schema']==2:
        for key in suite.recipe['duts']:
            testbench_name(key,value['duts'].get(key,{}),value['schema'])
    return value


def selected_duts(suite, duts=None):
    keys = list(dict.fromkeys(duts or suite.recipe['duts']))
    for key in keys:
        if key not in suite.recipe['duts']:
            raise UcvError(f'Unknown DUT {suite.name}/{key}')
    return keys


def test_roots(suite, duts):
    meta = metadata(suite)
    rows = meta['duts']
    roots = []
    for key in selected_duts(suite, duts):
        entry=rows.get(key,{})
        values = entry.get('tests', [testbench_path(key,entry,meta['schema'])+'/tests'])
        if not values or not isinstance(values, list):
            raise UcvError(f'{suite.name}/{key}: declare tests in workspace.json')
        for value in values:
            path = contained(suite.path, value)
            if not path.exists():
                raise UcvError(f'{suite.name}/{key}: missing test path {value}; declare it in workspace.json')
            roots.append(path)
    if meta['schema']==2:
        shared=contained(suite.path,'testbenches/shared/tests')
        if shared.is_dir():roots.append(shared)
    return list(dict.fromkeys(roots))


def source_url(baseline, relative):
    """A source file belongs to its deepest locked submodule, or the root repo."""
    path = Path(relative)
    owner = baseline
    for entry in sorted(baseline['recursive_submodules'],
                        key=lambda row: len(Path(row['path']).parts), reverse=True):
        if path.is_relative_to(entry['path']):
            owner = entry
            path = path.relative_to(entry['path'])
            break
    repository = owner['repository'].removesuffix('.git')
    return f"{repository}/blob/{owner['commit']}/{quote(path.as_posix(), safe='/')}"


def info(project, suite, duts=None):
    meta = metadata(suite)
    _,field=layout_names(meta)
    source = project.root / '.cache/sources' / source_key(suite.baseline)
    rows = []
    for key in selected_duts(suite, duts):
        spec = suite.recipe['duts'][key]
        entry = meta['duts'].get(key, {})
        resources = {}
        base=testbench_path(key,entry,meta['schema'])
        environments=[base+'/env/agent/main.py',base+'/env/agent.py',base+'/env/__init__.py',base+'/env.py']
        defaults = {'environment':next((p for p in environments if (suite.path/p).is_file()),base+'/env.py'),
                    'tests': [base+'/tests']}
        resources[field]=[{'path':str(suite.path/base/'README.md'),'exists':(suite.path/base/'README.md').is_file()}]
        shared=suite.path/'testbenches/shared'
        if meta['schema']==2 and shared.is_dir():
            resources['shared']=[{'path':str(shared/'README.md'),'exists':(shared/'README.md').is_file()}]
        for role, folder in (('design_spec','design'),('verification_spec','verification')):
            candidates=[f'docs/spec/{folder}/{key}.md',f'docs/spec/{folder}/README.md']
            defaults[role]=next((p for p in candidates if (suite.path/p).is_file()),None)
        for role in ('fixtures','loader'):
            if meta.get(role):
                path=contained(suite.path,meta[role])
                resources[role]=[{'path':str(path),'exists':path.is_file()}]
        for role in ('design_spec', 'verification_spec', 'environment', 'tests'):
            values = entry.get(role, defaults.get(role))
            if values is None:
                resources[role] = []
                continue
            values = values if isinstance(values, list) else [values]
            resources[role] = [{'path': str(contained(suite.path, value)),
                                'exists': contained(suite.path, value).exists()} for value in values]
        chisel = []
        for value in entry.get('chisel', []):
            local = contained(source, value)
            chisel.append({'path': str(local), 'exists': local.is_file(),
                           'url': source_url(suite.baseline, value)})
        resources['chisel'] = chisel
        base = project.root / '.cache/duts' / project.cache_key(suite, key)
        for role, path in [('rtl', base/'rtl'/(spec['top']+'.sv')),
                           ('dut_python', base/'dut/__init__.py')]:
            resources[role] = [{'path': str(path), 'exists': path.is_file()}]
        prefix = './scripts/ucv'
        target = f'{suite.name} --dut {key}'
        commands = {'source': f'{prefix} prepare {suite.name} --source-only',
                    'prepare': f'{prefix} prepare {target} --rtl-source release',
                    'build': f'{prefix} build {target} --jobs 2',
                    'run': f'{prefix} run {target} --workers 1'}
        registry=project.root/'baselines/rtl-releases.json'
        if not registry.is_file() or suite.baseline['name'] not in read(registry).get('releases',{}):
            commands['prepare']=f'{prefix} prepare {target} --rtl-source source'
            commands['build']+=' --rtl-source source'
        if entry.get('smoke'):
            commands['smoke'] = commands['run'] + ' -- ' + shlex.quote(entry['smoke'])
        rows.append({'dut': key, field:testbench_name(key,entry,meta['schema']), **spec, 'resources': resources, 'commands': commands})
    documents={role:str(suite.path/path) for role,path in
               [('overview','docs/README.md'),('bugs','docs/bugs/README.md')]
               if (suite.path/path).is_file()}
    return {**suite.summary(), 'path': str(suite.path), 'documents':documents, 'duts': rows}


def markdown(value):
    lines = [f"# {value['suite']}", '', f"Baseline: {value['baseline']} / {value['design_config']}",
              f"Source: {value['commit']}", f"Workspace: {value['path']}", '']
    for role,path in value.get('documents',{}).items():
        lines.append(f'- {role}: [{path}]({Path(path).as_uri()})')
    lines.append('')
    for row in value['duts']:
        lines += [f"## {row['dut']} ({row['top']} → {row['export_name']})", '']
        for role, resources in row['resources'].items():
            if not resources:
                lines.append(f'- {role}: 待在 workspace.json 登记')
            for resource in resources:
                label = '已存在' if resource['exists'] else '尚未准备'
                lines.append(f"- {role} [{label}]: [{resource['path']}]({Path(resource['path']).as_uri()})")
                if resource.get('url'):
                    lines.append(f"  - [固定版本源码]({resource['url']})")
        lines += ['', '```sh', *row['commands'].values(), '```', '']
    return '\n'.join(lines)


def check(project, suites):
    """Structural checks only; never mark design or verification semantics approved."""
    errors, notices, inventory = [], [], []
    bug_records=[]
    for suite in suites:
        value = info(project, suite)
        meta=metadata(suite)
        _,field=layout_names(meta)
        errors.extend(f'{suite.name}: {error}' for error in problems(suite,meta))
        for page in refresh_readmes(project,suite,meta):
            if not page['current']:errors.append(f"{suite.name}/{page[field]}: stale {field} README; run ucv docs {suite.name} --write")
        declared = meta['duts']
        source = project.root / '.cache/sources' / source_key(suite.baseline)
        source_available = source.is_dir()
        if not source_available and any(row['resources']['chisel'] for row in value['duts']):
            notices.append(f'{suite.name}: source checkout unavailable; chisel paths not checked locally: {source}')
        if (suite.path/'docs').is_dir():
            for entry in ('docs/README.md','docs/spec/design/README.md',
                          'docs/spec/verification/README.md','docs/bugs/README.md'):
                if not (suite.path/entry).is_file():
                    errors.append(f'{suite.name}: missing documentation entry: {entry}')
        for row in value['duts']:
            for role in ('fixtures','loader'):
                for resource in row['resources'].get(role,[]):
                    if not resource['exists']:errors.append(f"{suite.name}: missing {role}: {resource['path']}")
            for role in ('design_spec', 'verification_spec', 'environment', 'tests'):
                if not row['resources'][role]:
                    notices.append(f"{suite.name}/{row['dut']}: {role} 未登记")
                for resource in row['resources'][role]:
                    if not resource['exists']:
                        destination = errors if role in declared.get(row['dut'],{}) else notices
                        destination.append(f"{suite.name}/{row['dut']}: missing {role}: {resource['path']}")
            if not row['resources']['chisel']:
                notices.append(f"{suite.name}/{row['dut']}: chisel 未登记")
            elif source_available:
                for resource in row['resources']['chisel']:
                    if not resource['exists']:
                        errors.append(f"{suite.name}/{row['dut']}: missing chisel in source checkout: {resource['path']}")
            smoke = declared.get(row['dut'], {}).get('smoke')
            if smoke:
                path = contained(suite.path, smoke.split('::')[0])
                roots = test_roots(suite, [row['dut']])
                if not path.is_file() or not any(path.resolve().is_relative_to(p.resolve()) for p in roots):
                    errors.append(f"{suite.name}/{row['dut']}: smoke is missing or outside selected tests")
        for legacy in (suite.path/'docs/bugs').glob('*.md'):
            if legacy.name!='README.md':
                notices.append(f'{suite.name}: unclassified issue/support page: {legacy.relative_to(suite.path)}')
        from .documents import refresh_index
        try:
            result=refresh_index(project,suite)
            bug_records.append({'suite':suite.name,'issues':result['issues']})
            if (suite.path/'docs/bugs/README.md').is_file() and not result['index_current']:
                errors.append(f'{suite.name}: stale bug index; run ucv docs {suite.name} --write')
        except UcvError as error:
            errors.append(str(error))
    for root in [project.root, *[s.path for s in suites]]:
        navigation = root / 'docs/navigation.json'
        config=read(navigation) if navigation.is_file() else {'schema':1,'current':[]}
        if not isinstance(config,dict):
            errors.append('Invalid document navigation: '+str(navigation));continue
        current=config.get('current', [])
        if config.get('schema')!=1 or not isinstance(current,list) or any(not isinstance(p,str) for p in current):
            errors.append('Invalid document navigation: '+str(navigation));continue
        relocations=config.get('relocations',{})
        if (not isinstance(relocations,dict)
                or any(not isinstance(p,str) or not p or not isinstance(q,str) or not q
                       for p,q in relocations.items())):
            errors.append('Invalid document relocations: '+str(navigation));relocations={}
        for original,destination in relocations.items():
            contained(root,original)
            if not contained(root,destination).is_file():
                errors.append(f'{navigation}: missing relocated document: {destination}')
        if root != project.root:
            suite=next(s for s in suites if s.path==root)
            _,field=layout_names(metadata(suite))
            resources=[str(Path(r['path']).relative_to(root)) for row in info(project,suite)['duts']
                       for role in ('design_spec','verification_spec',field,'shared') for r in row['resources'].get(role,[])]
            bug_paths=[r['path'] for s in bug_records if s['suite']==suite.name for r in s['issues']]
            current=list(dict.fromkeys([*current,*resources,*bug_paths]))
        for name in current:
            path = contained(root, name)
            if not path.is_file():
                errors.append('Missing current document: ' + str(path))
                continue
            text = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)
            for target in re.findall(r'\]\(([^\s)]+)\)', text):
                if '://' in target or target.startswith(('#', 'mailto:')):
                    continue
                target = unquote(target.split('#')[0])
                resolved=(path.parent/target).resolve()
                if target and not resolved.exists():
                    if resolved.is_relative_to(root) and relocated(root,str(resolved.relative_to(root))).exists():
                        notices.append(f'{name}: historical path relocated: {target}')
                        continue
                    parts=set(Path(target).parts)
                    generated={'.cache','.tools','.venv','.history','.ucv','results','rtl','dut','XiangShan','XiangShan-internal'}
                    if parts & generated:
                        notices.append(f'{name}: evidence/generated resource unavailable: {target}')
                    else:
                        errors.append(f'{name}: missing local link: {target}')
        pages = {str(p.relative_to(root)) for p in (root/'docs').rglob('*.md')}
        inventory.append({'root': str(root), 'current': current,
                          'unindexed': sorted(pages-set(current)), 'relocations':relocations})
    return {'status': 'FAIL' if errors else 'PASS', 'scope': 'structure-only',
            'errors': errors, 'notices': notices, 'documents': inventory, 'bugs':bug_records}


def initialize(project, name, group, dut, top, export_name):
    """Create a real suite skeleton; existing directories are never overwritten."""
    for label, value in [('suite',name), ('group',group), ('dut',dut), ('top',top), ('export_name',export_name)]:
        if not value or not re.fullmatch(r'[A-Za-z_]\w*', value) or keyword.iskeyword(value):
            raise UcvError(f'{label} must be an explicit identifier')
    with lock(project.root/'.cache/locks/init'):
        config = read(project.root/'ucv.json')
        existing = name in config['suites']
        path = contained(project.root, config['suites'][name] if existing else f'suites/{group}/{name}')
        if existing and path.parent.name != group:
            raise UcvError('Existing suite belongs to another group')
        if not existing and path.exists():
            raise UcvError('Refusing to overwrite existing directory: '+str(path))
        recipe = read(path/'ucv.json') if existing else {
            'schema':1,'suite':name,'generation':'soc','closure':'module-dependencies',
            'duts':{},'pytest_root':'.','tests':['testbenches'],'process_isolation':'suite'}
        workspace = metadata(project.suite(name)) if existing else {'schema':2,'fixtures':'conftest.py','duts':{}}
        directory,field=layout_names(workspace)
        base=testbench_path(dut,{field:dut},workspace['schema'])
        if dut in recipe['duts']:
            raise UcvError('DUT already exists: '+name+'/'+dut)
        navigation=path/'docs/navigation.json'
        nav=read(navigation) if navigation.is_file() else {'schema':1,'current':[]}
        if (nav.get('schema')!=1 or not isinstance(nav.get('current'),list)
                or any(not isinstance(p,str) for p in nav['current'])):
            raise UcvError('Invalid document navigation: '+str(navigation))
        files = {
            f'{base}/__init__.py':'',
            f'{base}/tests/__init__.py':'',
            f'{base}/transactions.py':'"""Define typed requests and observations from the reviewed contract."""\n',
            f'{base}/env.py': '"""Implement the DUT transaction environment using the locked Toffee API."""\n'
                'class Environment:\n    def __init__(self, dut):\n'
                '        raise NotImplementedError("TODO: bind ports, driver, monitor and independent checks")\n',
            f'{base}/tests/test_{dut}_smoke.py': '"""Replace this placeholder with a real DUT transaction check."""\n'
                'import pytest\n\ndef test_smoke():\n'
                '    pytest.fail("TODO: register the DUT fixture and implement the smoke contract")\n',
            f'docs/spec/design/{dut}.md': f'# {top} — Design spec\n\n状态：草稿，待设计确认。基线：由工程 ucv.json 继承。\n\n'
                '## 职责与上下游\n\nTODO\n\n## 接口、配置与合法输入\n\nTODO\n\n'
                '## 行为要求、时序与并发\n\n为每条要求分配稳定 ID；记录 reset/redirect/异常及不变量。\n\n'
                '## 依据与待确认问题\n\nTODO：规格来源、设计 owner 与 review 结论。\n',
            f'docs/spec/verification/{dut}.md': f'# {top} — Verification spec\n\n状态：草稿，尚未实现验证。\n\n'
                '## 范围与假设\n\nTODO\n\n## 要求到验证项\n\n'
                '| 设计要求 ID | 场景与合法前态 | 独立预期依据 | 观察与 checker | 用例/覆盖 |\n'
                '|---|---|---|---|---|\n\n## 完成条件与缺口\n\nTODO\n',
        }
        from .documents import issue_index, issues
        initial_issues=issues(project.suite(name)) if existing else []
        issue_baseline=project.suite(name).baseline['name'] if existing else None
        overview={
            'docs/README.md':f'# {name} 资料汇总\n\n'
                '[设计规格](spec/design/README.md) · [验证规格](spec/verification/README.md) · '
                '[问题汇总](bugs/README.md)\n\n'
                '本页维护当前范围和入口；运行明细通过 `ucv report` 读取。\n',
            'docs/spec/design/README.md':'# 设计规格\n\n按模块维护职责、接口、时序、合法域与行为要求。\n\n'
                f'初始模块：[`{dut}`]({dut}.md)。新增模块由 `ucv info` 发现。\n',
            'docs/spec/verification/README.md':'# 验证规格\n\n按模块维护场景、独立预期、检查、覆盖与完成条件。\n\n'
                f'初始模块：[`{dut}`]({dut}.md)。新增模块由 `ucv info` 发现。\n',
            'docs/bugs/README.md':'# 问题汇总\n\n同一问题保留稳定 ID；当前状态由 open/closed 目录决定。\n\n'
                +issue_index(initial_issues,issue_baseline)+'\n',
        }
        files.update({p:text for p,text in overview.items() if not (path/p).exists() and not (path/p).is_symlink()})
        if not existing:
            files.update({'__init__.py':'from pathlib import Path\n\nROOT = Path(__file__).resolve().parent\n',
                'README.md':f'# {name}\n\n从仓库根运行 `./scripts/ucv info {name}` 查看规格、源码和运行入口。\n\n'
                    '资料见 [docs/README.md](docs/README.md)。先填写 docs/spec/design 与 '
                    'docs/spec/verification，再实现 testbenches/<dut>/ 中的事务环境和显式失败占位用例。\n',
                'pytest.ini':'[pytest]\nasyncio_mode = auto\nasyncio_default_fixture_loop_scope = function\n'
                    'testpaths = testbenches\nmarkers =\n    selftest: environment checks, not hardware credit\n',
                'conftest.py':'"""Register testbench-owned fixtures here; keep one suite pytest root."""\npytest_plugins = ("ucv.pytest_selftest",)\n'})
        if not (path/directory/'__init__.py').exists():files[directory+'/__init__.py']=''
        # Preflight the whole DUT boundary, including unregistered user work.
        for candidate in (path/base,path/dut):
            if candidate.exists() or candidate.is_symlink():
                raise UcvError(f'Refusing to overwrite existing {field}: '+str(candidate))
        if existing:
            errors=problems(project.suite(name),workspace)
            if errors:
                raise UcvError(f'Existing suite violates {field} layout:\n'+'\n'.join(errors))
        for name_in_suite in files:
            target = contained(path, name_in_suite)
            if target.exists() or target.is_symlink():
                raise UcvError('Refusing to overwrite: '+str(target))
        for name_in_suite, content in files.items():
            target = path/name_in_suite
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('x') as stream:stream.write(content)
        for parent in [project.root/'suites',path.parent]:
            entry = parent/'__init__.py'
            if not entry.exists():
                with entry.open('x') as stream:stream.write('')
        recipe['duts'][dut] = {'top':top,'export_name':export_name}
        workspace['duts'][dut] = {field:dut,'design_spec':f'docs/spec/design/{dut}.md',
            'verification_spec':f'docs/spec/verification/{dut}.md','environment':f'{base}/env.py',
            'chisel':[], 'tests':[f'{base}/tests'],
            'smoke':f'{base}/tests/test_{dut}_smoke.py::test_smoke'}
        write(path/'ucv.json',recipe)
        write(path/'workspace.json',workspace)
        nav['current']=list(dict.fromkeys([*nav['current'], 'README.md', *overview,
                                         f'docs/spec/design/{dut}.md',f'docs/spec/verification/{dut}.md',f'{base}/README.md']))
        write(navigation,nav)
        for state in ('open','closed'):(path/'docs/bugs'/state).mkdir(parents=True,exist_ok=True)
        if not existing:
            config['suites'][name] = str(path.relative_to(project.root))
            write(project.root/'ucv.json',config)
            project.config=config
        refresh_readmes(project,project.suite(name),workspace,write=True)
        return str(path)
