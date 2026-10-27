"""Exact independent source checkouts and Chisel generation. MPL-2.0."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .common import UcvError, digest, execute, file_hash, lock, now, read, write

def git(path, *args):
    return execute(['git','-C',path,*args]).stdout.strip()

def source_key(baseline):
    return digest({k:baseline[k] for k in ('repository','commit','recursive_submodules','patches')})

def checkout(url, commit, destination, mirror=None, log=None, allow_dirty=False):
    destination = Path(destination)
    if not (destination/'.git').exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        execute(['git','clone','--no-hardlinks','--no-checkout', mirror or url, destination], log=log)
        execute(['git','-C',destination,'remote','set-url','origin',url], log=log)
        if execute(['git','-C',destination,'cat-file','-e',commit+'^{commit}'],check=False).returncode:
            execute(['git','-C',destination,'fetch','origin',commit], log=log)
        execute(['git','-C',destination,'checkout','--detach',commit], log=log)
    if git(destination,'rev-parse','HEAD') != commit:
        raise UcvError(f'Checkout is at the wrong revision: {destination}')
    if not allow_dirty and git(destination,'diff','HEAD','--name-only','--ignore-submodules=all'):
        raise UcvError(f'Tracked source changes in {destination}; use a named baseline patch')
    return destination

def source(project, baseline):
    key = source_key(baseline)
    target = project.root/'.cache/sources'/key
    log = project.root/'.cache/logs'/f'source-{key}.log'
    with lock(project.root/'.cache/locks'/f'source-{key}'):
        mirror = project.local.get('source_mirrors',{}).get(baseline['name'])
        if baseline['visibility']=='internal' and (not mirror or not Path(mirror).is_dir()):
            raise UcvError(f"{baseline['name']}: provide source_mirrors.{baseline['name']} in .ucv/local.json; internal source is external")
        applied = target/'.ucv-patches.json'
        checkout(baseline['repository'],baseline['commit'],target,mirror,log,
                 allow_dirty=bool(baseline['patches'] and applied.exists()))
        if applied.exists():
            receipt = read(applied)
            if (receipt['patches'] != baseline['patches']
                    or receipt['diff_sha256'] != digest(git(target,'diff','HEAD','--binary','--ignore-submodules=all'))):
                raise UcvError('Source patch content differs from its receipt')
        entries = baseline['recursive_submodules']
        # Parent directories must be checked out before their children.
        for depth in sorted({len(Path(e['path']).parts) for e in entries}):
            def one(entry):
                relative = entry['path']
                seed = Path(mirror)/relative if mirror else None
                checkout(entry['repository'],entry['commit'],target/relative,
                         str(seed) if seed and (seed/'.git').exists() else None,
                         project.root/'.cache/logs'/f'submodule-{key}-{relative.replace("/","_")}.log')
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(one,[e for e in entries if len(Path(e['path']).parts)==depth]))
        # Check completeness against every parent gitlink, not only the lock list.
        actual = {}
        for relative in ['', *[e['path'] for e in entries]]:
            directory = target/relative
            if not (directory/'.gitmodules').exists():
                continue
            for row in git(directory,'config','-f','.gitmodules','--get-regexp',r'submodule\..*\.path').splitlines():
                _, child = row.split(None,1)
                revision = git(directory,'ls-tree','HEAD',child).split()[2]
                actual[str(Path(relative)/child)] = revision
        if actual != {e['path']:e['commit'] for e in entries}:
            raise UcvError(f"Recursive submodule lock disagrees with {baseline['name']} gitlinks")
        if baseline['patches'] and not applied.exists():
            for patch in baseline['patches']:
                execute(['git','-C',target,'apply',project.root/patch['path']],log=log)
            write(applied, {'patches':baseline['patches'],
                  'diff_sha256':digest(git(target,'diff','HEAD','--binary','--ignore-submodules=all'))})
        write(target/'.ucv-source.json',{'baseline':baseline,'checked_at':now()})
    return target

def generation_spec(baseline):
    # Preserve the identity of existing whole-chip RTL caches. The two null
    # fields are legacy schema slots, never configurable generation overrides.
    return {'baseline':baseline,'generation':'soc','dut':None,'overlay':None}

def generate(project, suite):
    baseline = suite.baseline
    spec = generation_spec(baseline)
    key = digest(spec)
    destination = project.root/'.cache/generated'/key
    receipt = destination/'generation.json'
    with lock(project.root/'.cache/locks'/f'generate-{key}'):
        if receipt.exists():
            record = read(receipt)
            if record['spec']!=spec or any(file_hash(destination/'rtl'/p)!=h for p,h in record['rtl'].items()):
                raise UcvError(f'Generated RTL cache is corrupt: {destination}')
            return destination/'rtl'
        checkout_root = source(project, baseline)
        env = project.environment()
        mill = project.root/'.tools/bin/mill'
        firtool = project.root/'.tools/bin/firtool'
        if not mill.is_file() or not firtool.is_file():
            raise UcvError('Generation tools missing; run ucv setup')
        if baseline['tools']['firtool'] not in execute([firtool,'--version']).stdout:
            raise UcvError('firtool version differs from the baseline')
        if (checkout_root/'.mill-version').read_text().strip()!=baseline['tools']['mill']:
            raise UcvError('mill version differs from the baseline')
        build_file = next(checkout_root.glob('build.mill'), checkout_root/'build.sc')
        if baseline['tools']['chisel'] not in build_file.read_text():
            raise UcvError('Chisel version differs from the baseline')
        env['NOOP_HOME'] = str(checkout_root)
        env['MILL_VERSION'] = baseline['tools']['mill']
        output = destination/'rtl'
        output.mkdir(parents=True,exist_ok=True)
        command = [mill,'-i','-Djvm-xmx=64G','-Djvm-xss=64m',baseline['design'].get('mill_target','xiangshan.runMain'),
                   baseline['design']['top'],
                   '--target-dir',output,'--config',baseline['design']['config'],
                   '--num-cores',str(baseline['design']['num_cores']),
                   '--target','systemverilog','--split-verilog','--dump-fir',
                   '--firtool-binary-path',firtool,'--firtool-opt',' '.join(baseline['firtool_options'])]
        # Mill writes build state: all generations using the same checkout serialize.
        command += baseline['design'].get('chisel_args',[])
        with lock(project.root/'.cache/locks'/f'mill-{source_key(baseline)}'):
            execute(command,cwd=checkout_root,env=env,log=destination/'generate.log')
        rtl = {str(p.relative_to(output)):file_hash(p) for p in sorted(output.rglob('*'))
               if p.is_file() and p.suffix in {'.sv','.v','.vh','.svh'}}
        if not rtl:
            raise UcvError(f'No RTL generated; see {destination}/generate.log')
        write(receipt,{'spec':spec,'command':list(map(str,command)),'rtl':rtl,'completed_at':now(),
                       'assertions':'Chisel/CIRCT original $fatal; no post-generation hardware edits'})
    return output
