"""Portable suite paths and pinned runtime validation. MPL-2.0."""
from functools import lru_cache
from importlib.metadata import version
import os
from pathlib import Path
from .common import UcvError, file_hash, read
from .config import Project
from .sources import git

def project_root():
    return Project().root

def tool_path(name):
    root=project_root()
    if name in {'verilator','verilator_coverage'}:return root/'.tools/verilator/bin'/name
    if name=='python':return root/'.venv/bin/python'
    return root/'.tools/bin'/name

def source_path(baseline='public-893e1580b'):
    from .sources import source_key
    project=Project()
    return project.root/'.cache/sources'/source_key(project.baseline(baseline))

def soc_rtl(baseline='public-893e1580b'):
    from .common import digest
    from .sources import generation_spec
    project=Project()
    spec=generation_spec(project.baseline(baseline))
    return project.root/'.cache/generated'/digest(spec)/'rtl'

def historical_path(suite,relative=''):
    project=Project()
    root=project.local.get('historical_roots',{}).get(suite)
    if root is None:raise UcvError(f'Historical evidence for {suite} is unavailable; configure historical_roots.{suite}')
    return Path(root)/relative

def source_path_for(suite_root):
    return source_path(Project().suite(Path(suite_root).name).baseline['name'])

def soc_rtl_for(suite_root):
    return soc_rtl(Project().suite(Path(suite_root).name).baseline['name'])

def native_seed():
    return '+verilator+seed+'+os.environ.get('UCV_SEED','1')

def scratch_root():
    path=project_root()/'.cache/tmp'
    path.mkdir(parents=True,exist_ok=True)
    return path

@lru_cache(maxsize=1)
def validate_runtime():
    import toffee
    import xspcomm
    project=Project()
    source=project.root/'.tools/sources/toffee'
    if git(source,'rev-parse','HEAD')!=project.tools['toffee']['commit'] or git(source,'diff','--name-only','HEAD'):
        raise RuntimeError('Pinned toffee source checkout changed')
    package=Path(toffee.__file__).resolve().parent
    if not package.is_relative_to(project.root/'.venv'):
        raise RuntimeError(f'toffee must come from the project environment: {package}')
    for path in (source/'src/toffee').rglob('*.py'):
        if file_hash(path)!=file_hash(package/path.relative_to(source/'src/toffee')):
            raise RuntimeError(f'Installed toffee differs from locked source: {path.name}')
    validate_binding(xspcomm)
    if version('xspcomm')!=project.tools['xcomm']['package_version']:
        raise RuntimeError('xspcomm Python package version differs from lock')
    return dict(toffee=str(package),xspcomm=str(Path(xspcomm.__file__).resolve()),
                package_version=version('xspcomm'),native_abi=xspcomm.abi_version(),
                coverage_protocol=xspcomm.XTriggerEngine.CoverageVersion())

def validate_binding(binding):
    pin=Project().tools['xcomm']
    if (not all(callable(getattr(binding,name,None)) for name in ('version','abi_version'))
            or not callable(getattr(getattr(binding,'XTriggerEngine',None),'CoverageVersion',None))):
        raise RuntimeError('generated DUT contains incomplete xcomm bindings')
    actual=(binding.version(),binding.abi_version(),binding.XTriggerEngine.CoverageVersion())
    expected=(pin['package_version'],pin['native_abi'],pin['coverage_protocol'])
    if actual!=expected:raise RuntimeError(f'Native runtime mismatch: {actual}, expected {expected}')
    for method in ('AcquireClock','ReleaseClock','CollectExpressions','ExprNewBits','ExprNewBool','ExprEvalBits'):
        if not hasattr(binding.XTriggerEngine,method):raise RuntimeError(f'Native runtime lacks {method}')

def toolchain():
    project=Project()
    return {**project.tools,
            'toffee':{**project.tools['toffee'],'package_version':version('pytoffee'),
                      'runner_command':[str(tool_path('python')),'-m','toffee','run'],
                      'installed_source':str(project.root/'.tools/sources/toffee/src/toffee')},
            'verilator':{**project.tools['verilator'],'root':str(project.root/'.tools/verilator'),
                         'coverage_processor':str(tool_path('verilator_coverage'))},
            'picker':{**project.tools['picker'],'executable':str(tool_path('picker'))}}
