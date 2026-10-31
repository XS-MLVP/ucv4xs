"""Portable suite paths and pinned runtime validation. MPL-2.0."""
from functools import lru_cache
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version
import os
from pathlib import Path
from .common import UcvError, digest, file_hash, read
from .config import Project
from .sources import git

def project_root():
    return Project().root

def tool_path(name):
    root=project_root()
    if name in {'verilator','verilator_coverage'}:return root/'.tools/verilator/bin'/name
    if name=='python':return Project(root).runtime_python()
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

def suite_python_sources(suite_root):
    """List suite source files without following native or evidence links."""
    root=Path(suite_root).resolve()
    excluded={'dut','rtl','results','XiangShan','XiangShan-internal',
              '__pycache__','.pytest_cache','.git'}
    paths=[]
    for directory,children,files in os.walk(root,followlinks=False):
        parent=Path(directory)
        children[:]=[name for name in children
                     if name not in excluded and not (parent/name).is_symlink()]
        paths.extend(parent/name for name in files
                     if name.endswith('.py') and not (parent/name).is_symlink())
    return sorted(paths)

def distribution_name(pin, fallback):
    """Return the locked Python distribution name, with a legacy fallback."""
    return pin.get('distribution') or fallback

def installed_version(pin, *legacy):
    """Read the installed version without confusing a renamed distribution."""
    names=[pin.get('distribution'),*legacy]
    for name in dict.fromkeys(n for n in names if n):
        try:return version(name)
        except PackageNotFoundError:continue
    raise RuntimeError(f"installed distribution missing: {pin.get('distribution','/'.join(legacy))}")

@lru_cache(maxsize=1)
def validate_runtime():
    import toffee
    import xspcomm
    project=Project()
    development=project.local.get('development_toffee')
    if development:
        return validate_development_runtime(project,toffee,xspcomm,development)
    source=project.root/'.tools/sources/toffee'
    if git(source,'rev-parse','HEAD')!=project.tools['toffee']['commit'] or git(source,'diff','--name-only','HEAD'):
        raise RuntimeError('Pinned toffee source checkout changed')
    package=Path(toffee.__file__).resolve().parent
    environment=project.runtime_python().parent.parent.resolve()
    if not package.is_relative_to(environment):
        raise RuntimeError(f'toffee must come from the selected runtime environment: {package}')
    for path in sorted((source/'src/toffee').rglob('*')):
        if path.is_file() and path.suffix in {'.py','.html','.css','.typed'}:
            installed=package/path.relative_to(source/'src/toffee')
            if not installed.is_file() or file_hash(path)!=file_hash(installed):
                raise RuntimeError(f'Installed toffee differs from locked source: {path.name}')
    validate_binding(xspcomm)
    binding_version=installed_version(project.tools['xcomm'],'xspcomm')
    if binding_version!=project.tools['xcomm']['package_version']:
        raise RuntimeError('xcomm Python package version differs from lock')
    return dict(toffee=str(package),xspcomm=str(Path(xspcomm.__file__).resolve()),
                toffee_distribution=distribution_name(project.tools['toffee'],'pytoffee'),
                package_version=installed_version(project.tools['toffee'],'pytoffee'),
                binding_distribution=distribution_name(project.tools['xcomm'],'xspcomm'),
                binding_version=binding_version,native_abi=xspcomm.abi_version(),
                coverage_protocol=xspcomm.XTriggerEngine.CoverageVersion())

def validate_development_runtime(project,toffee,binding,development):
    """Verify an explicitly selected local source install, without forging pins.

    Local paths and installation receipts live in .ucv, never in public build
    recipes.  The old build cache/tool receipts remain valid and unchanged;
    this runtime's source, distribution version and binding identity are
    additional run evidence, not a claim to have rebuilt native DUTs.
    """
    source=Path(development['source']).expanduser().resolve()
    receipt_path=project.root/development['receipt']
    receipt=read(receipt_path)
    if git(source,'rev-parse','HEAD')!=receipt['base_commit']:
        raise RuntimeError('Development Toffee base commit changed; reinstall and refresh the receipt')
    names=git(source,'ls-files','--cached','--others','--exclude-standard','-z').split('\0')
    files={name:file_hash(source/name) for name in sorted(set(names))
           if name and (source/name).is_file()}
    if files!=receipt['source_files'] or digest(files)!=receipt['source_sha256']:
        raise RuntimeError('Development Toffee source changed; reinstall and refresh the receipt')
    package=Path(toffee.__file__).resolve().parent
    environment=project.runtime_python().parent.parent.resolve()
    if not package.is_relative_to(environment):
        raise RuntimeError(f'Toffee must come from the selected environment: {package}')
    if version(receipt['distribution'])!=receipt['package_version']:
        raise RuntimeError('Development Toffee package version differs from receipt')
    installed={str(path.relative_to(package)) for path in package.rglob('*')
               if path.is_file() and path.suffix in {'.py','.html','.css','.typed'}}
    if installed!=set(receipt['package_files']):
        raise RuntimeError('Installed development Toffee file set differs from receipt')
    for name,expected in receipt['package_files'].items():
        path=package/name
        if not path.is_file() or file_hash(path)!=expected:
            raise RuntimeError(f'Installed development Toffee differs from source: {name}')
    native=receipt['runtime_binding']
    if version(native['distribution'])!=native['package_version']:
        raise RuntimeError('Development runtime binding distribution changed')
    validate_binding_identity(binding,native)
    return dict(mode='development',python=str(project.runtime_python()),toffee=str(package),
                distribution=receipt['distribution'],package_version=receipt['package_version'],
                source=str(source),base_commit=receipt['base_commit'],
                source_sha256=receipt['source_sha256'],receipt_sha256=file_hash(receipt_path),
                wheel_sha256=receipt['wheel_sha256'],
                xspcomm=str(Path(binding.__file__).resolve()),runtime_binding=native,
                native_dut_binding=project.tools['xcomm'])

def validate_binding(binding):
    pin=Project().tools['xcomm']
    validate_binding_identity(binding,pin)

def validate_binding_identity(binding,pin):
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
    development=project.local.get('development_toffee')
    toffee=({**project.tools['toffee'],**validate_runtime()} if development else
            {**project.tools['toffee'],
             'package_version':installed_version(project.tools['toffee'],'pytoffee'),
             'installed_source':str(project.root/'.tools/sources/toffee/src/toffee')})
    return {**project.tools,
            'toffee':{**toffee,'runner_command':[str(tool_path('python')),'-m','toffee','run']},
            'verilator':{**project.tools['verilator'],'root':str(project.root/'.tools/verilator'),
                         'coverage_processor':str(tool_path('verilator_coverage'))},
            'picker':{**project.tools['picker'],'executable':str(tool_path('picker'))}}
