"""Project-local installation from pinned sources. MPL-2.0."""
import os
from pathlib import Path
import platform
import shutil
import sys
import urllib.request
import venv
from .common import UcvError, execute, file_hash, lock, now, read, write
from .sources import checkout

def setup(project, jobs=16):
    if sys.version_info[:2]!=(3,12) or platform.system()!='Linux' or platform.machine()!='x86_64':
        raise UcvError('The locked environment requires Linux x86_64 and Python 3.12')
    root = project.root
    prefix = root/'.tools'
    prefix.mkdir(exist_ok=True)
    log = prefix/'setup.log'
    with lock(root/'.cache/locks/setup'):
        if not (root/'.venv/bin/python').exists():
            venv.EnvBuilder(with_pip=True,system_site_packages=False).create(root/'.venv')
        python = root/'.venv/bin/python'
        env = project.environment()
        execute([python,'-m','pip','install','-r',root/'dependencies/python.txt'],env=env,log=log)
        sources = {}
        for name in ('toffee','xcomm','picker'):
            pin = project.tools[name]
            sources[name] = checkout(pin['repository'],pin['commit'],prefix/'sources'/name,
                                    project.local.get('dependency_mirrors',{}).get(name),log)
        # Native library and SWIG wrapper are built together from the same pin.
        env.update(BUILD_XSPCOMM_SWIG='python',CMAKE_BUILD_PARALLEL_LEVEL=str(jobs),
                   SETUPTOOLS_SCM_PRETEND_VERSION_FOR_XSPCOMM=project.tools['xcomm']['package_version'])
        execute([python,'-m','pip','install','--no-build-isolation','--no-deps',sources['xcomm']],env=env,log=log)
        # Picker needs headers/native libraries beside its installed templates.
        xbuild = prefix/'build/xcomm'
        execute(['cmake','-S',sources['xcomm'],'-B',xbuild,'-DCMAKE_BUILD_TYPE=Release',
                 f'-DCMAKE_INSTALL_PREFIX={prefix}','-DBUILD_TESTING=OFF',
                 '-DSKBUILD_PROJECT_VERSION=0.3.0',
                 '-DSKBUILD_PROJECT_VERSION_FULL='+project.tools['xcomm']['package_version']],env=env,log=log)
        execute(['cmake','--build',xbuild,'-j',jobs],env=env,log=log)
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
        install_generation_tools(project,log)
        verilator = prefix/'verilator'
        if not (verilator/'bin/verilator').exists():
            seed = project.local.get('verilator_seed')
            if seed:
                if '5.052' not in execute([Path(seed)/'bin/verilator','--version']).stdout:
                    raise UcvError('Verilator seed is not 5.052')
                shutil.copytree(seed,verilator,symlinks=False)
            else:
                pin=project.tools['verilator']
                source=prefix/'sources/verilator'
                execute(['git','clone','--branch',pin['ref'],'--depth','1',pin['repository'],source],log=log)
                execute(['autoconf'],cwd=source,log=log)
                execute(['./configure',f'--prefix={verilator}'],cwd=source,log=log)
                execute(['make','-j',jobs],cwd=source,log=log)
                execute(['make','install'],cwd=source,log=log)
        execute([python,'-m','pip','install','--no-build-isolation','--no-deps','-e',root],env=env,log=log)
        freeze=execute([python,'-m','pip','freeze'],env=env).stdout
        (prefix/'installed-python.txt').write_text(freeze)
        write(prefix/'receipt.json',{'tools':project.tools,'completed_at':now(),
              'python':sys.version,'packages':freeze.splitlines(),
              'binaries':{str(p.relative_to(prefix)):file_hash(p) for p in
                 [prefix/'bin/picker',prefix/'bin/firtool',prefix/'bin/mill',verilator/'bin/verilator_bin']}})
    return str(prefix/'receipt.json')

def install_generation_tools(project,log=None):
    prefix=project.root/'.tools/bin'
    prefix.mkdir(parents=True,exist_ok=True)
    for name in ('mill','firtool'):
        dest=prefix/name
        if dest.exists():continue
        seed=project.local.get(name)
        if seed:
            shutil.copy2(seed,dest)
        elif name=='mill':
            urllib.request.urlretrieve('https://repo1.maven.org/maven2/com/lihaoyi/mill-dist/0.12.17/mill-dist-0.12.17.jar',dest)
        else:
            archive=project.root/'.tools/firtool.tar.gz'
            urllib.request.urlretrieve('https://github.com/llvm/circt/releases/download/firtool-1.149.0/firrtl-bin-linux-x64.tar.gz',archive)
            import tarfile
            with tarfile.open(archive) as stream:
                member=next(m for m in stream.getmembers() if m.name.endswith('/bin/firtool'))
                dest.write_bytes(stream.extractfile(member).read())
        dest.chmod(0o755)
