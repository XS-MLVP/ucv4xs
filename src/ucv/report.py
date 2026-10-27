"""Keep hardware verdicts separate from migration acceptance. MPL-2.0."""
from collections import Counter
from pathlib import Path
from .common import read, write, file_hash

def report(directory,compare=None):
    directory=Path(directory)
    run=read(directory/'run.json')
    counts=Counter();suites={};cases={};gaps=[];artifacts=[]
    if run['status']=='ERROR':gaps.append('Run integrity error: '+run.get('error','verification source changed during execution'))
    if run['status']=='RUNNING':gaps.append('Run has not completed')
    for task in run['tasks']:
        path=directory/task['cases']
        if not path.exists():
            gaps.append(f"Missing case receipt: {task['suite']}/{task['scope']}");continue
        data=read(path)
        for node,row in data['cases'].items():
            identity=task['suite']+'::'+node
            if identity in cases:gaps.append('Duplicate execution identity: '+identity)
            cases[identity]=row['verdict']
            counts[row['verdict']]+=1
            suites.setdefault(task['suite'],Counter())[row['verdict']]+=1
        if not data['collect_only'] and set(data['collected'])!=set(data['cases']):
            gaps.append(f"Collection/execution mismatch: {task['suite']}/{task['scope']}")
        if not run.get('collect_only') and task.get('output'):
            manifest=directory/task['output']/'manifest.json'
            if not manifest.exists():
                gaps.append(f"Missing runner manifest: {task['suite']}/{task['scope']}")
                continue
            evidence=read(manifest)
            if evidence.get('state')!='committed' or not evidence.get('coverage_complete'):
                gaps.append(f"Uncommitted/incomplete coverage: {task['suite']}/{task['scope']}")
            for item in evidence.get('artifacts',[]):
                path=Path(item['path'])
                if not path.is_absolute():path=manifest.parent/path
                if not path.is_file() or file_hash(path)!=item['sha256']:
                    gaps.append('Missing/changed coverage artifact: '+str(path))
                artifacts.append({'suite':task['suite'],'scope':task['scope'],**item})
    hardware='FAIL' if counts['FAIL'] or counts['ERROR'] or counts['XPASS'] else 'PASS'
    if not counts or counts['INCOMPLETE'] or gaps or run.get('collect_only'):
        hardware='INCOMPLETE'
    result={'run':str(directory),'run_status':run['status'],'hardware_verdict':hardware,
            'migration_acceptance':'NOT_CERTIFIED','counts':dict(counts),
            'suites':{s:dict(c) for s,c in suites.items()},'baselines':run['suites'],
            'mixed_baseline':run['mixed_baseline'],'gaps':gaps,'cases':cases,
            'coverage_artifacts':artifacts,
            'coverage_reports':[str(p.relative_to(directory)) for p in directory.rglob('*')
                                 if p.is_file() and p.name in {'coverage.json','coverage.html','index.html'}]}
    if compare:
        prior=read(Path(compare)/'summary.json')
        old=prior['cases']
        before={s['suite']:s['baseline_fingerprint'] for s in prior['baselines']}
        after={s['suite']:s['baseline_fingerprint'] for s in result['baselines']}
        result['comparison']={'same_baseline_suites':[s for s in before if before[s]==after.get(s)],
            'changed_baseline_suites':[s for s in before if s in after and before[s]!=after[s]],
            'added':sorted(cases.keys()-old.keys()),'removed':sorted(old.keys()-cases.keys()),
            'changed':{k:{'before':old[k],'after':cases[k]} for k in cases.keys() & old.keys() if cases[k]!=old[k]}}
    write(directory/'summary.json',result)
    lines=[f"Run: {directory.name}",f"Hardware verdict: {hardware}",
           'Migration/rebuild acceptance: NOT_CERTIFIED (requires acceptance evidence)',
           'Baseline: '+('MIXED' if run['mixed_baseline'] else 'UNIFIED'),'',
           '| Suite | Baseline | Inherited from | Counts |','|---|---|---|---|']
    for suite in run['suites']:
        lines.append(f"| {suite['suite']} | {suite['baseline']} | {suite['inherited_from']} | {dict(suites.get(suite['suite'],{}))} |")
    lines+=['','Verification gaps:',*['- '+g for g in gaps]]
    lines+=['','Counts include infrastructure and model tests. Hardware acceptance must also review each suite\'s functional points, known failures and skips.']
    (directory/'summary.md').write_text('\n'.join(lines)+'\n')
    return result
