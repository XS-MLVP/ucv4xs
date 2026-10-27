"""Review every original failing shape, with per-item falsifiable checks."""
from collections import Counter
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.run_vagq_exhaustive import atomic_json, digest
from vagqverify.vagq.failure_review import analyze_failure
from vagqverify.vagq.scenario_matrix import legal_public_feature_cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    original, out = args.original.resolve(), args.output.resolve()
    frozen = json.loads((original / 'full/source-hashes.json').read_text())
    for name, expected in frozen.items():
        assert digest(ROOT / name) == expected, f'frozen source changed: {name}'
    rows = json.loads((original / 'failed-shapes.json').read_text())
    cases = tuple(legal_public_feature_cases())
    assert len(rows) == 2278 and len({r['ordinal'] for r in rows}) == 2278
    reviews = [analyze_failure(row, cases[row['ordinal']]) for row in rows]
    out.mkdir(parents=True, exist_ok=True)
    atomic_json(out / 'case-review.json', reviews)
    summary = dict(reviewed=len(reviews), distinct=len({r['shape_id'] for r in reviews}),
        by_family=dict(Counter(r['family'] for r in reviews)),
        all_checks_satisfied=sum(r['all_checks_satisfied'] for r in reviews),
        unresolved=[dict(ordinal=r['ordinal'], shape_id=r['shape_id'],
            failed_checks=[name for name, passed in r['checks'].items() if not passed])
            for r in reviews if not r['all_checks_satisfied']],
        review_scope='offline causal/source equations; native replay is separate',
        source_epoch_unchanged=True)
    atomic_json(out / 'analysis-summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
