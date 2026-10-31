"""Audit final native shard receipts and summarize actual shape executions."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.run_vagq_exhaustive import audit_attempt, atomic_json, digest
from suites.vector.vagq.waveform import convert_fst, read_public_samples
from suites.vector.vagq.vagq.exhaustive import build_shape_sequence, compare_shape, observed_bytes
from suites.vector.vagq.vagq.scenario_matrix import OPERATION_NAMES, feature_case_id, legal_public_feature_cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    summary = json.loads((run / 'summary.json').read_text())
    frozen = json.loads((run / 'source-hashes.json').read_text())
    assert summary['state'] == 'complete', 'refusing to report an incomplete run as finished'
    for name, value in frozen.items():
        assert digest(ROOT / name) == value, f'source epoch changed: {name}'
        snapshot = run / 'sources' / name
        if snapshot.exists():
            assert digest(snapshot) == value
    cases = tuple(legal_public_feature_cases())
    receipts = json.loads((run / 'completed-shapes.json').read_text())
    assert len(cases) == summary['completed'] == len(receipts) == 8352
    assert [row['ordinal'] for row in receipts] == list(range(8352))
    assert len({row['shape_id'] for row in receipts}) == 8352
    assert Counter(row['status'] for row in receipts) == Counter(summary['counts'])
    artifact_receipts, waveform_receipts = [], []
    functional_attempted, functional_passed = set(), set()
    for manifest_name in summary['manifests']:
        manifest_path = Path(manifest_name)
        attempt = manifest_path.parents[1]
        cmd = json.loads((attempt / 'command.json').read_text())
        start = int(cmd['env']['EXHAUSTIVE_START'])
        stop = start + int(cmd['env']['EXHAUSTIVE_LIMIT'])
        rows = audit_attempt(attempt, range(start, stop), frozen)
        assert rows is not None and rows == receipts[start:stop]
        manifest = json.loads(manifest_path.read_text())
        for artifact in manifest['artifacts']:
            artifact_receipts.append(dict(kind=artifact['kind'], path=artifact['path'],
                sha256=artifact['sha256'], size=artifact['size']))
        functional = json.loads((attempt / 'execution/functional-coverage.json').read_text())
        group = next(group for group in functional['groups']
                     if group['instance'] == 'vagq.public_dut.exhaustive_sequences.v2')
        points = {point['name']: point for point in group['points']}
        functional_attempted.update(name for name, count in points['attempted_shape']['counts'].items() if count)
        functional_passed.update(name for name, count in points['passed_shape']['counts'].items() if count and name != 'not-passed')
        for path in (attempt / 'cases').rglob('VAGQ.fst'):
            decoded = run.parent / 'decoded'
            decoded.mkdir(exist_ok=True)
            vcd = decoded / (attempt.parent.name + '-' + attempt.name + '.vcd')
            convert_fst(path, vcd)
            names = ('clock', 'reset', 'io_addrUop_0_valid', 'io_robWriteback_valid')
            samples = read_public_samples(vcd, names)
            assert {sample['values']['clock'] for sample in samples} == {0, 1}
            assert {sample['values']['reset'] for sample in samples} == {0, 1}
            assert any(s['values']['io_robWriteback_valid'] for s in samples)
            assert any(s['values']['io_addrUop_0_valid'] for s in samples)
            waveform_receipts.append(dict(path=str(path), size=path.stat().st_size, sha256=digest(path),
                decoded_path=str(vcd), native_timepoints=len(samples),
                clock_edges=sum(a['values']['clock'] != b['values']['clock']
                                for a, b in zip(samples, samples[1:])),
                reset_assert_and_release=True, public_admission_and_writeback_observed=True,
                scope='native waveform activity audit, not a cycle-exact ISA proof'))

    assert functional_attempted == {row['shape_id'] for row in receipts}
    assert functional_passed == {row['shape_id'] for row in receipts if row['status'] == 'PASS'}
    by_operation = defaultdict(Counter)
    by_uops = defaultdict(Counter)
    by_nf = defaultdict(Counter)
    by_boundary = defaultdict(Counter)
    error_tags = Counter()
    diagnostics = Counter()
    failures = []
    packet_total = admitted = writebacks = 0
    expected_bytes = raw_bytes = placed_bytes = 0
    result_hash = hashlib.sha256()
    for row in receipts:
        ordinal = row['ordinal']
        case = cases[ordinal]
        assert row['shape_id'] == feature_case_id(case)
        result_path = Path(row['path'])
        result = json.loads(result_path.read_text())
        assert digest(result_path) == row['sha256']
        result_hash.update(bytes.fromhex(row['sha256']))
        stimulus_path = result_path.with_name(f'{ordinal:05d}-stimulus.json')
        plan = build_shape_sequence(case, ordinal)
        assert json.loads(stimulus_path.read_text()) == plan.stimulus()
        assert result['stimulus'] == plan.stimulus()
        by_operation[OPERATION_NAMES[case.operation]][result['status']] += 1
        by_uops[str(len(plan.packets))][result['status']] += 1
        by_nf[str(case.nf)][result['status']] += 1
        by_boundary['nf0_guard_admitted' if case.nf == 0 else 'forced_segment_public_ports'][result['status']] += 1
        error_tags.update(result.get('errors', []))
        packet_total += len(plan.packets)
        admitted += result.get('admitted_uops', 0)
        writebacks += result.get('writebacks', 0)
        expected_bytes += sum(plan.expected_bytes.values())
        if result['status'] == 'ERROR':
            diagnostics['execution_errors'] += 1
        else:
            events = result['events']
            recomputed = compare_shape(plan, events)
            assert all(result[key] == value for key, value in recomputed.items()),\
                f'checker result differs from recorded events: {ordinal}'
            raw, placed, placement = observed_bytes(events['requests'])
            raw_bytes += sum(raw.values())
            placed_bytes += sum(placed.values())
            diagnostics['raw_byte_counter_match'] += raw == plan.expected_bytes
            diagnostics['placement_byte_counter_match'] += placed == plan.expected_bytes
            diagnostics['all_uops_accepted_once'] += Counter(x['entry'] for x in events['admissions']) == Counter(range(len(plan.packets)))
            diagnostics['all_uops_wrote_back_once'] += Counter(x['entry'] for x in events['writebacks']) == Counter(range(len(plan.packets)))
            diagnostics['timed_out'] += bool(events['timed_out'])
            diagnostics['duplicate_placement_shapes'] += any(n > 1 for n in placement.values())
            if result['status'] == 'FAIL':
                diagnostics['failure_raw_matches'] += raw == plan.expected_bytes
                diagnostics['failure_raw_differs'] += raw != plan.expected_bytes
        if result['status'] != 'PASS':
            failures.append({key: value for key, value in row.items() if key not in ('event',)})
    assert admitted == summary['admitted_uops']
    assert writebacks == summary['writebacks']
    assert packet_total == summary['planned_uop_packets'] == 43192
    report = dict(format='vagq-exhaustive-execution-report', version=2,
        generated_at=datetime.now(timezone.utc).isoformat(),
        requested=8352, executed=len(receipts), unexecuted=0,
        outcomes=summary['counts'],
        actual_packet_plan=packet_total, admitted_uops=admitted, writebacks=writebacks,
        native_shards=len(summary['manifests']),
        native_waveforms=len(waveform_receipts),
        functional_attempted_shapes=len(functional_attempted),
        functional_passed_shapes=len(functional_passed),
        by_operation=dict(by_operation), by_actual_sequence_uops=dict(by_uops),
        by_nf=dict(by_nf), by_boundary=dict(by_boundary),
        overlapping_failure_tags=dict(error_tags),
        byte_occurrences=dict(expected=expected_bytes, raw=raw_bytes, placed=placed_bytes),
        diagnostics=dict(diagnostics),
        failure_classification='Unreviewed public checker mismatches, NOT automatically confirmed RTL defects.',
        scope='8352 public input tuples with VLMAX and full producer-uop sequences; nf>0 is forced-port; response placement is synthetic; no final whole-chip memory-effect claim',
        elapsed_seconds=summary['elapsed_seconds'])
    atomic_json(run.parent / 'report.json', report)
    atomic_json(run.parent / 'failed-shapes.json', failures)
    evidence = dict(native_artifacts=artifact_receipts, native_waveforms=waveform_receipts,
        source_epoch_verified=True, result_receipts_verified=8352,
        byte_checker_recomputed_from_events=True,
        result_receipt_aggregate_sha256=result_hash.hexdigest(),
        all_shape_identities_unique=True,
        functional_artifact_matches_journal=True,
        unchanged_independent_isa_oracle=frozen['vagq/isa_reference.py'])
    atomic_json(run.parent / 'evidence.json', evidence)
    lines = [
        '# VAGQ 全量 shape 重执行结果', '',
        f'**实际完成 {report["executed"]}/8352 个 shape，未执行 0。**', '',
        f'- shape 结果：{report["outcomes"]}。',
        f'- 实际输入计划：{packet_total} 个 uop；真实接受 {admitted} 个，writeback {writebacks} 次。',
        f'- {report["native_shards"]} 片 native 回归，{len(waveform_receipts)} 个完成的原生 FST。',
        '- 每个 shape 的完整输入、请求、response、empty marker、STD 和 writeback 记录均已落盘。',
        '- 已核验全部 shape/result hash、8352 个唯一 ID、native manifest、FST、functional attempt/pass bins 与 journal 一致。',
        '', '## 按操作分类', '', '| 操作 | PASS | FAIL | ERROR |', '| --- | ---: | ---: | ---: |',
    ]
    for operation, counts in by_operation.items():
        lines.append(f'| {operation} | {counts["PASS"]} | {counts["FAIL"]} | {counts["ERROR"]} |')
    lines.extend([
        '', '## 失败范围与原因', '',
        f'- `nf=0`：{dict(by_nf["0"])}。这只表示本次 public shape 检查，不是完整译码/整机验收。',
        f'- `nf>0` 强行 public-port 注入：{dict(by_boundary["forced_segment_public_ports"])}。',
        f'- 字节多重集不一致：{error_tags["full architectural byte multiset mismatch"]} 个 shape。',
        f'- 有界无进展/未完成 writeback：{error_tags["bounded public protocol timeout"]} 个 shape。',
        f'- 重复 response placement：{error_tags["duplicate public response placement"]} 个 shape。',
        '- 上述原因可重叠，不相加。全部失败仍需对 producer/consumer 假设和 RTL 分别复核。',
        '', '## 执行与边界', '',
        '- 使用原来的 8352 tuple 清单，不删失败项。`vl=VLMAX`，真实 uop 序列、index register bank 和 `last_uop` 都随 shape 变化。',
        '- 原 inventory 的 data-flow 数不是实际 producer uop 数；实际序列基于已验证的 public producer adapter。',
        '- 完整 element/address 字节 Counter 检查保留 multiplicity；不能用集合去重掩盖重复。',
        '- 原始请求字节和 `(dataMask << byteOffset)` 的 16-byte response-placement 单独统计。后者是 consumer 源契约模型，不是 LSU RTL 或最终 memory effect 仿真。',
        '- FAIL 是可重现的 public checker 对比失败，尚未经过反误报复核，不能直接称为 RTL bug；ERROR 不给 DUT 通过信用。',
        '- nf>0 依然是直接注入，不冒充当前 DecodeStage 的生产路径；本轮不是整机 ISA 验收。',
        '', '## 文件', '',
        '- `report.json`：完整执行数、uop 数、结果和分类。',
        '- `failed-shapes.json`：每个失败 shape 的身份、原因和 result 路径。',
        '- `evidence.json`：native/FST/source/result 审计。',
        '- `full/summary.json`、`full/completed-shapes.json`：可恢复执行账本。',
        '- `full/shard-*/attempt-*/shapes/*-stimulus.json` 与 `*-result.json`：逐个真实执行证据。',
        '- `before-retry/`、`qualification-v1..v3/`：旧 runner 和资格运行，包括修复前的 harness 错误，不覆盖历史。',
        '', '## 恢复命令', '', '```sh',
        f'python3 tools/run_vagq_exhaustive.py --output {run.relative_to(ROOT)} --shard-size 256',
        '```',
        '', '该命令只复用通过完整审计的已完成分片；不会把有 FAIL 的分片重标为 PASS。',
    ])
    (run.parent / 'README.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
