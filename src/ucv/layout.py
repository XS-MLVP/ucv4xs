"""Versioned testbench source layout and generated work entrances. MPL-2.0.

This module never imports a verification package or a native DUT.
"""
from contextlib import nullcontext
from configparser import ConfigParser, Error as ConfigError
from importlib.util import resolve_name
from pathlib import Path
import ast
import keyword
import os
import re
import shlex

from .common import UcvError, contained, lock, read

START = '<!-- ucv:module:start -->'
END = '<!-- ucv:module:end -->'
ROLES = {'env', 'model', 'checker', 'coverage', 'transactions', 'tests'}
INFRASTRUCTURE = {'runtime', 'tools'}
CACHES = {'__pycache__', '.pytest_cache'}
DATA_DIRS = {'dependencies', 'manifest'}
GENERATED_DIRS = {'dut', 'rtl', 'results'}
SUITE_DIRS = {'modules', 'docs', *INFRASTRUCTURE, *DATA_DIRS, *GENERATED_DIRS, *CACHES}
SUITE_FILES = {'__init__.py', 'conftest.py', 'pytest.ini', 'README.md', 'ucv.json',
               'workspace.json', 'requirements.txt'}
SOURCE_LINKS = {'XiangShan'}
LAYOUTS = {1: ('modules', 'module'), 2: ('testbenches', 'testbench')}


def layout_names(meta):
    schema=meta.get('schema')
    if type(schema) is not int or schema not in LAYOUTS:
        raise UcvError('workspace schema must be 1 or 2')
    return LAYOUTS[schema]


def testbench_name(dut, entry, schema=2):
    _,field=layout_names({'schema':schema})
    other='module' if field=='testbench' else 'testbench'
    if other in entry:
        raise UcvError(f'{dut}: workspace schema {schema} uses {field}, not {other}')
    value=entry.get(field, dut if schema==1 else None)
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z_]\w*',value) or keyword.iskeyword(value):
        raise UcvError(f'{dut}: {field} must be an explicit Python identifier')
    if schema==2 and (dut=='shared' or value=='shared'):
        raise UcvError(f'{dut}: shared is reserved and cannot be a DUT testbench')
    return value


def testbench_path(dut, entry, schema=2):
    directory,_=layout_names({'schema':schema})
    return directory+'/'+testbench_name(dut,entry,schema)


def entry_problems(root, directories, files, *, scope, links=()):
    """A closed, typed whitelist over physical entries, including ignored ones."""
    errors=[]
    if not root.is_dir() or root.is_symlink():return errors
    for child in sorted(root.iterdir()):
        name=child.name
        if child.is_symlink():
            if name not in links:errors.append(f'symlink not allowed at {scope}: {name}')
        elif name in links:
            errors.append(f'expected source symlink at {scope}: {name}')
        elif child.is_dir():
            if name not in directories:errors.append(f'unexpected directory at {scope}: {name}')
        elif child.is_file():
            if name not in files:errors.append(f'unexpected file at {scope}: {name}')
        else:
            errors.append(f'unsupported entry at {scope}: {name}')
    return errors


def module_name(dut, entry):
    """Compatibility entry for schema 1 callers."""
    return testbench_name(dut,entry,1)


def module_path(dut, entry):
    """Compatibility entry for schema 1 callers."""
    return testbench_path(dut,entry,1)


def collection_plugins(suite):
    """Read root plugin declarations for early registration without suite imports."""
    path=suite.path/'conftest.py'
    if not path.is_file():return []
    names=[]
    try:
        for node in ast.parse(path.read_text(),filename=str(path)).body:
            targets=(node.targets if isinstance(node,ast.Assign) else
                     [node.target] if isinstance(node,ast.AnnAssign) else [])
            if not any(isinstance(target,ast.Name) and target.id=='pytest_plugins' for target in targets):continue
            names=ast.literal_eval(node.value)
            if isinstance(names,str):names=[names]
            if (not isinstance(names,(list,tuple)) or any(not isinstance(name,str) or not name or
                    any(not part.isidentifier() or keyword.iskeyword(part) for part in name.split('.')) for name in names)):
                raise ValueError('invalid plugin names')
    except (SyntaxError,ValueError,TypeError) as error:
        raise UcvError(f'{suite.name}: conftest.py pytest_plugins must declare explicit import names: {error}') from error
    return list(dict.fromkeys(names))


def source_files(path):
    if path.is_symlink():return []
    paths=[]
    for directory,children,files in os.walk(path,followlinks=False):
        parent=Path(directory)
        children[:]=[name for name in children if name not in CACHES and not (parent/name).is_symlink()]
        paths.extend(parent/name for name in files if name.endswith('.py') and not (parent/name).is_symlink())
    return sorted(paths)


def shared_import_problems(root):
    """Resolve static imports without importing suite code, including relative forms."""
    shared=root/'testbenches/shared'
    namespace=f'suites.{root.parent.name}.{root.name}'
    errors=[]
    for path in source_files(shared):
        if path.relative_to(shared).parts[0]=='tests':continue
        package=namespace+'.'+'.'.join(path.parent.relative_to(root).parts)
        try:tree=ast.parse(path.read_text(),filename=str(path))
        except SyntaxError as error:
            errors.append(str(error));continue
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                names=[alias.name for alias in node.names]
            elif isinstance(node,ast.ImportFrom):
                try:base=resolve_name('.'*node.level+(node.module or ''),package)
                except ImportError as error:
                    errors.append(f'{path.relative_to(root)}:{node.lineno}: {error}');continue
                names=[base,*[base+'.'+alias.name for alias in node.names]]
            else:continue
            for name in names:
                # Fully qualified suite imports and short imports are both
                # visible; resolving relatives above never executes a package.
                local=re.sub(r'^suites\.[^.]+\.[^.]+\.', '', name)
                if local.startswith('testbenches.') and local.split('.')[1]!='shared':
                    errors.append(f'{path.relative_to(root)}:{node.lineno}: shared implementation imports DUT testbench: {name}')
                    break
                if local=='tools' or local.startswith('tools.'):
                    errors.append(f'{path.relative_to(root)}:{node.lineno}: shared implementation imports suite tools: {name}')
                    break
    return errors


def problems(suite, meta):
    """Reject parallel layouts and tests without an explicitly registered owner."""
    errors = []
    root = suite.path
    directory,field=layout_names(meta)
    schema=meta['schema']
    directories=SUITE_DIRS if schema==1 else (SUITE_DIRS-{'modules','runtime'})|{'testbenches'}
    errors.extend(entry_problems(root,directories,SUITE_FILES,scope='suite root',links=SOURCE_LINKS))
    if schema==2:
        try:collection_plugins(suite)
        except UcvError as error:errors.append(str(error))
    # These are metadata records, never alternative implementation trees.
    for name in DATA_DIRS:
        data=root/name
        if data.is_dir() and not data.is_symlink():
            files=({'versions.json'} if name=='dependencies' else
                   {p.name for p in data.iterdir() if p.suffix in {'.json','.sha256','.md'}})
            errors.extend(entry_problems(data,set(),files,scope=name))
    errors.extend(entry_problems(root/'docs',{'spec','bugs','guides'},
                                {'README.md','navigation.json','path-migrations.json'},scope='docs'))
    errors.extend(entry_problems(root/'docs/spec',{'design','verification'},{'README.md'},scope='docs/spec'))
    bugs=root/'docs/bugs'
    if bugs.is_dir() and not bugs.is_symlink():
        errors.extend(entry_problems(bugs,{'open','closed','evidence'},
                                    {p.name for p in bugs.iterdir() if p.suffix=='.md'},scope='docs/bugs'))
    if suite.recipe.get('pytest_root', '.') != '.' or suite.recipe.get('tests') != [directory]:
        errors.append(f'pytest_root must be . and tests must be ["{directory}"]')
    for path in ('__init__.py', 'conftest.py', 'pytest.ini', directory+'/__init__.py'):
        if not (root/path).is_file():errors.append('missing layout entry: '+path)
    if (root/'pytest.ini').is_file():
        config=ConfigParser(interpolation=None)
        try:
            config.read(root/'pytest.ini')
            if config.get('pytest','testpaths',fallback='').split()!=[directory]:
                errors.append('pytest.ini testpaths must be '+directory)
        except ConfigError as error:
            errors.append('invalid pytest.ini: '+str(error))
    if meta.get('fixtures') != 'conftest.py':errors.append('fixtures must point to suite conftest.py')
    owners = {}
    for dut in suite.recipe['duts']:
        entry = meta['duts'].get(dut,{})
        module = testbench_name(dut,entry,schema)
        owners.setdefault(module,[]).append(dut)
        base = testbench_path(dut,entry,schema)
        for role in ('environment','tests'):
            values = entry.get(role, [])
            values = values if isinstance(values,list) else [values]
            if not values:errors.append(f'{dut}: declare {role} in workspace.json')
            for value in values:
                path = contained(root,value)
                boundary = root/base/('tests' if role=='tests' else 'env')
                legal = path.resolve().is_relative_to(boundary.resolve()) or (role=='environment' and path==root/base/'env.py')
                if not legal:errors.append(f'{dut}: {role} outside its {field}: {value}')
        for role,folder in (('design_spec','design'),('verification_spec','verification')):
            values=entry.get(role,[])
            values=values if isinstance(values,list) else [values]
            # Plans/ledgers may be referenced in addition to the centralized spec.
            if not any(contained(root,v).is_relative_to(root/'docs/spec'/folder) for v in values):
                errors.append(f'{dut}: {role} must link the suite docs/spec/{folder}')
    shared=root/'testbenches/shared'
    if schema==2 and (shared.exists() or shared.is_symlink()):owners['shared']=[]
    for module,duts in owners.items():
        base=root/directory/module
        required=['__init__.py','README.md']
        if duts or (base/'tests').exists():required.append('tests/__init__.py')
        for path in required:
            if not (base/path).is_file():errors.append(f'{module}: missing {path}')
        if base.is_dir() and not base.is_symlink():
            errors.extend(entry_problems(base,ROLES|CACHES,
                                        {'__init__.py','README.md',*(role+'.py' for role in ROLES-{'tests'})},
                                        scope=field+' '+module))
            for role in ROLES:
                if (base/(role+'.py')).exists() and (base/role).is_dir():
                    errors.append(f'{module}: choose {role}.py or {role}/, not both')
    modules=root/directory
    errors.extend(entry_problems(modules,set(owners)|CACHES,{'__init__.py'},scope=directory))
    for path in source_files(modules) if modules.is_dir() else []:
        if path.name=='conftest.py':errors.append('fixture registration belongs at suite root: '+str(path.relative_to(root)))
        if path.name.startswith('test_') and 'tests' not in path.relative_to(modules).parts:
            errors.append(f'test outside {field} tests: '+str(path.relative_to(root)))
    for path in modules.rglob('pytest.ini') if modules.is_dir() and not modules.is_symlink() else []:
        errors.append('pytest configuration belongs at suite root: '+str(path.relative_to(root)))
    for name in INFRASTRUCTURE:
        infrastructure=root/name
        for path in source_files(infrastructure):
            if path.name=='conftest.py':errors.append('fixture registration belongs at suite root: '+str(path.relative_to(root)))
        for path in infrastructure.rglob('pytest.ini') if infrastructure.is_dir() and not infrastructure.is_symlink() else []:
            errors.append('pytest configuration belongs at suite root: '+str(path.relative_to(root)))
    if schema==2:errors.extend(shared_import_problems(root))
    return errors


def relocated_name(root, name):
    """Navigate a frozen path/nodeid; this does not establish receipt equivalence."""
    manifest=root/'docs/path-migrations.json'
    if not manifest.is_file():return name
    value=read(manifest)
    if (not isinstance(value,dict) or value.get('schema')!=1 or not isinstance(value.get('paths'),dict)
            or any(not isinstance(k,str) or not k or not isinstance(v,str) or not v
                   for k,v in value['paths'].items())):
        raise UcvError('Invalid path migration map: '+str(manifest))
    paths=sorted(value['paths'].items(),key=lambda item:len(item[0]),reverse=True)
    visited=set()
    while True:
        for old,new in paths:
            if (name==old or name.startswith((old+'/',old+'::'))
                    or ('::' in old and name.startswith(old+'['))):
                # Reusing a migration source is a cycle, including a growing
                # prefix such as a -> a/subdir that never repeats a full name.
                if old in visited:raise UcvError('Path migration cycle: '+str(manifest)+': '+old)
                visited.add(old)
                name=new+name[len(old):]
                contained(root,name.split('::')[0])
                break
        else:return name


def relocated(root, name):
    """Resolve a relocated file or directory for documentation navigation."""
    return contained(root,relocated_name(root,name).split('::')[0])


def readme_block(suite, module, entries, schema=1):
    directory,_=layout_names({'schema':schema})
    base=suite.path/directory/module
    def link(value):
        path=contained(suite.path,value)
        relative=Path(os.path.relpath(path,base)).as_posix()
        return f'[{value}]({relative})'
    if schema==2 and module=='shared':
        lines=[START, '', '由 `ucv docs --write` 更新；跨 testbench 共享实现与自检入口。', '',
               'shared 是保留的共享包，不对应 RTL top；实现按实际职责组织，自检归 tests/。', '',
               '## 工作入口', '',
               '- 设计规格：'+link('docs/spec/design/README.md'),
               '- 验证合同：'+link('docs/spec/verification/README.md')]
        for role in ('env','transactions','model','checker','coverage','tests'):
            path=next((p for p in (base/(role+'.py'),base/role) if p.exists()),None)
            if path is not None:lines.append('- '+role+'：'+link(str(path.relative_to(suite.path))))
        lines+=['- 问题：'+link('docs/bugs/README.md')]
        if (base/'tests').is_dir():
            lines+=['', '## 从仓库根操作', '', '```sh',
                    f'./scripts/ucv run {suite.name} --collect-only --workers 1 -- testbenches/shared/tests',
                    f'./scripts/ucv run {suite.name} --workers 1 -- testbenches/shared/tests',
                    './scripts/ucv report', '```', '',
                    '按 DUT 默认选择时同时收集这些共享自检；显式 pytest 路径或 nodeid 仍限定实际选择。']
        return '\n'.join([*lines,'',END])
    lines=[START, '', '由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。', '',
           '| DUT 键 | RTL top | Python 导出名 |', '|---|---|---|']
    for dut,_ in entries:
        spec=suite.recipe['duts'][dut]
        lines.append(f"| `{dut}` | `{spec['top']}` | `{spec['export_name']}` |")
    if len(entries)>1:
        lines+=['','这些 DUT 显式共用参数化实现；运行共享用例时选择其实际需要的全部 DUT。']
    lines+=['','## 工作入口','']
    for role,label in [('design_spec','设计规格'),('verification_spec','验证合同与计划'),('environment','公开环境'),('tests','用例与自检')]:
        paths=[]
        for _,entry in entries:
            values=entry.get(role,[])
            paths.extend(values if isinstance(values,list) else [values])
        lines.append('- '+label+'：'+' · '.join(link(p) for p in dict.fromkeys(paths)))
    implementations=[]
    for role in ('transactions','model','checker','coverage'):
        path=next((p for p in (base/(role+'.py'),base/role) if p.exists()),None)
        if path is not None:implementations.append(link(str(path.relative_to(suite.path))))
    if implementations:lines.append('- 实现职责：'+' · '.join(implementations))
    lines+=['- 问题：'+link('docs/bugs/README.md'), '', '## 从仓库根操作', '', '```sh']
    selection=' '.join('--dut '+dut for dut,_ in entries)
    smoke=list(dict.fromkeys(entry['smoke'] for _,entry in entries if entry.get('smoke')))
    run=f'./scripts/ucv run {suite.name} {selection} --workers 1'
    if smoke:run+=' -- '+' '.join(shlex.quote(node) for node in smoke)
    lines += [f'./scripts/ucv info {suite.name} {selection}',
              f'./scripts/ucv run {suite.name} {selection} --collect-only --workers 1',
              run,
              './scripts/ucv report', '```', '',
              '源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。', '', END]
    return '\n'.join(lines)


def refresh_readmes(project, suite, meta, write=False):
    directory,field=layout_names(meta)
    grouped={}
    for dut in suite.recipe['duts']:
        entry=meta['duts'].get(dut,{})
        grouped.setdefault(testbench_name(dut,entry,meta['schema']),[]).append((dut,entry))
    if meta['schema']==2 and (suite.path/directory/'shared').is_dir():grouped['shared']=[]
    rows=[]
    with lock(project.root/'.cache/locks'/(directory+'-'+suite.name)) if write else nullcontext():
        for module,entries in grouped.items():
            path=contained(suite.path,f'{directory}/{module}/README.md')
            original=path.read_text() if path.is_file() else f'# {module}\n\n'
            block=readme_block(suite,module,entries,meta['schema'])
            if START in original or END in original:
                if original.count(START)!=1 or original.count(END)!=1 or original.index(START)>original.index(END):
                    raise UcvError(f'Invalid {field} README markers: '+str(path))
                before,rest=original.split(START)
                _,after=rest.split(END)
                expected=before+block+after
            else:expected=original.rstrip()+'\n\n'+block+'\n'
            changed=expected!=original
            if write and changed:
                path.parent.mkdir(parents=True,exist_ok=True)
                temp=path.with_suffix('.md.tmp');temp.write_text(expected);temp.replace(path)
            rows.append({field:module,'path':str(path),'current':not changed or write,'updated':changed and write})
    return rows
