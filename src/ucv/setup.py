"""Project-local installation from pinned sources. MPL-2.0."""
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request
import venv
from . import host
from .common import UcvError, digest, execute, file_hash, lock, now, read, write
from .sources import checkout, git

def dependency_source(project, name, log=None):
    """Checkout a locked dependency and verify every applied tool patch."""
    pin = project.tools[name]
    destination = project.root/'.tools/sources'/name
    patches = pin.get('patches', [])
    patch_receipt = destination/'.ucv-patches.json'
    checkout(pin['repository'],pin['commit'],destination,
             project.local.get('dependency_mirrors',{}).get(name),log,
             allow_dirty=bool(patches and patch_receipt.exists()))
    for patch in patches:
        if file_hash(project.root/patch['path']) != patch['sha256']:
            raise UcvError('Dependency patch content changed: '+patch['path'])
    if patch_receipt.exists():
        prior = read(patch_receipt)
        if (prior['patches'] != patches or prior['diff_sha256'] !=
                digest(git(destination,'diff','HEAD','--binary','--ignore-submodules=all'))):
            raise UcvError('Installed dependency patches differ from the lock: '+name)
    elif patches:
        for patch in patches:
            execute(['git','-C',destination,'apply',project.root/patch['path']],log=log)
        write(patch_receipt,{'patches':patches,'diff_sha256':
            digest(git(destination,'diff','HEAD','--binary','--ignore-submodules=all'))})
    return destination

def reusable_verilator(project, previous):
    """Reuse a native install only when its lock, host and binary still match."""
    verilator = project.root/'.tools/verilator'
    return (
        previous.get('tools',{}).get('verilator') == project.tools['verilator']
        and previous.get('machine') == host.machine()
        and previous.get('system') == host.system()
        and (verilator/'bin/verilator').is_file()
        and (verilator/'bin/verilator_bin').is_file()
        and previous.get('binaries',{}).get('verilator/bin/verilator_bin')
            == file_hash(verilator/'bin/verilator_bin'))

def setup(project, jobs=16, profile='runtime'):
    host.require()
    if sys.version_info[:2]!=(3,12):
        raise UcvError(f'The locked environment requires {host.requirement()}')
    root = project.root
    prefix = root/'.tools'
    env = project.environment()
    log = prefix/'setup.log'
    with lock(root/'.cache/locks/setup'):
        previous = read(prefix/'receipt.json') if (prefix/'receipt.json').is_file() else {}
        reuse_verilator = reusable_verilator(project, previous)
        needed = ['git', 'cmake', 'make', 'c++', 'swig']
        if not project.local.get('verilator_seed') and not reuse_verilator:
            needed += ['autoconf', 'flex', 'bison', 'help2man']
        missing = [name for name in needed if not shutil.which(name, path=env.get('PATH'))]
        if missing:
            raise UcvError('Missing host build tools: '+', '.join(missing)+
                           '; see README.md host prerequisites')
        for binary in ('bin/picker', 'verilator/bin/verilator_bin', 'bin/firtool'):
            if (prefix/binary).exists():
                host.require_native_machine(prefix/binary)
        prefix.mkdir(exist_ok=True)
        if not (root/'.venv/bin/python').exists():
            venv.EnvBuilder(with_pip=True,system_site_packages=False).create(root/'.venv')
        python = root/'.venv/bin/python'
        execute([python,'-m','pip','install','-r',root/'dependencies/python.txt'],env=env,log=log)
        sources = {}
        for name in ('toffee','xcomm','picker'):
            sources[name] = dependency_source(project, name, log)
        # Native library and SWIG wrapper are built together from the same pin.
        xcomm_pin = project.tools['xcomm']
        xcomm_distribution = xcomm_pin.get('distribution', 'xspcomm')
        xcomm_version = xcomm_pin['package_version']
        env.update(BUILD_XSPCOMM_SWIG='python', CMAKE_BUILD_PARALLEL_LEVEL=str(jobs),
                   **{f"SETUPTOOLS_SCM_PRETEND_VERSION_FOR_{xcomm_distribution.upper().replace('-', '_')}":
                      xcomm_version})
        # The toffee pin carries an explicit version so the install does not
        # depend on release tags being present in a mirror or shallow clone.
        toffee_pin = project.tools['toffee']
        if toffee_pin.get('package_version'):
            toffee_distribution = toffee_pin.get('distribution', 'pytoffee')
            toffee_key = toffee_distribution.upper().replace('-', '_')
            env[f"SETUPTOOLS_SCM_PRETEND_VERSION_FOR_{toffee_key}"] = toffee_pin['package_version']
        execute([python,'-m','pip','install','--no-build-isolation','--no-deps',sources['xcomm']],env=env,log=log)
        # Picker needs headers/native libraries beside its installed templates.
        xbuild = prefix/'build/xcomm'
        execute(['cmake','-S',sources['xcomm'],'-B',xbuild,'-DCMAKE_BUILD_TYPE=Release',
                 f'-DCMAKE_INSTALL_PREFIX={prefix}','-DBUILD_TESTING=OFF',
                 '-DSKBUILD_PROJECT_VERSION='+xcomm_version,
                 '-DSKBUILD_PROJECT_VERSION_FULL='+xcomm_version],env=env,log=log)
        execute(['cmake','--build',xbuild,'-j',jobs],env=env,log=log)
        # Installs only add files. Remove earlier ABI libraries first, otherwise
        # a generated DUT copies several ABIs beside each other and the loader
        # may pick a stale soname. Picker stages the SDK in three places.
        for stale in (prefix/'lib', prefix/'share/picker/lib', prefix/'share/picker/python/xspcomm'):
            if stale.is_dir():
                for item in stale.iterdir():
                    if (item.name.startswith(('libxspcomm.so', '_pyxspcomm.so'))
                            or (item.name.startswith('libxspcomm') and item.name.endswith('.dylib'))):
                        item.unlink()
        execute(['cmake','--install',xbuild],env=env,log=log)
        for name,pin in project.tools['picker']['dependencies'].items():
            parent = project.local.get('dependency_mirrors',{}).get('picker')
            seed = Path(parent)/'dependence'/name if parent else None
            checkout(pin['repository'],pin['commit'],sources['picker']/'dependence'/name,
                     str(seed) if seed and seed.exists() else None,log)
        env['NO_BUILD_XSPCOMM']='1'
        pbuild = prefix/'build/picker'
        execute(['cmake','-S',sources['picker'],'-B',pbuild,'-DCMAKE_BUILD_TYPE=Release',
                 f'-DCMAKE_INSTALL_PREFIX={prefix}','-DBUILD_TESTING=OFF',
                 '-DSLANG_INCLUDE_TESTS=OFF','-DSLANG_INCLUDE_TOOLS=OFF'],env=env,log=log)
        execute(['cmake','--build',pbuild,'-j',jobs],env=env,log=log)
        execute(['cmake','--install',pbuild],env=env,log=log)
        execute([python,'-m','pip','install','--no-build-isolation','--no-deps',sources['toffee']],env=env,log=log)
        if profile=='full':install_generation_tools(project,log)
        verilator = prefix/'verilator'
        if not reuse_verilator:
            seed = project.local.get('verilator_seed')
            if seed:
                # Check the architecture before executing the seed: running a
                # foreign binary reports an opaque exec error instead.
                host.require_native_machine(Path(seed)/'bin/verilator_bin')
                version = project.tools['verilator']['version']
                if version not in execute([Path(seed)/'bin/verilator','--version']).stdout:
                    raise UcvError('Verilator seed is not '+version)
                shutil.copytree(seed,verilator,symlinks=False,dirs_exist_ok=True)
            else:
                pin=project.tools['verilator']
                source=prefix/'sources/verilator'
                if not (source/'.git').exists():
                    execute(['git','clone','--branch',pin['ref'],'--depth','1',pin['repository'],source],log=log)
                dependency_source(project,'verilator',log)
                execute(['autoconf'],cwd=source,env=env,log=log)
                execute(['./configure',f'--prefix={verilator}'],cwd=source,env=env,log=log)
                execute(['make','-j',jobs],cwd=source,env=env,log=log)
                execute(['make','install'],cwd=source,env=env,log=log)
        execute([python,'-m','pip','install','--no-build-isolation','--no-deps','-e',root],env=env,log=log)
        freeze=execute([python,'-m','pip','freeze'],env=env).stdout
        (prefix/'installed-python.txt').write_text(freeze)
        binaries=[prefix/'bin/picker',verilator/'bin/verilator_bin']
        if profile=='full':binaries += [prefix/'bin/firtool',prefix/'bin/mill']
        for binary in binaries:
            if binary.name != 'mill':host.require_native_machine(binary)
        write(prefix/'receipt.json',{'tools':project.tools,'profile':profile,'completed_at':now(),
              'machine':host.machine(),'system':host.system(),
              'python':sys.version,'packages':freeze.splitlines(),
              'binaries':{str(p.relative_to(prefix)):file_hash(p) for p in
                 binaries}})
    return str(prefix/'receipt.json')

def install_generation_tools(project,log=None):
    prefix=project.root/'.tools/bin'
    prefix.mkdir(parents=True,exist_ok=True)
    for name in ('mill','firtool'):
        dest=prefix/name
        if dest.exists():
            if name=='firtool':host.require_native_machine(dest)
            continue
        # Publish only a complete, validated executable. A failed download or
        # extraction must not leave a destination that a retry would skip.
        with tempfile.TemporaryDirectory(prefix='generation-',dir=prefix) as temp:
            staged=Path(temp)/name
            seed=project.local.get(name)
            if seed:
                # Refuse a foreign seed before copying it into the project.
                if name=='firtool':host.require_native_machine(seed)
                shutil.copy2(seed,staged)
            elif name=='mill':
                # This script resolves Linux/macOS distributions itself.
                urllib.request.urlretrieve(host.MILL_LAUNCHER,staged)
            else:
                url=host.firtool_url()
                if url is None:
                    raise UcvError(
                        f'No published firtool for {host.describe()} at {host.FIRTOOL_VERSION}. '
                        f'Supply one through local.json "firtool", or take RTL from a '
                        f'released package (baselines/rtl-releases.json) instead of generating it')
                archive=Path(temp)/'firtool.tar.gz'
                urllib.request.urlretrieve(url,archive)
                import tarfile
                with tarfile.open(archive) as stream:
                    member=next((m for m in stream.getmembers()
                                 if m.isfile() and m.name.endswith('/bin/firtool')),None)
                    if member is None:
                        raise UcvError('The firtool archive does not contain bin/firtool')
                    staged.write_bytes(stream.extractfile(member).read())
                host.require_native_machine(staged)
            staged.chmod(0o755)
            staged.replace(dest)
