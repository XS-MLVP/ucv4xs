"""Suite subprocesses, BPU native isolation and bounded workers. MPL-2.0."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from datetime import datetime, timezone
import os
from pathlib import Path
import uuid
from .common import UcvError, digest, execute, file_hash, lock, now, read, write
from .sources import git

def source_identity(project,suites):
    files={}
    for directory in [project.root/'src',project.root/'baselines',project.root/'recipes',*[s.path for s in suites]]:
        for p in directory.rglob('*'):
            if p.is_file() and p.suffix in {'.py','.ini','.json','.toml','.scala','.patch'} and not p.is_symlink() and not {'rtl','dut','results','__pycache__'} & set(p.relative_to(directory).parts):
                files[str(p.relative_to(project.root))]=file_hash(p)
    for p in [project.root/'ucv.json',project.root/'dependencies/versions.json',project.root/'dependencies/python.txt']:
        files[str(p.relative_to(project.root))]=file_hash(p)
    try:
        commit=git(project.root,'rev-parse','HEAD')
        status=git(project.root,'status','--porcelain=v1')
    except UcvError:commit=None;status='uncommitted repository'
    return {'git_commit':commit,'git_status':status,'files':files,'sha256':digest(files)}

def run(project,suites,workers=8,seed=1,pytest_args=None,collect_only=False,output=None):
    if workers<1:raise UcvError('workers must be positive')
    extra=list(pytest_args or [])
    if any(a.startswith(('--toffee-output','--rootdir','--override-ini','--junitxml','--bpu-dut-scope','--bpu-partition','-n','--numprocesses')) for a in extra):
        raise UcvError('ucv owns output, pytest roots, BPU partitioning and worker budgets')
    python=project.root/'.venv/bin/python'
    if not python.exists():raise UcvError('Run ucv setup first')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    output=Path(output).resolve() if output else project.root/'results'/stamp
    if output.exists():raise UcvError(f'Output must be new: {output}')
    # Missing external source is an error even if a stale package is present.
    for suite in suites:
        if suite.baseline['visibility']=='internal':
            source=project.local.get('source_mirrors',{}).get(suite.baseline['name'])
            if not source or not Path(source).is_dir():raise UcvError(f'Missing external source for {suite.name}')
    output.mkdir(parents=True)
    record={'schema':1,'started_at':now(),'source':source_identity(project,suites),
            'suites':[s.summary() for s in suites], 'mixed_baseline':len({s.baseline_key for s in suites})>1,
            'tools':project.tools,'seed':seed,'workers':workers,'pytest_args':extra,
            'collect_only':collect_only,'tasks':[],'status':'RUNNING'}
    write(output/'run.json',record)
    tasks=[]
    try:
        with ExitStack() as stack:
            for suite in sorted(suites,key=lambda s:s.name):
                stack.enter_context(lock(project.root/'.cache/locks'/('suite-run-'+suite.name)))
            for suite in suites:
                env=project.environment()
                env.update(PYTHONPATH=str(project.root/'src')+os.pathsep+str(suite.path),
                           UCV_SEED=str(seed),PYTHONHASHSEED=str(seed),DCACHE_TEST_RANDOM_SEED=str(seed))
                flags=['-q','-p','no:cacheprovider','-p','ucv.pytest_plugin','--durations=20',
                       '-c',str(suite.path/'pytest.ini'),'--rootdir='+str(suite.path)]
                # A suite keeps its own pytest.ini and collection root.
                tests=[str(suite.path/p) for p in suite.recipe.get('tests',['tests'])]
                builds={}
                if not collect_only:
                    for dut in suite.recipe['duts']:
                        base=project.root/'.cache/duts'/project.cache_key(suite,dut)
                        receipt=read(base/'build.json')
                        if (suite.path/'dut'/dut).resolve() != (base/'dut').resolve():
                            raise UcvError(f'{suite.name}/{dut}: active DUT does not match the effective baseline; run ucv build')
                        if receipt.get('smoke')!='PASS' or receipt['baseline']!=suite.baseline:
                            raise UcvError(f'{suite.name}/{dut}: no valid build and smoke receipt')
                        for name,h in receipt['outputs'].items():
                            if file_hash(base/'dut'/name)!=h:raise UcvError(f'Native package changed: {suite.name}/{dut}')
                        builds[dut]={'cache_key':base.name,'rtl':receipt['rtl'],'outputs':receipt['outputs']}
                    write(output/(suite.name+'-builds.json'),builds)
                if suite.name=='bpu':
                    partition=output/'bpu-partition.json'
                    env['UCV_CASE_DIR']=str(output/'collection/bpu')
                    command=[python,'-m','pytest',*tests,*flags,'--collect-only',
                             '--bpu-write-partition',partition,*extra]
                    execute(command,cwd=suite.path,env=env,log=output/'logs/bpu-collection.log')
                    index=read(partition)
                    if collect_only:
                        record['tasks'].append({'suite':'bpu','scope':'collection','status':'PASS','exit_code':0,
                                                'cases':str((output/'collection/bpu/cases.json').relative_to(output))})
                        continue
                    scopes=list(dict.fromkeys(row['scope'] for row in index['cases']))
                    for scope in scopes:
                        task_env={**env,'BPUVERIFY_DUT_SCOPE':scope}
                        args=[*flags,'--bpu-dut-scope',scope,'--bpu-partition-index',partition,
                              '--bpu-partition-sha256',file_hash(partition),*extra]
                        tasks.append((suite,scope,task_env,tests,args))
                else:
                    tasks.append((suite,'suite',env,tests,[*flags,*(['--collect-only'] if collect_only else []),*extra]))
            width=min(len(tasks),len(suites),workers) or 1
            per_task=max(1,workers//width)
            def one(task):
                suite,scope,env,tests,flags=task
                label=suite.name+('-'+scope if scope!='suite' else '')
                target=output/label
                env={**env,'UCV_CASE_DIR':str(output/'cases'/label)}
                command=[python,'-m','toffee','run',*tests,'--workers',str(1 if collect_only else per_task),
                         '--output',target,'--native-coverage-tool',project.root/'.tools/verilator/bin/verilator_coverage',
                         *flags]
                result=execute(command,cwd=suite.path,env=env,log=output/'logs'/(label+'.log'),check=False)
                row={'suite':suite.name,'scope':scope,'exit_code':result.returncode,
                     'status':'PASS' if result.returncode==0 else 'FAIL',
                     'command':list(map(str,command)),'output':label,'cases':'cases/'+label+'/cases.json'}
                if not (output/row['cases']).exists():row['status']='ERROR'
                print(f'{label}: {row["status"]} (exit {result.returncode})',flush=True)
                return row
            with ThreadPoolExecutor(max_workers=width) as pool:
                for future in as_completed([pool.submit(one,t) for t in tasks]):
                    record['tasks'].append(future.result())
                    write(output/'run.json',record)
            record['status']='PASS' if all(t['status']=='PASS' for t in record['tasks']) else 'FAIL'
    except BaseException as error:
        record['status']='ERROR';record['error']=str(error)
        raise
    finally:
        record['completed_at']=now()
        record['source_after']=source_identity(project,suites)['sha256']
        if record['source_after']!=record['source']['sha256']:
            record['status']='ERROR';record['source_changed_during_run']=True
        write(output/'run.json',record)
        write(project.root/'.ucv/last-run.json',{'path':str(output)})
    return output,record
