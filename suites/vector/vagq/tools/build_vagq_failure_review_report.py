import ucv.runtime as ucv_paths
"""Independently audit all failure reviews, interventions and native metadata.

Reports the additional merge-mask reference discrepancy instead of hiding the
failed all-output qualification. Never rewrites the original FAIL results.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import argparse
import csv
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.run_vagq_exhaustive import atomic_json, digest
from tools.run_vagq_failure_review import audit
from suites.vector.vagq.maskgen.reference import MaskRequest, evaluate_protocol
from suites.vector.vagq.vagq.exhaustive import (
    U64_MASK, build_shape_sequence, compare_shape, observed_bytes,
)
from suites.vector.vagq.vagq.failure_review import analyze_failure
from suites.vector.vagq.vagq.scenario_matrix import (
    FeatureCase, OPERATION_NAMES, legal_public_feature_cases,
)
from suites.vector.vagq.waveform import convert_fst, read_public_samples


FAMILY_NAMES = {
    'narrow_spill': '原始请求字节正确；单 flow placement 截断',
    'zero_mask': 'wide segment 的零 mask／ACK 停滞（主要原因）',
    'special7': '7-field/e8/index-e32 的 4-byte 布局与 7-byte 请求不一致',
    'wide_offset': '无超时的非零起点元素编号错误',
}
LAYOUT_FIELDS = (
    'elemValidMask', 'elemActiveMask', 'elemAgnosticMask', 'elemBase',
    'startFieldOffset', 'startByteOffset', 'skipMerge',
)


def response_key(row):
    return tuple(row[name] for name in ('cycle', 'kind', 'entry', 'issue_mask'))


def verify_driven_responses(run):
    """Check ACTUALLY driven ACKs, not the pre-override helper's event log."""
    generated = Counter(response_key(row) for row in run['events']['responses'])
    actual = Counter(response_key(row) for row in run['actual_driven_lsu_responses'])
    overrides = run['diagnostic_overrides']
    for row in overrides:
        before = (row['cycle'], row['kind'], row['entry'], row['original'])
        after = (row['cycle'], row['kind'], row['entry'], row['driven'])
        assert generated[before] > 0
        generated[before] -= 1
        generated[after] += 1
    assert +generated == actual
    if run['policy'] == 'baseline':
        assert not overrides
    elif run['policy'] == 'ack_zero_only':
        assert overrides and all(row['original'] == 0 for row in overrides)
    else:
        assert run['policy'] == 'onehot_all' and overrides
    assert run['acceptance_credit'] is False


def source_segment_merge_mask(request, uop_count):
    """Scala's destElemWindow=lmulOffset, NOT the destLsrcOffset field.

    Source-contract diagnostic only; this is not a replacement ISA oracle.
    The preserved reference currently confuses these two different quantities.
    """
    physical_windows = math.ceil(request.lmul)
    per_window = uop_count // physical_windows
    assert per_window >= 1
    window = request.uop_idx // per_window
    fields = 16 >> request.deew
    start, end = window * fields, (window + 1) * fields

    def range_mask(point):
        if point >= end:
            return 0xFFFF
        if point <= start:
            return 0
        return (1 << ((point - start) << request.deew)) - 1

    return (~((~range_mask(request.vstart) & range_mask(request.vl))
              & request.v0_mask)) & 0xFFFF


def intended_sites(plan, requests):
    rows = []
    for request in requests:
        mop = next(m for m in plan.layout[request['entry']]
                   if m.valid_bit and m.byte == request['byte_offset'])
        if mop.index != request['element']:
            rows.append(dict(entry=request['entry'], site=mop.byte,
                expected_element=mop.index, actual_element=request['element'],
                expected_field=mop.field))
    return rows


def substitute_wide_fragments(plan, requests):
    """Offline cause isolation, NOT execution, ACK repair, or DUT correctness.

    Restore each allocated fragment's element/address and flow-bounded mask.
    The independent architecture Counter remains unchanged.
    """
    corrected = deepcopy(requests)
    changed = Counter()
    for request in corrected:
        mop = next(m for m in plan.layout[request['entry']]
                   if m.valid_bit and m.byte == request['byte_offset'])
        width = min(((plan.case.nf + 1) - mop.field) << plan.case.data_eew,
                    16 - mop.byte)
        mask = (1 << width) - 1
        displacement = plan.index_values[mop.index] if plan.case.indexed else mop.index * plan.stride
        address = (plan.base + displacement + (mop.field << plan.case.data_eew)) & U64_MASK
        for name, value in (('element', mop.index), ('address', address), ('data_mask', mask)):
            changed[name] += request[name] != value
            request[name] = value
    raw, placed, _ = observed_bytes(corrected)
    return dict(raw_matches_architecture=raw == plan.expected_bytes,
        placed_matches_architecture=placed == plan.expected_bytes,
        changed_fields=dict(changed), offline_only=True, acceptance_credit=False)


def check_manifest(path):
    manifest = json.loads(path.read_text())
    assert manifest['state'] == 'committed' and manifest['coverage_complete']
    for artifact in manifest['artifacts']:
        target = Path(artifact['path'])
        assert target.stat().st_size == artifact['size'] and digest(target) == artifact['sha256']
        if artifact['kind'] == 'native':
            for name, value in artifact['build']['files'].items():
                assert digest(Path(name)) == value, f'native build provenance changed: {name}'
    return dict(path=str(path), sha256=digest(path), pytest_exitstatus=manifest['pytest_exitstatus'],
        tests=manifest['tests'], artifacts=manifest['artifacts'])


def waveform_receipt(fst, decoded, *, maskgen=False):
    decoded.parent.mkdir(parents=True, exist_ok=True)
    convert_fst(fst, decoded)
    names = ('in_uopIdx', 'out_elemValidMask', 'out_mergeWriteMask') if maskgen else (
        'clock', 'reset', 'io_addrUop_0_valid', 'io_robWriteback_valid',
    )
    samples = read_public_samples(decoded, names, module='MaskGenDut_top' if maskgen else 'VAGQDut_top')
    if maskgen:
        assert len({sample['values']['in_uopIdx'] for sample in samples}) > 1
        assert len({sample['values']['out_elemValidMask'] for sample in samples}) > 1
    else:
        assert {sample['values']['clock'] for sample in samples} == {0, 1}
        assert {sample['values']['reset'] for sample in samples} == {0, 1}
        assert any(sample['values']['io_addrUop_0_valid'] for sample in samples)
        assert any(sample['values']['io_robWriteback_valid'] for sample in samples)
    return dict(path=str(fst), sha256=digest(fst), size=fst.stat().st_size,
        decoded_path=str(decoded), decoded_sha256=digest(decoded), native_timepoints=len(samples),
        scope='Actual native waveform activity audit, not a cycle-exact ISA proof')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('review', type=Path)
    args = parser.parse_args()
    review = args.review.resolve()
    original = review.parent / 'vagq-exhaustive-20261020-v1'
    run = review / 'native'
    summary = json.loads((run / 'summary.json').read_text())
    assert summary['state'] == 'complete' and summary['requested'] == summary['reviewed'] == 2278
    frozen = json.loads((run / 'source-hashes.json').read_text())
    for name, value in frozen.items():
        assert digest(ROOT / name) == value, f'frozen epoch changed: {name}'
        snapshot = run / 'sources' / name
        if snapshot.exists():
            assert digest(snapshot) == value
    baseline = json.loads((original / 'baseline.json').read_text())
    for name, value in baseline['unchanged_rtl_and_native'].items():
        assert digest(ROOT / name) == value
    originals = json.loads((original / 'failed-shapes.json').read_text())
    offline = json.loads((review / 'case-review.json').read_text())
    receipts = json.loads((run / 'completed-reviews.json').read_text())
    expected_ordinals = [row['ordinal'] for row in originals]
    assert len(set(expected_ordinals)) == len(expected_ordinals) == 2278
    assert [row['ordinal'] for row in offline] == [row['ordinal'] for row in receipts] == expected_ordinals
    cases = tuple(legal_public_feature_cases())
    native, waves, sampled = [], [], Counter()
    for name in summary['manifests']:
        path = Path(name)
        attempt = path.parents[1]
        command = json.loads((attempt / 'command.json').read_text())
        wanted = command['ordinals']
        rows = audit(attempt, wanted)
        assert rows == receipts[command['start']:command['stop']]
        assert json.loads((attempt / 'exit.json').read_text())['returncode'] == 0
        native.append(check_manifest(path))
        journal = [json.loads(line) for line in (attempt / 'review/progress.jsonl').read_text().splitlines()]
        assert [row['ordinal'] for row in journal if row['event'] == 'started'] == wanted
        assert [row for row in journal if row['event'] == 'finished'] == rows
        functional = json.loads((attempt / 'execution/functional-coverage.json').read_text())
        group = next(group for group in functional['groups'] if group['instance'] == 'vagq.review.reproduced')
        assert group['collection_complete']
        point = next(point for point in group['points'] if point['name'] == 'reproduced_shape')
        sampled.update({key: value for key, value in point['counts'].items() if value})
        fsts = list((attempt / 'cases').rglob('VAGQ.fst'))
        assert len(fsts) == 1
        waves.append(waveform_receipt(fsts[0], review / 'decoded' / (attempt.parent.name + '.vcd')))
    assert sampled == Counter(row['shape_id'] for row in originals)

    # All original failure-uop metadata was sampled from the actual native MaskGen.
    producer = review / 'producer-check'
    producer_manifest = check_manifest(producer / 'execution/manifest.json')
    assert producer_manifest['pytest_exitstatus'] == 1, 'retain the failed ALL-output qualification'
    producer_build = next(artifact['build'] for artifact in producer_manifest['artifacts']
                          if artifact['kind'] == 'native')
    assert producer_build['files'][str(ROOT / 'dut/MaskGen/MaskGenDut.v')] == frozen['rtl/MaskGen.sv']
    producer_dir = producer / 'review'
    producer_summary = json.loads((producer_dir / 'summary.json').read_text())
    journal_path = producer_dir / 'metadata.jsonl'
    assert digest(journal_path) == producer_summary['journal_sha256']
    for name, value in json.loads((producer_dir / 'source-hashes.json').read_text()).items():
        assert digest(ROOT / name) == value
    producer_rows = [json.loads(line) for line in journal_path.read_text().splitlines()]
    assert [row['ordinal'] for row in producer_rows] == expected_ordinals
    metadata = {}
    field_errors = Counter()
    metadata_uops = merge_errors = 0
    for row in producer_rows:
        ordinal = row['ordinal']
        plan = build_shape_sequence(cases[ordinal], ordinal)
        assert row['shape_id'] == plan.stimulus()['shape_id'] and len(row['samples']) == len(plan.packets)
        differing = 0
        for sample, (addr, _data) in zip(row['samples'], plan.packets):
            request = MaskRequest(addr.v0_byte_mask, addr.deew, addr.ieew, addr.emul,
                addr.vl, addr.vstart, addr.vma, addr.vta, addr.uop_idx, addr.nf)
            assert sample['request'] == asdict(request) and sample['expected'] == evaluate_protocol(request)
            errors = [key for key in sample['expected'] if sample['expected'][key] != sample['actual'][key]]
            assert set(errors) <= {'mergeWriteMask'}
            field_errors.update(errors)
            differing += bool(errors)
            expected = dict(sample['expected'], mergeWriteMask=source_segment_merge_mask(request, len(plan.packets)))
            assert expected == sample['actual'], f'source equations did not explain metadata: {ordinal}'
            metadata_uops += 1
        assert not row['all_match'] and differing > 0
        merge_errors += differing
        metadata[ordinal] = dict(uops=len(row['samples']), seven_layout_fields_exact=True,
            merge_model_differing_uops=differing, source_dest_window_explains_all=True)
    assert metadata_uops == producer_summary['uops'] == 13536
    assert merge_errors == 10596
    mask_fsts = list((producer / 'cases').rglob('MaskGen.fst'))
    assert len(mask_fsts) == 1
    producer_wave = waveform_receipt(mask_fsts[0], review / 'decoded/producer-MaskGen.vcd', maskgen=True)
    producer_analysis = dict(shapes=2278, actual_uop_samples=metadata_uops,
        layout_fields=list(LAYOUT_FIELDS), all_layout_fields_match_native=True,
        all_output_qualification_status='FAIL, preserved; do not claim all-output qualification passed',
        mismatching_fields=dict(field_errors), affected_shapes=2278,
        source_dest_window_explains_all_native_samples=True,
        cause='reference.py uses destLsrcOffset as destination_window; Scala packs destElemWindow=lmulOffset',
        original_failure_causes_depend_on_merge_mask=False,
        frozen_reference_unchanged=True, manifest=producer_manifest, waveform=producer_wave)
    atomic_json(review / 'producer-model-review.json', producer_analysis)

    final_rows, totals = [], Counter()
    by_family = defaultdict(Counter)
    by_operation = defaultdict(Counter)
    diag_counts, secondary = Counter(), Counter()
    extended_lengths = []
    for original_row, explanation, receipt in zip(originals, offline, receipts):
        ordinal = original_row['ordinal']
        case = cases[ordinal]
        plan = build_shape_sequence(case, ordinal)
        assert case.nf > 0
        # JSON journals normalize witness tuples to lists.
        recomputed_explanation = json.loads(json.dumps(analyze_failure(original_row, case)))
        assert recomputed_explanation == explanation
        assert explanation['all_checks_satisfied']
        original_path = Path(original_row['path'])
        record = json.loads(original_path.read_text())
        assert digest(original_path) == original_row['sha256']
        stimulus_path = original_path.with_name(f'{ordinal:05d}-stimulus.json')
        assert json.loads(stimulus_path.read_text()) == plan.stimulus() == record['stimulus']
        result = json.loads(Path(receipt['path']).read_text())
        assert digest(Path(receipt['path'])) == receipt['sha256']
        base = result['baseline']
        for key in record:
            if key not in ('elapsed_seconds',):
                assert base[key] == record[key], f'baseline differs at {ordinal}: {key}'
        assert base['status'] == 'FAIL' and result['review_status'] == 'VERIFIED'
        assert result['checks'] == receipt['checks'] and all(result['checks'].values())
        assert base['stimulus'] == plan.stimulus() and not result['baseline_differing_fields']
        recomputed = compare_shape(plan, base['events'])
        assert all(base[key] == value for key, value in recomputed.items())
        verify_driven_responses(base)
        family = explanation['family']
        wide_fragment_check = None
        if family == 'wide_offset':
            wide_fragment_check = substitute_wide_fragments(plan, base['events']['requests'])
            assert wide_fragment_check['raw_matches_architecture'] and wide_fragment_check['placed_matches_architecture']
        wrong_sites = intended_sites(plan, base['events']['requests'])
        secondary['baseline_nonzero_start_wrong_element_shapes'] += bool(wrong_sites)
        secondary['baseline_nonzero_start_wrong_element_requests'] += len(wrong_sites)
        if wrong_sites:
            assert family in ('zero_mask', 'wide_offset')
            assert all(row['actual_element'] == row['expected_element'] + 1 and row['site'] > 0 for row in wrong_sites)
        diagnostics = {}
        for policy, diagnostic in result['diagnostics'].items():
            control_plan = build_shape_sequence(FeatureCase(**diagnostic['stimulus']['case']), ordinal)
            assert diagnostic['stimulus'] == control_plan.stimulus()
            verify_driven_responses(diagnostic)
            recomputed = compare_shape(control_plan, diagnostic['events'])
            assert all(diagnostic[key] == value for key, value in recomputed.items())
            raw, placed, _ = observed_bytes(diagnostic['events']['requests'])
            item = dict(actual_uops=diagnostic['actual_sequence_uops'],
                admitted=diagnostic['admitted_uops'], writebacks=diagnostic['writebacks'],
                cycles=diagnostic['cycles'], timed_out=diagnostic['events']['timed_out'],
                retained_checker_status=diagnostic['status'],
                raw_counter_matches=raw == control_plan.expected_bytes,
                placed_counter_matches=placed == control_plan.expected_bytes,
                ack_overrides=len(diagnostic['diagnostic_overrides']), acceptance_credit=False)
            if policy == 'extended_wait':
                assert family == 'zero_mask' and diagnostic['cycles'] > base['cycles']
                assert diagnostic['events']['timed_out']
                for event in ('requests', 'admissions', 'writebacks', 'empty_requests', 'std_outputs', 'responses', 'vrf_reads'):
                    assert diagnostic['events'][event] == base['events'][event]
                extended_lengths.append((base['cycles'], diagnostic['cycles']))
            elif policy == 'counterfactual_ack_zero':
                assert family == 'zero_mask' and not diagnostic['events']['timed_out']
                assert Counter(row['entry'] for row in diagnostic['events']['writebacks']) == Counter(range(len(plan.packets)))
                intervention = substitute_wide_fragments(plan, diagnostic['events']['requests'])
                assert intervention['raw_matches_architecture'] and intervention['placed_matches_architecture']
                item['offline_fragment_substitution'] = intervention
                assert diagnostic['status'] == 'FAIL', 'ACK diagnostic alone is NOT a functional fix'
            elif policy == 'counterfactual_request_start_ack':
                assert family == 'special7' and raw == plan.expected_bytes
                assert not diagnostic['events']['timed_out'] and diagnostic['status'] == 'FAIL'
            else:
                assert policy == 'index_e32_control' and family == 'wide_offset'
                assert diagnostic['status'] == 'PASS'
            diagnostics[policy] = item
            diag_counts[policy] += 1
        raw, placed, _ = observed_bytes(base['events']['requests'])
        counts = dict(shapes=1, actual_uops=len(plan.packets),
            admitted_uops=base['admitted_uops'], writebacks=base['writebacks'],
            raw_counter_match=int(raw == plan.expected_bytes), placed_counter_match=int(placed == plan.expected_bytes))
        totals.update(counts)
        by_family[family].update(counts)
        by_operation[OPERATION_NAMES[case.operation]][family] += 1
        final_rows.append(dict(ordinal=ordinal, shape_id=receipt['shape_id'], family=family,
            cause=FAMILY_NAMES[family], original_status='FAIL', original_result=str(original_path),
            original_sha256=original_row['sha256'], original_stimulus_sha256=digest(stimulus_path),
            replay_result=receipt['path'], replay_sha256=receipt['sha256'],
            baseline_failure_exactly_reproduced=True,
            explanation=explanation, producer_metadata=metadata[ordinal],
            secondary_wrong_element_sites=wrong_sites, diagnostics=diagnostics,
            offline_wide_fragment_substitution=wide_fragment_check,
            production_decode_reachable=False,
            indexed_data_width_matches_sew=case.data_eew == case.vsew if case.indexed else None,
            functional_acceptance_credit=False))
    assert totals['shapes'] == 2278 and totals['actual_uops'] == metadata_uops
    assert secondary['baseline_nonzero_start_wrong_element_shapes'] == 28
    assert secondary['baseline_nonzero_start_wrong_element_requests'] == 28
    assert totals['admitted_uops'] == 13536 and totals['writebacks'] == 11780
    atomic_json(review / 'reviewed-failures.json', final_rows)
    with (review / 'reviewed-failures.csv').open('w') as stream:
        keys = ('ordinal', 'shape_id', 'family', 'cause', 'original_status',
                'baseline_failure_exactly_reproduced', 'production_decode_reachable',
                'indexed_data_width_matches_sew', 'functional_acceptance_credit',
                'original_result', 'original_sha256', 'replay_result', 'replay_sha256')
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows({key: row[key] for key in keys} for row in final_rows)

    # Preserve the source equations used in the causal review, with exact hashes.
    internal = ucv_paths.source_path_for(ROOT)
    source_names = (
        'src/main/scala/xiangshan/backend/vector/vagq/SplitCtrl.scala',
        'src/main/scala/xiangshan/backend/vector/vagq/MaskGen.scala',
        'src/main/scala/xiangshan/backend/vector/vagq/VagqInfoGen.scala',
        'src/main/scala/xiangshan/backend/vector/vagq/MergeCtrl.scala',
        'src/main/scala/xiangshan/backend/vector/Decoder/DecodeStage.scala',
        'src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala',
        'src/main/scala/xiangshan/mem/pipeline/NewStoreUnit.scala',
    )
    source_receipts = []
    for name in source_names:
        path = internal / name
        target = review / 'source-evidence/XiangShan-internal' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert digest(target) == digest(path)
        else:
            shutil.copy2(path, target)
        source_receipts.append(dict(path=str(path), snapshot=str(target), sha256=digest(path)))
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=internal, text=True).strip()
    status = subprocess.check_output(['git', 'status', '--short'], cwd=internal, text=True)
    assert head == 'd4566d58a5ace1f6a5df4409b37a84b971f48e43' and status == ''
    qualification_path = review / 'review-checker-qualification/pytest.xml'
    qualification = ET.parse(qualification_path).getroot()
    suites = list(qualification.iter('testsuite'))
    assert sum(int(suite.attrib['tests']) for suite in suites) == 12
    assert not any(int(suite.attrib[key]) for suite in suites for key in ('failures', 'errors', 'skipped'))
    checker_sources = ('tests/vagq/test_failure_review_qualification.py',
                       'tests/vagq/test_failure_review_report_checks.py')
    checker_qualification = dict(tests=12, failures=0, errors=0,
        junit=str(qualification_path), junit_sha256=digest(qualification_path),
        sources={name: digest(ROOT / name) for name in checker_sources},
        scope='Offline audit/negative-test qualification only; no DUT acceptance coverage')
    for path in (Path(__file__), *(ROOT / name for name in checker_sources)):
        target = review / 'source-evidence' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    report = dict(format='vagq-all-failure-causal-review', version=1,
        generated_at=datetime.now(timezone.utc).isoformat(), requested=2278,
        reviewed=2278, exactly_reproduced=2278, unreviewed=0,
        original_statuses_unchanged=True, totals=dict(totals),
        by_primary_family={key: dict(value) for key, value in by_family.items()},
        by_operation={key: dict(value) for key, value in by_operation.items()},
        overlapping_secondary_findings=dict(secondary),
        diagnostic_runs=dict(diag_counts), diagnostic_acceptance_credit=0,
        extended_wait=dict(shapes=600, baseline_cycle_min=min(a for a, b in extended_lengths),
            baseline_cycle_max=max(a for a, b in extended_lengths),
            extended_cycle_min=min(b for a, b in extended_lengths),
            extended_cycle_max=max(b for a, b in extended_lengths),
            idle_setting=512, note='Existing per-shape hard cap stops at 296..416 cycles; NOT 512 fully elapsed idle cycles.'),
        all_native_producer_layout_fields_match=True,
        producer_merge_reference_discrepancy=dict(affected_shapes=2278,
            affected_uop_samples=10596, sampled_uops=13536,
            original_all_output_qualification='FAIL, preserved', source_explains_all=True),
        indexed_data_eew_not_equal_sew=sum(row['indexed_data_width_matches_sew'] is False for row in final_rows),
        production_decode_admitted_failure_shapes=0,
        confirmed_production_path_rtl_bugs=0,
        production_bug_count_note='Zero CONFIRMED here, not proof of absence; every failed shape has nf>0 and current useVAGQ decoder guard requires nf=0.',
        full_segment_data_and_whole_chip_memory_effect='UNVERIFIED',
        native_replay_shards=len(native), native_replay_waveforms=len(waves),
        producer_native_waveforms=1, native_elapsed_seconds=summary['elapsed_seconds'],
        original_exhaustive_outcomes=dict(PASS=6074, FAIL=2278, ERROR=0),
        reviewed_failure_table_sha256=digest(review / 'reviewed-failures.json'))
    atomic_json(review / 'report.json', report)
    evidence = dict(original_failed_shapes_sha256=digest(original / 'failed-shapes.json'),
        original_report_sha256=digest(original / 'report.json'),
        frozen_source_epoch_verified=True, original_rtl_and_native_unchanged=True,
        independent_isa_oracle_sha256=frozen['vagq/isa_reference.py'],
        receipt_and_journal_verified=2278, original_checker_recomputed=2278,
        offline_explanations_recomputed=2278, actually_driven_acks_verified=True,
        checker_qualification=checker_qualification,
        functional_reproduced_bins=dict(unique=2278, each_hit_exactly_once=True,
            scope='Failure reproduction ONLY; no new functional acceptance'),
        native_manifests=native, native_waveforms=waves,
        producer_model_review_sha256=digest(review / 'producer-model-review.json'),
        scala_source_receipts=source_receipts, internal_git_head=head, internal_git_status=status,
        report_generator_sha256=digest(Path(__file__)))
    atomic_json(review / 'evidence.json', evidence)
    write_readme(review, report, final_rows)
    print(json.dumps(report, indent=2, ensure_ascii=False))


def write_readme(review, report, rows):
    lines = [
        '# 全部 2278 个失败 shape 的反误报复核', '',
        '**2278/2278 已逐项检查并在原生 DUT 上完整重放，原始失败全部精确复现；未复核 0。**', '',
        '这不是 2278 个 RTL bug，也不是将失败改判通过。原始全量结果仍为 **6074 PASS / 2278 FAIL / 0 ERROR**。',
        '本次复核通过表示“原失败与原因证据相符”，不表示原 shape 功能通过。', '',
        '## 不重叠的主要失败分类', '',
        '| 主要分类 | shape | raw 字节 Counter 正确 | 原始 uop / writeback | 结论 |',
        '| --- | ---: | ---: | ---: | --- |',
    ]
    conclusions = {
        'narrow_spill': '不能据此报访存地址 bug；placement/数据路径仍未验证',
        'zero_mask': '零 mask 和响应不能置 ACK 的停滞可复现，不是等待过短',
        'special7': 'forced-port 的布局与请求/ACK 宽度契约不一致',
        'wide_offset': 'forced-port 非零首 site 被当作后一个元素',
    }
    for key, name in FAMILY_NAMES.items():
        values = report['by_primary_family'][key]
        lines.append(f'| {name} | {values["shapes"]} | {values["raw_counter_match"]} | '
                     f'{values["actual_uops"]} / {values["writebacks"]} | {conclusions[key]} |')
    lines.extend([
        '', '四组之和为 2278。它们是**主要失败分类**，不是互斥的所有根因标签：',
        '- 非零首 site 的元素编号错误在原始日志中共影响 **28** 项：无超时组 16 项，另有 12 项与零 mask 超时重叠。',
        '- 600 个零 mask 案例还存在字节缺失；只恢复 ACK 不恢复数据/地址正确性。',
        '- 原始 600 timeout、48 duplicate placement、2266 byte mismatch 标签存在重叠，不能相加。',
        '', '## 1. 1598 项：地址请求正确，单 flow placement 不能替代架构访存', '',
        '逐项用独立 ISA oracle 的完整 `(element, address)` 字节多重集比较，1598 项 raw 请求全部一致、',
        '所有 uop 均完成，且无重复 placement。原 checker 将请求的 `dataMask` 左移 `byteOffset` 后截成 16 位，',
        '跨过当前 flow 的字节被丢弃；每项缺失 Counter **恰好**等于被截去的字节 Counter。',
        '因此“地址生成失败”的解释被排除；但不能据 raw 一致就宣称 segment 读写数据正确或整机 PASS。',
        '这类强制 segment 请求的 staging/consumer 数据契约仍有边界，原始 FAIL 保留。',
        '', '## 2. 600 项：wide segment 的零 dataMask 导致 ACK 无法完成', '',
        '`SplitCtrl.selectElem` 对 continuation 使用 `0xffff >> (16-lastMopWidth)`；',
        '`lastMopWidth > 16` 时，generated SV 的无符号减法回绕，移位量过大，得到零 mask。',
        '请求仍 valid，起始 pending bit 已设 sent；consumer 契约返回 `dataMask << byteOffset`，故 ACK 为零。',
        '`MergeCtrl` 要求 `reqAck.andR`，因此该 entry 无法 writeback；ordered load 还会阻挡后续 entry。',
        '',
        '- 全部 600 项逐一重构 pending bit 和缺失 writeback，结果一致。',
        '- 原始运行 73～89 cycle；延长诊断运行到 **296～416 cycle** 的既有 hard cap，公共事务仍完全相同且继续停滞。',
        '  `max_idle=512` 是设置值，**并非已经等待了 512 个 idle cycle**。',
        '- 只给零 mask 请求的起点注入 one-hot ACK：600/600 恢复全部 writeback；这是反事实诊断，不是真实 LSU 响应或修复。',
        '- ACK 诊断本身 **600 项仍全为 FAIL**。在它们的日志副本中，按 allocated fragment 的元素/地址与 flow 边界替换 mask，',
        '  600/600 的字节 Counter 才与保持不变的架构答案一致；这只是离线因果解释，不是执行通过。',
        '', '## 3. 64 项：7-field/e8/index-e32 特殊布局的契约不一致', '',
        '`VagqInfoGen` 与 `MaskGen` 的特殊布局按 4-byte 间距安排 site；',
        '`SplitCtrl` 发出的请求却为 7-byte `dataMask=0x7f`。',
        '48 个非 ordered-load 案例 raw 请求字节正确，但 response placement 重叠；',
        '16 个 ordered-load 案例的整段 ACK 提前确认邻接 site，导致应发出的请求被跳过。',
        '对全部 64 项使用 request-start-only ACK 的明确标记诊断后，raw 架构请求恢复一致，',
        '但原 placement checker 仍全部 FAIL，不能把诊断 ACK 当作 consumer 修复或验收。',
        '', '## 4. 16 项：wide segment 在非零 startByteOffset 处误认首元素', '',
        '`SplitCtrl` 的 wide 分支用 `site.orR` 作 idxOffset。index-register bank 在 flow 中途切分时，',
        '首个 site 可以是非零；它本应对应 offset 0，却被算作 1，因此 element 和 index 地址都向后错一项。',
        '16 项中仅离线替换该元素/地址，完整 placement 字节差异就消失；raw 请求另有超出当前 flow 的 fragment 重复，',
        '再按 flow 边界截取 mask 后，16 项 raw Counter 也全部解释一致。这些替换不是真实 DUT 修复。',
        '把 index e64 改成不会在该位置切 bank 的 e32，',
        '16 个实际 native 对照均通过自己的 checker，但**它们是不同输入，不是原输入的通过结果**。',
        '另有 12 个同机制案例归在 zero-mask 主要组；逐项明细中保留次要标签。',
        '', '## 附加发现：MaskGen 参考模型的 mergeWriteMask 错误（不是新增 DUT bug）', '',
        '对全部失败的 **13536 个 uop** 另行执行真实 native MaskGen。布局相关七个字段全部一致：',
        '`elemValidMask / elemActiveMask / elemAgnosticMask / elemBase / startFieldOffset / startByteOffset / skipMerge`。',
        '这是本轮实际输入下的逐样本核对，不是对所有 mask/agnostic 参数组合的证明；',
        '本次定位使用的布局、active mask 和起点并非 adapter 擅自猜测。',
        '',
        '但全输出资格检查真实 **FAIL**：2278 项中共 **10596 个 uop** 的 `mergeWriteMask` 模型与 DUT 不同。',
        '`maskgen/reference.py::mop_info()` 把 field-major 的 `destLsrcOffset` 当作 `destination_window`；',
        'Scala 实际单独保存 `destElemWindow=lmulOffset`。按源契约的元素窗口单独计算后，',
        '**13536/13536** 原生样本所有字段都解释一致。该字段不参与原 exhaustive 的输入布局/架构字节答案，',
        '也不参与本次停滞 pending-bit 计算，故不是四组原始失败的原因；',
        '它进一步说明 segment 最终 merge/VRF 数据没有被本轮证明。参考模型、失败资格运行及原始 oracle 均未为迎合 DUT 而改写。',
        '', '## 生产路径与验收边界', '',
        '- 所有 2278 项都是 `nf>0` forced-public-port；当前 `DecodeStage.scala:195-197` 要求 `nf==0` 才设 `useVAGQ`。',
        '- 这里确认的是 unsupported/forced-port 条件下的 DUT 行为与契约问题；**没有新增可确认的当前生产路径 RTL 缺陷**。',
        '  这不表示整个设计不存在缺陷，也不意味着这些接口问题可以删掉或忽略。',
        f'- 其中 {report["indexed_data_eew_not_equal_sew"]} 项 indexed 输入另有 `data_eew != vsew` 的结构扩展；',
        '  这些 tuple 不能直接作为真实 indexed RVV 指令的解码证据；其余 tuple 也不由此自动获得 ISA 合法性证明。',
        '- standalone synthetic ACK 不是 NewLoadUnit/NewStoreUnit RTL 联仿；无真实 SQ/Sbuffer/DCache/Uncache memory effect。',
        '- 本次不新增功能 PASS、waiver 或 RTL 满覆盖声明，也不改原始分母；line/branch/toggle 合并及可达性审查不属本次失败复核结果。',
        '', '## 证据与复现', '',
        '- `reviewed-failures.json`：全部 2278 项，原输入/结果 hash、原因 witness、次要原因、native 重放和诊断结果。',
        '- `reviewed-failures.csv`：同一全集的便于筛选版。',
        '- `case-review.json`：逐项源等式、原始 byte/response/ACK 证据。',
        '- `native/completed-reviews.json`、9 片 `manifest.json` 与 `review/*-review.json`：完整真实重放、延长等待、实际驱动 ACK 与副本诊断。',
        '- `producer-check/`：全输出资格失败的原始运行、逐 uop native MaskGen 样本和原生覆盖/FST；不隐藏失败。',
        '- `producer-model-review.json`：merge-mask 参考模型问题的单独复核及全部样本核对。',
        '- `review-checker-qualification/pytest.xml`：12 个离线反例/审计资格测试通过；不计 DUT 通过信用。',
        '- `evidence.json`、`decoded/`、`source-evidence/`：manifest/hash/FST 解码与源证据。9 个重放 FST 和 1 个 MaskGen FST 均已实际解码。',
        '- 独立 ISA oracle、generated RTL 和 VAGQ native 库均与原全量 baseline 一致；`XiangShan-internal` HEAD 为 d4566d5，status clean。',
        '', '```sh',
        'python3 tools/build_vagq_failure_review_report.py results/vagq-exhaustive-review-20261020-v1',
        '```',
        '', '上述命令只重审既有证据，不重跑仿真；native 恢复命令见 `native/shard-*/attempt-*/command.json`。',
        '', '## 后续处置建议', '',
        '1. 先修正 merge-mask 参考模型的字段含义并重新资格检查，不能因旧普通回归通过而继续信任未覆盖的多 uop 分支。',
        '2. 在设计方明确 segment support 的 producer/consumer 端到端契约之前，将三种 forced-port 机制作为实现限制保留。',
        '3. 如果准备开放 `nf>0` 生产路径，再修正/验证请求分片、起点编号、ACK ownership 和最终 merge/VRF/SQ 数据。',
        '4. 不把 raw 请求正确、诊断恢复 writeback 或不同输入的控制组通过合并成原 shape 的功能通过。',
    ])
    (review / 'README.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
