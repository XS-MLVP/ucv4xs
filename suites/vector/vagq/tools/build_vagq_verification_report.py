"""Build an auditable VAGQ/RVV verification-metrics report.

This report intentionally keeps four different questions separate:

* what the independent RVV/public shape inventory contains;
* which marginal/pairwise/shape bins the generated-DUT campaign selected;
* which runtime handshake/lifecycle/value groups were observed; and
* which larger claims (formal, mutation, whole-chip memory effect) were not run.

The RVV denominator is imported from ``scenario_matrix`` and is therefore not
reconstructed from the generated RTL or from the functional-coverage result.
"""

from collections import Counter
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from vagqverify.vagq.scenario_matrix import (  # noqa: E402
    OPERATION_NAMES,
    PUBLIC_DIMENSIONS,
    feature_values,
    legal_public_feature_cases,
    pairwise_tokens,
    public_space_metadata,
    representative_public_feature_cases,
)


def _group(functional, instance):
    return next(
        (item for item in functional.get('groups', [])
         if item.get('instance') == instance),
        None,
    )


def _point(group, name):
    if group is None:
        return None
    return next((item for item in group.get('points', [])
                 if item.get('name') == name), None)


def _counts(point):
    return {} if point is None else point.get('counts', {})


def _point_metric(point, *, exclude=()):
    counts = _counts(point)
    eligible = {name: value for name, value in counts.items()
                if name not in set(exclude)}
    return {
        'total': len(eligible),
        'hit': sum(bool(value) for value in eligible.values()),
        'missed': sorted(name for name, value in eligible.items() if not value),
        'counts': eligible,
    }


def _cross_metrics(group):
    if group is None:
        return {'total': 0, 'hit': 0, 'missed': [], 'crosses': {}}
    result = {}
    total = hit = 0
    missed = []
    for cross in group.get('crosses', []):
        # toffee keeps hit counts in ``counts`` and the schema/bin metadata
        # in ``bins``.  The latter uses ``id`` rather than ``name``.
        counts = cross.get('counts', {})
        item = {
            'total': len(counts),
            'hit': sum(bool(value) for value in counts.values()),
            'missed': sorted(name for name, value in counts.items() if not value),
            'counts': counts,
        }
        result[cross.get('name', 'unknown')] = item
        total += item['total']
        hit += item['hit']
        missed.extend(
            {'cross': cross.get('name', 'unknown'), 'bin': name}
            for name in item['missed']
        )
    return {'total': total, 'hit': hit, 'missed': missed, 'crosses': result}


def _space_report():
    legal = tuple(legal_public_feature_cases())
    representative = tuple(representative_public_feature_cases())
    legal_tokens = set().union(*(pairwise_tokens(case) for case in legal))
    selected_tokens = set().union(*(pairwise_tokens(case) for case in representative))
    marginal = {}
    for dimension in PUBLIC_DIMENSIONS:
        legal_values = {feature_values(case)[dimension] for case in legal}
        selected_values = {feature_values(case)[dimension] for case in representative}
        marginal[dimension] = {
            'total': len(legal_values),
            'hit': len(legal_values & selected_values),
            'values': sorted(legal_values),
            'missed': sorted(legal_values - selected_values),
        }
    per_operation = Counter(case.operation for case in legal)
    metadata = public_space_metadata()
    return {
        'definition': {
            'source': 'vagqverify/vagq/scenario_matrix.py',
            'vlen_bits': metadata['vlen_bits'],
            'vlen_bytes': metadata['vlen_bits'] // 8,
            'flow_bytes': metadata['flow_bytes'],
            'operations': metadata['operations'],
            'valid_vlmul_encodings': metadata['lmul_encodings'],
            'valid_eew_encodings': metadata['eew_encodings'],
            'nf_range': [0, 7],
            'emul_rule': 'EMUL exponent = lmul_exp(vlmul) + eew - vsew; keep -3..3',
            'uop_rule': metadata['uop_count_rule'],
            'reserved_and_unrepresentable': [
                'reserved vlmul encoding 4',
                'fractional VLMAX configurations without whole elements',
                'data/index EMUL outside the RVV three-bit exponent range',
                'shapes needing more than eight 16-byte public flows',
            ],
        },
        'legal_inventory': {
            'total': len(legal),
            'per_operation_encoding': {
                OPERATION_NAMES[operation]: count
                for operation, count in sorted(per_operation.items())
            },
            'marginal': marginal,
            'pairwise': {
                'total': len(legal_tokens),
                'hit_by_representative': len(selected_tokens & legal_tokens),
                'missed_by_representative': sorted(legal_tokens - selected_tokens),
            },
            'representative': {
                'total': len(representative),
                'unique': len(set(representative)),
                'sha256': metadata['representative_case_sha256'],
            },
        },
        'accounting': metadata,
    }


def _functional_report(functional):
    feature = _group(functional, 'vagq.rvv_isa_audit.public_dut.feature_space')
    shape = _point(feature, 'shape')
    comparison = _point(feature, 'comparison')
    selected_shape_counts = _counts(shape)
    selected_shape_names = [
        name for name, count in selected_shape_counts.items()
        if name != 'supplemental' and count
    ]
    semantic = _group(functional, 'vagq.rvv_isa_audit.public_dut.checked')
    contract = _group(functional, 'vagq.integration.checked')
    runtime_metrics = {
        name: {
            'samples': None if group is None else group.get('samples'),
            'coverage': None if group is None else group.get('coverage'),
            'points': {
                point.get('name'): _point_metric(point)
                for point in (group or {}).get('points', [])
            },
        }
        for name, group in (
            ('handshake', _group(functional, 'vagq.handshake.checked')),
            ('boundary_values', _group(functional, 'vagq.boundary_values.checked')),
            ('lifecycle', _group(functional, 'vagq.lifecycle.checked')),
        )
    }
    lifecycle_group = _group(functional, 'vagq.lifecycle.checked')
    if lifecycle_group is not None:
        lifecycle_transition = _point(lifecycle_group, 'transition')
        runtime_metrics['lifecycle']['transition_target'] = _point_metric(
            lifecycle_transition, exclude=('other',),
        )
        runtime_metrics['lifecycle']['other_transition_samples'] = _counts(
            lifecycle_transition,
        ).get('other', 0)

    return {
        'public_contract': {
            'instance': 'vagq.integration.checked',
            'samples': None if contract is None else contract.get('samples'),
            'coverage': None if contract is None else contract.get('coverage'),
            'covered': None if contract is None else contract.get('covered'),
        },
        'feature_space_execution': {
            'instance': 'vagq.rvv_isa_audit.public_dut.feature_space',
            'samples': None if feature is None else feature.get('samples'),
            'generated_dut_shape_samples': len(selected_shape_names),
            'supplemental_non_dut_samples': selected_shape_counts.get('supplemental', 0),
            'supplemental_scope': 'pure model/qualification sample; no generated DUT execution credit',
            'matrix_packet_defaults': {
                'vl': 1, 'vstart': 0, 'vma': 0, 'vta': 0,
                'uop_idx': 0, 'last_uop': 1,
                'mask': '0xffff if nf>0 else 0x1',
            },
            'uop_count_execution': 'derived_label_only_in_matrix_packet; not a full multi-uop sequence',
            'separate_multi_uop_tests': [
                'tests/vagq/test_isa_dut_matrix.py::test_multi_uop_index_window_is_partitioned_without_gaps_or_duplicates',
            ],
            'multi_uop_execution_scope': 'uop_type=4 and uop_type=6; two-uop indexed-load partitions',
            'marginal_coverage': {
                point.get('name'): _point_metric(point)
                for point in (feature or {}).get('points', [])
                if point.get('name') not in ('shape', 'comparison')
            },
            'shape_bins': {
                'total': len(selected_shape_counts) - int('supplemental' in selected_shape_counts),
                'hit': len(selected_shape_names),
                'missed': sorted(
                    name for name, count in selected_shape_counts.items()
                    if name != 'supplemental' and not count
                ),
                'supplemental_samples': selected_shape_counts.get('supplemental', 0),
            },
            'comparison': _point_metric(comparison),
            'comparison_target': {
                'pass': _counts(comparison).get('pass', 0),
                'counterexample': _counts(comparison).get('counterexample', 0),
                'negative_bin_is_not_a_required_pass': True,
            },
            'pairwise_cross': _cross_metrics(feature),
            'schema_metadata': (
                (feature or {}).get('origins', {})
            ),
        },
        'semantic_audit': {
            'instance': 'vagq.rvv_isa_audit.public_dut.checked',
            'samples': None if semantic is None else semantic.get('samples'),
            'coverage': None if semantic is None else semantic.get('coverage'),
            'audit_outcome': _point_metric(_point(semantic, 'audit_outcome')),
            'segment_mop': _point_metric(_point(semantic, 'segment_mop')),
        },
        'runtime_metrics': runtime_metrics,
    }


def _markdown(report):
    space = report['rvv_space']
    execution = report['functional']['feature_space_execution']
    lines = [
        '# VAGQ verification metrics',
        '',
        'This report keeps shape inventory, functional bins, RTL coverage, and '
        'unobserved system claims separate.',
        '',
        '## RVV/public shape space',
        '',
        f"- Legal public shapes: **{space['legal_inventory']['total']}**.",
        f"- Pairwise covering execution set: **{space['legal_inventory']['representative']['total']}** unique shapes.",
        f"- Pairwise tokens: **{space['legal_inventory']['pairwise']['hit_by_representative']}/{space['legal_inventory']['pairwise']['total']}**.",
        f"- Shape-bin evidence in the functional artifact: **{execution['shape_bins']['hit']}/{execution['shape_bins']['total']}** selected shapes; supplemental samples: **{execution['shape_bins']['supplemental_samples']}**.",
        '',
        'The denominator is not 6×4×7×4×4×8: EMUL legality, whole-element '
        'VLMAX, and the eight-flow limit remove combinations.  The exact rule '
        'is stored in the JSON `rvv_space.definition` and implemented by '
        '`scenario_matrix.py`.',
        '',
        '## Oracle and runtime metrics',
        '',
        f"- Feature-space group samples: **{execution['samples']}**; generated-DUT matrix packets: **{execution['generated_dut_shape_samples']}**, supplemental non-DUT samples: **{execution['supplemental_non_dut_samples']}**.",
        f"- Feature comparison group: pass samples **{execution['comparison_target']['pass']}**, counterexample samples **{execution['comparison_target']['counterexample']}**; the counterexample bin is negative evidence, not a required pass bin.",
        f"- Pairwise cross: **{execution['pairwise_cross']['hit']}/{execution['pairwise_cross']['total']}**.",
        '- The matrix `uop_count` is a derived label; its packets use one uop. Full multi-uop execution is reported separately.',
        '',
        '### Public-boundary runtime groups',
        '',
        f"- Handshake group: **{report['functional']['runtime_metrics']['handshake'].get('coverage')}%** raw group coverage.",
        f"- Boundary-value group: **{report['functional']['runtime_metrics']['boundary_values'].get('coverage')}%** raw group coverage.",
        f"- Lifecycle state: **{report['functional']['runtime_metrics']['lifecycle'].get('transition_target', {}).get('hit', 0)}/{report['functional']['runtime_metrics']['lifecycle'].get('transition_target', {}).get('total', 0)}** transition targets; `other` samples are reported separately in JSON.",
        '',
        '## Explicitly not claimed',
        '',
        '- No formal proof or formal cover-property run was added by this report.',
        '- No mutation campaign or mutation score was run.',
        '- Standalone VAGQ still does not observe final SQ/Sbuffer/DCache/Uncache memory effects.',
        '- Runtime lifecycle/handshake/value metrics are public-boundary metrics, not whole-chip protocol proof.',
    ]
    rtl = report.get('rtl')
    if rtl:
        lines.extend([
            '', '## RTL metrics', '',
            f"- Source lines: {rtl['source_lines']['hit']}/{rtl['source_lines']['total']}.",
            f"- Branch points: {rtl['branch_points']['hit']}/{rtl['branch_points']['total']}.",
            f"- Toggle points: {rtl['toggle_points']['hit']}/{rtl['toggle_points']['total']}.",
        ])
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('functional', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rtl-summary', type=Path)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    functional = json.loads(args.functional.read_text(encoding='utf-8'))
    report = {
        'format': 'vagq-verification-metrics',
        'version': 1,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'rvv_space': _space_report(),
        'functional': _functional_report(functional),
        'claims': {
            'runtime_scoreboard_checker': {
                'status': 'executed-as-test-oracle',
                'scope': 'public VAGQ boundary checker; not formal assertion coverage',
            },
            'formal': {'status': 'not-run'},
            'mutation': {'status': 'not-run'},
            'whole_chip_memory_effect': {'status': 'not-observable-in-standalone-root'},
        },
    }
    if args.rtl_summary is not None:
        rtl = json.loads(args.rtl_summary.read_text(encoding='utf-8'))
        report['rtl'] = rtl.get('rtl_coverage', rtl)
    if args.manifest is not None:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        report['execution'] = {
            'pytest_exitstatus': manifest.get('pytest_exitstatus'),
            'tests': manifest.get('tests'),
            'native_inputs': sum(
                item.get('input_files', item.get('build', {}).get('input_files', 0))
                for item in manifest.get('artifacts', [])
                if item.get('kind') == 'native'
            ),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    args.output.with_suffix('.md').write_text(_markdown(report), encoding='utf-8')
    print(json.dumps({
        'legal_shapes': report['rvv_space']['legal_inventory']['total'],
        'representative_shapes': report['rvv_space']['legal_inventory']['representative']['total'],
        'pairwise': report['rvv_space']['legal_inventory']['pairwise'],
        'feature_samples': report['functional']['feature_space_execution']['samples'],
    }, indent=2))


if __name__ == '__main__':
    main()
