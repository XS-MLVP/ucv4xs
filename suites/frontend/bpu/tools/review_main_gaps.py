"""On-demand Main entry-copy candidate association; no implicit export."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from suites.frontend.bpu.bpu.coverage.main_gaps import SOURCE,associate,producer_witnesses
from suites.frontend.bpu.coverage.local_guards import ROOT,native_points
from tools.coverage_delta import lcov_rows


def checked_input(path,evidence):
    receipt_path=path.parent.parent.parent/'receipt.json'
    controllers=[entry for entry in evidence['workers'] if entry['receipt']==str(receipt_path)]
    if len(controllers)!=1 or controllers[0]['sha256']!=sha256(receipt_path.read_bytes()).hexdigest():
        raise ValueError('Main worker receipt hash disagrees with controller')
    receipt=json.loads(receipt_path.read_text())
    entries=[entry for entry in receipt['files'] if entry['path']==str(path)]
    if len(entries)!=1 or entries[0]['sha256']!=sha256(path.read_bytes()).hexdigest():
        raise ValueError('Main native schema hash disagrees with worker receipt')
    return entries[0],receipt


def standalone_witnesses(result,baseline,integrated_report):
    baseline=Path(baseline).resolve();other='rtl/mbtb/WriteBuffer.sv'
    compiled=(ROOT/SOURCE).read_text().splitlines();isolated=(ROOT/other).read_text().splitlines()
    if compiled[:45]+compiled[46:]!=isolated[:45]+isolated[46:] or (
        compiled[45].split('//',1)[0].strip()!='module WriteBuffer_4(' or
        isolated[45].split('//',1)[0].strip()!='module WriteBuffer('):
        raise ValueError('standalone and integrated Main child bodies differ')
    epoch=json.loads((baseline/'source-epoch.json').read_text())
    for name in (SOURCE,other):
        if epoch.get(str(ROOT/name))!=sha256((ROOT/name).read_bytes()).hexdigest():
            raise ValueError('standalone witness uses stale compiled source')
    report=json.loads((baseline/'rtl-line-coverage.json').read_text())
    if report['dut']['mbtb']['build_provenance']!=integrated_report['dut']['mbtb']['build_provenance']:
        raise ValueError('standalone witness build differs from current diagnostic build')
    evidence=json.loads((baseline/'pytest-artifacts/evidence.json').read_text())
    if evidence['pytest_exitstatus']!=0 or not evidence['evidence_complete'] or evidence['integrity_errors']:
        raise ValueError('standalone path witness requires complete successful historical evidence')
    verdicts={test['nodeid']:test['status'] for test in evidence['tests']}
    manifest=json.loads((baseline/'pytest-artifacts/rtl-coverage-manifest.json').read_text())
    inputs=[Path(p).resolve() for p in manifest['files'] if '/native/mbtb/' in p]
    if not inputs or any(not p.is_relative_to(baseline) for p in inputs):raise ValueError('standalone native input escaped run')
    tests=set();points=[]
    for path in inputs:
        _,receipt=checked_input(path,evidence)
        names={row['nodeid'] for row in receipt['native_retention']['inputs'] if row['dut']=='mbtb'}
        if not names or any(verdicts.get(name)!='PASS' for name in names):
            raise ValueError('standalone merged input contains an unqualified test outcome')
        tests.update(names)
        points.extend((fields,count) for fields,count in native_points(path) if fields.get('f')==str(ROOT/other))
    witnesses=producer_witnesses(result['native_producers'],points,source_path=str(ROOT/other))
    return dict(scope='historical PASS-test aggregate demonstrates standalone compiled paths only; NOT current-worktree acceptance, isolated feature attribution or integrated FTQ legality',
        baseline=str(baseline),child_body_exact_except_module_header=True,build_provenance_unchanged=True,
        verified_native_inputs=len(inputs),qualified_input_test_count=len(tests),
        native_signatures=len(witnesses),observed_native_signatures=sum(w['observed'] for w in witnesses),
        witnesses=witnesses,functional_pass_credit=False,integrated_reachability_proved=False)


def review(baseline,*,standalone_baseline=None):
    baseline=Path(baseline).resolve()
    report_path=baseline/'diagnostic-rtl-line-coverage.json'
    report=json.loads(report_path.read_text());epoch=json.loads((baseline/'source-epoch.json').read_text())
    source=ROOT/SOURCE;text=source.read_text()
    if epoch.get(str(source))!=sha256(source.read_bytes()).hexdigest():raise ValueError('stale frozen Main source')
    row=report['dut']['bpu'];raw=row['uncovered_rtl_source_lines']
    lcov=lcov_rows(row['lcov_file'])
    if row['source_lines']!=dict(total=len(lcov),hit=sum(count>0 for count in lcov.values())):
        raise ValueError('Main review requires native report/LCOV agreement')
    expected={line for (file,line),count in lcov.items() if file==str(source) and count==0}
    if expected!={r['line'] for r in raw if r['file']==SOURCE}:raise ValueError('Main uncovered DA set is not exact')
    evidence=json.loads((baseline/'pytest-artifacts/evidence.json').read_text())
    if not evidence['evidence_complete'] or evidence['integrity_errors'] or evidence['pytest_exitstatus']!=report['pytest_exitstatus']:
        raise ValueError('Main review requires complete native pytest evidence, including its failure status')
    manifest=json.loads((baseline/'pytest-artifacts/rtl-coverage-manifest.json').read_text())
    inputs=[Path(p).resolve() for p in manifest['files'] if '/native/bpu/' in p]
    if not inputs or any(not p.is_relative_to(baseline) for p in inputs):raise ValueError('Main native inputs escaped frozen run')
    schema=inputs[0];entry,_=checked_input(schema,evidence)
    points=[(fields,count) for fields,count in native_points(schema) if fields.get('f')==str(source)]
    result=associate(raw,points,text,source_path=str(source))
    result.update(baseline=str(baseline),native_report=str(report_path),native_pytest_exitstatus=report['pytest_exitstatus'],
        native_schema=str(schema),native_schema_sha256=entry['sha256'],
        native_source_lines=row['source_lines'],measurement_current_for_worktree=False,
        analysis_code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        association_code_sha256=sha256((ROOT/'bpu/coverage/main_gaps.py').read_bytes()).hexdigest())
    if standalone_baseline is not None:result['standalone']=standalone_witnesses(result,standalone_baseline,report)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--standalone-baseline',type=Path)
    args=parser.parse_args();result=review(args.baseline,standalone_baseline=args.standalone_baseline)
    if args.output is not None:
        # Explicit report generation only; never replace an existing report.
        with args.output.open('x') as stream:
            json.dump(result,stream,indent=2);stream.write('\n')
    summary={key:result[key] for key in ('raw_missing','candidate_DA_counts','native_producer_count',
        'native_pytest_exitstatus','functional_pass_credit','rank_does_not_prove_simultaneous_pending_records')}
    if 'standalone' in result:
        summary['standalone']={key:result['standalone'][key] for key in ('verified_native_inputs','qualified_input_test_count',
            'native_signatures','observed_native_signatures','functional_pass_credit','integrated_reachability_proved')}
    print(json.dumps(summary))


if __name__=='__main__':main()
