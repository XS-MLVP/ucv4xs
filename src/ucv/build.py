"""Byte-preserving RTL closures and independently smoked native builds. MPL-2.0."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
import keyword
import os
from pathlib import Path
import re
import shutil
import tempfile
from .common import UcvError, activate, digest, execute, file_hash, lock, now, read, write
from .sources import generate, source_key

MODULE = re.compile(r'^\s*module\s+(\w+)', re.M)
INSTANCE = re.compile(r'^[ \t]*(\w+)[ \t]+(?:#\s*\([^;]*?\)\s*)?(\w+)[ \t]*\(',re.M)
KEYWORDS = set('module input output inout wire reg logic assign always always_ff always_comb always_latch initial if else case casez casex endcase for while return begin end function endfunction automatic task endtask generate endgenerate genvar parameter localparam typedef struct enum packed signed unsigned unique priority default break continue wait disable forever repeat assert cover assume'.split())

def closure(source, top):
    providers, children = {}, {}
    files = sorted([*Path(source).rglob('*.sv'), *Path(source).rglob('*.v')])
    for path in files:
        body = re.sub(r'/\*.*?\*/|//[^\n]*','',path.read_text(),flags=re.S)
        children[path] = {m for m,_ in INSTANCE.findall(body) if m not in KEYWORDS}
        for module in MODULE.findall(body):
            if module in providers:
                raise UcvError(f'Ambiguous RTL module {module}: {path}, {providers[module]}')
            providers[module] = path
    todo, seen, needed = [top], set(), set()
    while todo:
        module = todo.pop()
        if module in seen:continue
        seen.add(module)
        if module not in providers:
            raise UcvError(f'Unresolved RTL module {module} in closure of {top}')
        path = providers[module]
        needed.add(path)
        todo.extend(children[path]-seen)
    # Include headers are part of the closure and have their own content hashes.
    for path in list(needed):
        for name in re.findall(r'`include\s+"([^"]+)"',path.read_text()):
            include=path.parent/name
            if not include.is_file():raise UcvError(f'Missing RTL include: {include}')
            needed.add(include)
    if len({p.name for p in needed})!=len(needed):
        raise UcvError('Closure has colliding file names')
    return sorted(needed)

def prepare(project, suite, dut):
    if dut not in suite.recipe['duts']:raise UcvError(f'Unknown DUT {suite.name}/{dut}')
    spec = suite.recipe['duts'][dut]
    base = project.root/'.cache/duts'/project.cache_key(suite,dut)
    rtl = base/'rtl'
    receipt = rtl/'source.json'
    with lock(project.root/'.cache/locks'/('prepare-'+base.name)):
        if receipt.exists():
            data = read(receipt)
            if any(file_hash(rtl/name)!=h for name,h in data['files'].items()):
                raise UcvError(f'RTL closure cache changed: {rtl}')
        else:
            source = generate(project,suite,dut)
            needed = closure(source,spec['top'])
            rtl.mkdir(parents=True,exist_ok=True)
            for path in needed:shutil.copy2(path,rtl/path.name)
            files = {p.name:file_hash(p) for p in needed}
            (rtl/'filelist.f').write_text(''.join(p.name+'\n' for p in needed if p.suffix in {'.v','.sv'}))
            write(receipt,{'key':dut,**spec,'files':files,'baseline':suite.baseline,
                           'source':str(source),'cache_key':base.name,'created_at':now()})
        activate(suite.path/'rtl'/dut,rtl)
        # Existing contracts cite paths relative to the suite. Resolve that
        # compatibility entry to this suite's complete effective baseline.
        activate(suite.path/'XiangShan',project.root/'.cache/sources'/source_key(suite.baseline))
        # VAGQ's verification package addresses its original flat RTL names.
        if suite.name=='vagq':
            for name in read(receipt)['files']:
                activate(suite.path/'rtl'/name,rtl/name)
    return base

SMOKE = r'''
import importlib.util, sys
from pathlib import Path
p=Path(sys.argv[1]); name=sys.argv[2]
spec=importlib.util.spec_from_file_location('ucv_native_smoke',p/'__init__.py',submodule_search_locations=[str(p)])
m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)
d=getattr(m,'DUT'+name)(waveform_filename='',coverage_filename='')
try:
    assert m.xsp.abi_version()==3 and m.xsp.XTriggerEngine.CoverageVersion()==5
    assert d.dut.GetXSignalCFGBasePtr() and d.GetCovMetrics() & 1
    pins=set(d.xport.GetKeys())
    for s in vars(d).values():
        if callable(getattr(s,'IsInIO',None)) and s.IsInIO() and not s.IsOutIO():
            s.AsImmWrite(); s.Set(0)
    if 'clock' in pins:
        d.InitClock('clock')
        if 'reset' in pins:d.reset.Set(1)
        d.Step(4)
        if 'reset' in pins:d.reset.Set(0)
        d.Step(4)
    else:d.Step(1)
finally:d.Finish()
print('UCV_SMOKE_PASS')
'''

def repair_python_keywords(path):
    """Picker 4dd442c emits reserved public port names as Python attributes."""
    original = path.read_text()
    text = original
    # Only an attribute that is exactly a Python keyword is changed; signal
    # names, offsets and RTL remain identical.
    for word in keyword.kwlist:
        text = re.sub(rf'(?m)^(\s*)self\.{word}\s*=\s*(.*)$',
                      lambda m:f'{m[1]}setattr(self, {word!r}, {m[2]})',text)
        text = re.sub(rf'\bself\.{word}\b',f'getattr(self, {word!r})',text)
    if text!=original:path.write_text(text)
    return {'before':digest(original),'after':digest(text),'changed':text!=original}

def build(project, suite, dut, jobs=4):
    base = prepare(project,suite,dut)
    spec = suite.recipe['duts'][dut]
    package = base/'dut'
    receipt = base/'build.json'
    with lock(project.root/'.cache/locks'/('build-'+base.name)):
        if receipt.exists():
            record = read(receipt)
            if record.get('smoke')!='PASS' or any(file_hash(package/p)!=h for p,h in record['outputs'].items()):
                raise UcvError(f'Native build cache changed: {package}')
        else:
            if package.exists():
                # Failed attempts remain reviewable, never silently accepted.
                package.rename(base/('failed-dut-'+str(__import__('time').time_ns())))
            env = project.environment()
            command = [project.root/'.tools/bin/picker','export',spec['top']+'.sv','--fs','filelist.f',
                       '--sname',spec['top'],'--tname',spec['export_name'],'--tdir',package,
                       '--rw','mem_direct','-w','memory-direct.fst','-c',
                       '--vflag='+project.config.get('build_options',{}).get('vflag','--no-coverage-expr --no-coverage-fsm'),'--lang','python',
                       '--cp_lib','1','--autobuild','true','-j',str(jobs)]
            execute(command,cwd=base/'rtl',env=env,log=base/'build.log')
            tname=spec['export_name']
            expected=['__init__.py','signals.json',tname+'_offset.yaml','_UT_'+tname+'.so','libUT'+tname+'.so']
            if any(not (package/p).is_file() or not (package/p).stat().st_size for p in expected):
                raise UcvError(f'Picker did not produce a complete package: {package}; see {base}/build.log')
            binding_fix = repair_python_keywords(package/'__init__.py')
            with tempfile.TemporaryDirectory(prefix='smoke-',dir=base) as temp:
                execute([project.root/'.venv/bin/python','-c',SMOKE,package,tname],cwd=temp,env=env,log=base/'smoke.log')
            record = {'suite':suite.name,'dut':dut,**spec,'cache_key':base.name,
                      'baseline':suite.baseline,'rtl':read(base/'rtl/source.json')['files'],
                      'tools':project.tools,'command':list(map(str,command)),'smoke':'PASS',
                      'python_keyword_fix':binding_fix,'completed_at':now(),
                      'coverage_processor':str(project.root/'.tools/verilator/bin/verilator_coverage'),
                      'outputs':{p:file_hash(package/p) for p in expected}}
            write(receipt,record)
            write(package/'provenance.json',record)
        activate(suite.path/'dut'/dut,package)
    return record

def build_many(project, suites, duts=None, jobs=16, prepare_only=False):
    tasks=[]
    for suite in suites:
        keys=list(suite.recipe['duts']) if not duts else duts
        for key in keys:
            if key not in suite.recipe['duts']:raise UcvError(f'Unknown DUT {suite.name}/{key}')
            tasks.append((suite,key))
    if not tasks:raise UcvError('No DUTs selected')
    from .validation import installed_tools
    installed_tools(project,runtime=not prepare_only)
    with ExitStack() as stack:
        for suite in sorted(suites,key=lambda item:item.name):
            stack.enter_context(lock(project.root/'.cache/locks'/('suite-run-'+suite.name)))
        width=min(len(tasks),max(1,jobs//4))
        per_job=max(1,jobs//width)
        results=[]
        with ThreadPoolExecutor(max_workers=width) as pool:
            futures={pool.submit(prepare if prepare_only else build,project,suite,key,
                                **({} if prepare_only else {'jobs':per_job})):(suite.name,key) for suite,key in tasks}
            for future in as_completed(futures):
                name,key=futures[future]
                try:
                    value=future.result()
                    print(f'{name}/{key}: {"PREPARED" if prepare_only else "BUILT + SMOKE PASS"}',flush=True)
                    results.append({'suite':name,'dut':key,'status':'PASS'})
                except Exception as error:
                    print(f'{name}/{key}: ERROR: {error}',flush=True)
                    results.append({'suite':name,'dut':key,'status':'ERROR','error':str(error)})
    write(project.root/'.ucv/last-build.json',{'completed_at':now(),'results':results})
    return results
