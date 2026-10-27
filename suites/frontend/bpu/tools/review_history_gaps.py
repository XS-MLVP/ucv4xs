"""On-demand PHR guard/residue attribution; never rewrites native coverage."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from bpuverify.bpu.coverage.history_gaps import SOURCE,MODEL,local_claims,constrained_claims
from bpuverify.common.coverage.local_guards import ROOT,Source,match_native,native_points


def review(baseline,*,native_report=None,assume_owned_checkpoints=False):
    if type(assume_owned_checkpoints) is not bool:
        raise ValueError('owned-checkpoint constraint must be explicitly boolean')
    baseline=Path(baseline).resolve()
    path=(baseline/'diagnostic-rtl-line-coverage.json') if native_report is None else Path(native_report).resolve()
    assert path.is_relative_to(baseline),'native report must belong to the frozen run'
    report=json.loads(path.read_text());epoch=json.loads((baseline/'source-epoch.json').read_text())
    source=Source(SOURCE)
    assert epoch[str(ROOT/SOURCE)]==source.sha256,'stale RTL source'
    assert epoch[str(ROOT/MODEL)]==sha256((ROOT/MODEL).read_bytes()).hexdigest(),'stale semantic model'
    manifest=json.loads((baseline/'pytest-artifacts/rtl-coverage-manifest.json').read_text())
    inputs=[Path(item).resolve() for item in manifest['files'] if '/native/bpu/' in item]
    assert inputs and all(item.is_relative_to(baseline) for item in inputs)
    points=native_points(inputs[0])
    local=local_claims(source)
    raw={(row['file'],row['line']) for row in report['dut']['bpu']['uncovered_rtl_source_lines']}
    conditional,contract=constrained_claims(source,raw) if assume_owned_checkpoints else ([],None)
    native=match_native([*local,*conditional],report,'bpu',points)
    unclassified=[row for row in native['unclassified'] if row[0]==SOURCE]
    return dict(format='bpu-phr-gap-attribution',version=1,baseline=str(baseline),
        native_report=str(path),native_pytest_exitstatus=report['pytest_exitstatus'],
        source_sha256=source.sha256,native_schema_sha256=sha256(inputs[0].read_bytes()).hexdigest(),
        scope='local guards plus OPTIONAL owned-checkpoint constraint; NOT unrestricted-input reachability or functional PASS',
        phr_missing=sum(file==SOURCE for file,line in raw),local_guard_keys=len(local),
        conditional_cursor_keys=len(conditional),assume_owned_checkpoints=assume_owned_checkpoints,
        cursor_contract=contract,unclassified=unclassified,claims=native['claims'],native_points=native['native_points'],
        native_denominator_unchanged=True,functional_pass_credit=False,whole_design_formal_claim=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--native-report',type=Path)
    parser.add_argument('--assume-owned-checkpoints',action='store_true',
        help='Explicit conditional analysis: reset plus redirect/S2/S3 checkpoints from this history epoch; not arbitrary metadata')
    args=parser.parse_args()
    result=review(args.baseline,native_report=args.native_report,assume_owned_checkpoints=args.assume_owned_checkpoints)
    print(json.dumps({**{key:result[key] for key in ('phr_missing','local_guard_keys','conditional_cursor_keys',
        'assume_owned_checkpoints','native_denominator_unchanged','functional_pass_credit','whole_design_formal_claim')},
        'unclassified_count':len(result['unclassified'])}))


if __name__=='__main__':main()
