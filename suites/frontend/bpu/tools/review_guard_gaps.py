"""On-demand local SC/TAGE/BPU guard review; never rewrites coverage."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from suites.frontend.bpu.coverage.local_guards import ROOT, match_native, native_points
from suites.frontend.bpu.sc.coverage.guard_audit import source_claims as sc_claims
from suites.frontend.bpu.tage.coverage.coverage_audit import source_claims as tage_claims
from suites.frontend.bpu.bpu.coverage.guard_audit import source_claims as bpu_claims


def review(baseline,*,duts=('sc','tage'),native_report=None):
    baseline = Path(baseline).resolve()
    report_path = baseline/'rtl-line-coverage.json' if native_report is None else Path(native_report).resolve()
    assert report_path.resolve().is_relative_to(baseline), 'native report must belong to the frozen run'
    report = json.loads(report_path.read_text())
    epoch = json.loads((baseline/'source-epoch.json').read_text())
    manifest = json.loads((baseline/'pytest-artifacts/rtl-coverage-manifest.json').read_text())
    results = {}
    factories = dict(sc=sc_claims,tage=lambda:tage_claims(report),bpu=lambda:bpu_claims(report))
    for dut in duts:
        factory = factories[dut]
        claims,sources = factory()
        for source in sources:
            assert epoch[str((ROOT/source['file']).resolve())]==source['sha256'],('stale native source',source)
        inputs = [Path(path).resolve() for path in manifest['files'] if f'/native/{dut}/' in path]
        assert inputs and all(path.is_relative_to(baseline) for path in inputs)
        # One worker carries the full compiled schema. Aggregate zero DA keys
        # come from the complete native report, not this worker's hit subset.
        schema = inputs[0]
        results[dut] = match_native(claims,report,dut,native_points(schema))
        results[dut].update(sources=sources,native_schema=str(schema),
                           native_schema_sha256=sha256(schema.read_bytes()).hexdigest())
    return dict(format='bpu-bounded-local-guard-classification',version=1,baseline=str(baseline),
        native_report=str(report_path),native_report_sha256=sha256(report_path.read_bytes()).hexdigest(),
        native_pytest_exitstatus=report['pytest_exitstatus'],
        scope='source guard contradictions plus exact native producers; NOT functional PASS or whole-design formal',dut=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--dut',choices=('sc','tage','bpu'),action='append')
    parser.add_argument('--native-report',type=Path)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    result = review(args.baseline,duts=tuple(args.dut) if args.dut else ('sc','tage'),native_report=args.native_report)
    if args.output is not None:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        # Explicit opt-in export; existing reports/source cannot be replaced.
        with args.output.open('x') as stream:
            json.dump(result,stream,indent=2)
            stream.write('\n')
    print(json.dumps({dut:dict({key:row[key] for key in ('raw_missing','locally_classified',
        'native_denominator_unchanged','functional_pass_credit')},unclassified_count=len(row['unclassified']))
        for dut,row in result['dut'].items()}))


if __name__=='__main__':
    main()
