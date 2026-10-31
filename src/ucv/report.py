"""Keep hardware verdicts separate from migration acceptance. MPL-2.0."""
from collections import Counter
from pathlib import Path
from .common import read, write, file_hash

def report(directory,compare=None):
    directory=Path(directory)
    run=read(directory/'run.json')
    counts=Counter();suites={};cases={};gaps=[];artifacts=[];declarations={};uncertainties={}
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
            if isinstance(row.get('declared_incomplete'),dict):
                declarations[identity]=row['declared_incomplete']
            if row['verdict']=='UNCERTAIN':
                uncertainties[identity]=row.get('uncertain',{})
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
            elif 'uncertain' in evidence:
                # New Toffee manifests and case receipts share its classifier.
                # Legacy manifests predate this vocabulary; preserve their
                # original counts rather than reinterpret historical runs.
                expected=dict(Counter(row['verdict'] for row in data['cases'].values()))
                if evidence.get('tests')!=expected:
                    gaps.append(f"Runner/case verdict mismatch: {task['suite']}/{task['scope']}")
                expected_uncertain=[{'nodeid':node,**row.get('uncertain',{})}
                                    for node,row in sorted(data['cases'].items())
                                    if row['verdict']=='UNCERTAIN']
                if evidence['uncertain']!=expected_uncertain:
                    gaps.append(f"Runner/case UNCERTAIN declarations differ: {task['suite']}/{task['scope']}")
            for item in evidence.get('artifacts',[]):
                path=Path(item['path'])
                if not path.is_absolute():path=manifest.parent/path
                if not path.is_file() or file_hash(path)!=item['sha256']:
                    gaps.append('Missing/changed coverage artifact: '+str(path))
                artifacts.append({'suite':task['suite'],'scope':task['scope'],**item})
    residuals=[];residual_gaps=[]
    for suite in run['suites']:
        for row in suite.get('residuals',[]):
            residuals.append({'suite':suite['suite'],**row})
            if row.get('blocking') and row.get('acceptance')=='open':
                residual_gaps.append(f"Open blocking residual {row['id']} ({suite['suite']}): "
                                     +str(row.get('next_action') or 'no next action'))
    declared_incomplete=[];undeclared_incomplete=[]
    for identity,value in sorted(cases.items()):
        if value!='INCOMPLETE':continue
        suite,_,node=identity.partition('::')
        declaration=declarations.get(identity)
        if declaration:declared_incomplete.append({'suite':suite,'nodeid':node,**declaration})
        else:undeclared_incomplete.append(identity)
    # A real failure outranks every softer signal: coverage gaps, an open
    # residual or a harness-incomplete case must not downgrade FAIL to
    # INCOMPLETE and hide the defect.
    if counts['FAIL'] or counts['ERROR'] or counts['XPASS']:
        hardware='FAIL'
        if residual_gaps:gaps.extend(residual_gaps)
    elif (not counts or counts['INCOMPLETE'] or gaps or run.get('collect_only')
          or residual_gaps):
        hardware='INCOMPLETE'
        if residual_gaps:gaps.extend(residual_gaps)
        if undeclared_incomplete:
            gaps.append(f"Undeclared incomplete case(s) {len(undeclared_incomplete)}: "
                        "the harness did not complete them; see cases.json")
    else:
        hardware='UNCERTAIN' if counts['UNCERTAIN'] else 'PASS'
    uncertain=[{'suite':identity.partition('::')[0],
                'nodeid':identity.partition('::')[2],**row}
               for identity,row in sorted(uncertainties.items())]
    result={'run':str(directory),'run_status':run['status'],'hardware_verdict':hardware,
            'migration_acceptance':'NOT_CERTIFIED','counts':dict(counts),
            'suites':{s:dict(c) for s,c in suites.items()},'baselines':run['suites'],
            'mixed_baseline':run['mixed_baseline'],'gaps':gaps,'cases':cases,
            'residuals':residuals,
            'uncertain':uncertain,
            'declared_incomplete':declared_incomplete,
            'incomplete_summary':{'declared':len(declared_incomplete),
                'undeclared':len(undeclared_incomplete)},
            'residual_summary':{'total':len(residuals),
                'blocking_open':sum(1 for r in residuals if r.get('blocking') and r.get('acceptance')=='open'),
                'by_category':dict(Counter(str(r.get('category')) for r in residuals)),
                'by_acceptance':dict(Counter(str(r.get('acceptance')) for r in residuals))},
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
    if residuals:
        summary_counts=result['residual_summary']
        lines+=['','Residual register (unproven scope; not a test status):',
                f"- total {summary_counts['total']}, blocking+open {summary_counts['blocking_open']}, "
                f"categories {summary_counts['by_category']}"]
        for suite in run['suites']:
            rows=suite.get('residuals',[])
            if not rows:continue
            open_rows=[r for r in rows if r.get('acceptance')!='resolved']
            lines.append('- '+suite['suite']+': '+', '.join(
                f"{r['id']}[{r['category']}{', blocking' if r.get('blocking') else ''}]"
                for r in open_rows if r.get('acceptance')!='resolved'))
        lines+=['- Resolving these needs evidence or an explicit scope limitation; a residual never turns into PASS by being recorded.']
    if declared_incomplete:
        lines+=['','Declared incomplete (partial coverage; the test ran and its checks passed):']
        for row in declared_incomplete:
            lines.append(f"- {row['suite']}::{row['nodeid']}: {row['reason']} [{row['residual']}]")
        lines+=['- Counted as INCOMPLETE, never as PASS: a test that covers part of its point must not look green.']
    if uncertain:
        lines+=['','UNCERTAIN (tests executed; evidence is not yet sufficient):']
        for row in uncertain:
            reference=f" [{row['reference']}]" if row.get('reference') else ''
            lines.append(f"- {row['suite']}::{row['nodeid']}: {row.get('reason','reason missing')}{reference}")
        lines+=['- Not counted as PASS. UNCERTAIN alone does not change the command exit code.']
    lines+=['','Counts include infrastructure and model tests. Hardware acceptance must also review each suite\'s functional points, known failures and skips.']
    (directory/'summary.md').write_text('\n'.join(lines)+'\n')
    return result
