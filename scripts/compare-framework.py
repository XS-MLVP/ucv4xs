#!/usr/bin/env python3
"""Replay migrated benches against frozen historical native/RTL artifacts.

This is a framework comparison, not acceptance of a reconstructed baseline.
Original workspaces remain read-only. All temporary copies and outputs are ignored.
SPDX-License-Identifier: MPL-2.0
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime,timezone
import os
from pathlib import Path
import shutil
import sys
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ucv.common import execute,file_hash,now,read,write
from ucv.config import Project

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('suites',nargs='+')
    parser.add_argument('--workers',type=int,default=32)
    args=parser.parse_args()
    if args.workers<1:parser.error('workers must be positive')
    project=Project();root=project.root
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    output=root/'results'/('framework-comparison-'+stamp)
    output.mkdir(parents=True)
    view=root/'.history/framework-comparison'/stamp
    tasks=[]
    record={'kind':'same-RTL-framework-comparison','started_at':now(),
            'named_baseline_acceptance':False,'worker_budget':args.workers,'inputs':{},'tasks':[]}
    for suite in project.select(args.suites):
        original=Path(project.local.get('historical_roots',{}).get(suite.name,''))
        if not original.is_dir():raise RuntimeError(f'Missing historical source: {suite.name}')
        target=view/suite.name
        # BPU's current bench targets DefaultConfig. Its pre-port toffee
        # snapshot is the only comparable input for the historical Minimal RTL.
        bench = root/'.history/bpu-before-default-port' if suite.name=='bpu' else suite.path
        if not bench.is_dir():raise RuntimeError('Missing frozen framework-only bench: '+str(bench))
        shutil.copytree(bench,target,ignore=shutil.ignore_patterns('rtl','dut','results','__pycache__','.pytest_cache'))
        (target/'rtl').symlink_to(original/'rtl',target_is_directory=True)
        # Coverage requires canonical native-package ownership below this root.
        # A cross-workspace symlink changes that ownership even with equal bytes.
        shutil.copytree(original/'dut',target/'dut',symlinks=False)

        snapshot=read(root/'docs/history'/f'{suite.name}-source.json')
        files=snapshot['artifacts']
        for relative,data in files.items():
            if file_hash(original/relative)!=data['sha256']:
                raise RuntimeError(f'Historical artifact changed: {suite.name}/{relative}')
        record['inputs'][suite.name]={'artifact_index_sha256':file_hash(root/'docs/history'/f'{suite.name}-source.json'),
            'verification_files':{str(p.relative_to(target)):file_hash(p) for p in target.rglob('*.py')
                                  if not p.is_symlink() and 'dut' not in p.relative_to(target).parts},
            'input_boundary_adapter':None}
        if suite.name=='vagq':
            # Both old/new benches use exactly the same original files. Only the
            # receipt reader changes in this disposable copy: old flat artifacts
            # have no ucv generated-closure receipt. No model/checker is changed.
            write(target/'replay-inputs.json',{k:v['sha256'] for k,v in files.items() if k.startswith('rtl/')})
            path=target/'vagqverify/native.py';text=path.read_text()
            a=text.index('def verify_rtl():');b=text.index('\n\ndef public_signals',a)
            text=text[:a]+'''def verify_rtl():
    from ucv.common import read, file_hash
    for relative, expected in read(ROOT/'replay-inputs.json').items():
        if file_hash(ROOT/relative) != expected:
            raise RuntimeError(f'Frozen framework-comparison input changed: {relative}')
'''+text[b:]
            path.write_text(text)
            record['inputs'][suite.name]['input_boundary_adapter']={'path':'vagqverify/native.py','sha256':file_hash(path),
                'purpose':'Validate the exact historical flat RTL hashes instead of new generated-closure receipt layout'}
        env=project.environment()
        env.update(PYTHONPATH=str(root/'src')+os.pathsep+str(target),UCV_SEED='1',PYTHONHASHSEED='1')
        flags=['-q','-p','no:cacheprovider','-p','ucv.pytest_plugin','-c',str(target/'pytest.ini'),
               '--rootdir='+str(target),'--durations=10']
        if suite.name=='bpu':
            index=output/'bpu-partition.json';env['UCV_CASE_DIR']=str(output/'collection/bpu')
            execute([root/'.venv/bin/python','-m','pytest',target/'tests',*flags,'--collect-only',
                     '--bpu-write-partition',index],cwd=target,env=env,log=output/'logs/bpu-collection.log')
            for scope in dict.fromkeys(row['scope'] for row in read(index)['cases']):
                tasks.append((suite.name,scope,target,{**env,'BPUVERIFY_DUT_SCOPE':scope},
                    [*flags,'--bpu-dut-scope',scope,'--bpu-partition-index',str(index),
                     '--bpu-partition-sha256',file_hash(index)]))
        else:tasks.append((suite.name,'suite',target,env,flags))
    width=min(len(tasks),8,args.workers);per=max(1,args.workers//width)
    write(output/'framework-run.json',record)
    def one(task):
        name,scope,target,env,flags=task;label=name+'-'+scope
        env={**env,'UCV_CASE_DIR':str(output/'cases'/label)}
        result=execute([root/'.venv/bin/python','-m','toffee','run',target/'tests','--workers',str(per),
             '--output',output/label,'--native-coverage-tool',root/'.tools/verilator/bin/verilator_coverage',*flags],
             cwd=target,env=env,log=output/'logs'/(label+'.log'),check=False)
        print(label,result.returncode,flush=True)
        return {'suite':name,'scope':scope,'exit_code':result.returncode,'cases':'cases/'+label+'/cases.json'}
    with ThreadPoolExecutor(max_workers=width) as pool:
        for future in as_completed([pool.submit(one,t) for t in tasks]):
            record['tasks'].append(future.result());write(output/'framework-run.json',record)
    record['completed_at']=now();write(output/'framework-run.json',record)
    print(output)

if __name__=='__main__':main()
