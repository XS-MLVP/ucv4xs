import ucv.runtime as ucv_paths
"""Audit NF=0 focused runs without rewriting historical failures or coverage."""
from collections import Counter
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_vagq_failure_review_report import check_manifest
from tools.build_vagq_reference_fix_report import audit_wave, junit
from tools.run_vagq_exhaustive import atomic_json, digest
from vagqverify.vagq.exhaustive import assess_shape_boundaries, build_shape_sequence
from vagqverify.vagq.nf0_focus import PROFILES, assess_events, compatible_shapes, make_variant, ready_values, shape_scope
from vagqverify.vagq.scenario_matrix import legal_public_feature_cases


def audit_history(out):
    directory = ROOT / 'results/vagq-exhaustive-20261020-v1'
    cases = tuple(legal_public_feature_cases())
    rows = json.loads((directory / 'full/completed-shapes.json').read_text())
    selected = []
    counts = Counter()
    for receipt in rows:
        ordinal = receipt['ordinal']
        case = cases[ordinal]
        if case.nf:
            continue
        path = Path(receipt['path'])
        assert digest(path) == receipt['sha256']
        original = json.loads(path.read_text())
        plan = build_shape_sequence(case, ordinal)
        assert plan.stimulus() == original['stimulus']
        assessment = assess_shape_boundaries(plan, original['events'])
        scope = shape_scope(case)
        counts['original_' + receipt['status']] += 1
        counts[scope] += 1
        counts['request_boundary_' + assessment['request_boundary_status']] += 1
        selected.append(dict(ordinal=ordinal, scope=scope, original_status=receipt['status'],
            receipt=receipt, assessment=assessment, new_native_execution=False))
    assert len(selected) == 1450 and counts['original_PASS'] == 1450
    assert counts['instruction_shape_compatible'] == 468
    assert counts['vtype_unsupported'] == 126 and counts['indexed_data_eew_not_sew'] == 856
    atomic_json(out / 'historical-nf0-receipts.json', selected)
    return dict(counts=counts, records=len(selected), new_native_executions=0,
        all_8352_records_preserved=True, whole_producer_rename_reachability_proven=False)


def audit_run(out, name, *, smoke=False):
    run = out / name
    manifest = check_manifest(run / 'execution/manifest.json')
    counts, profiles, operations, sequence_lengths = Counter(), Counter(), Counter(), Counter()
    records = {}
    shapes = dict(compatible_shapes())
    for journal in sorted((run / 'cases').rglob('variants.jsonl')):
        for line in journal.open():
            receipt = json.loads(line)
            key = receipt['ordinal'], receipt['profile']
            assert key not in records
            case = shapes[key[0]]
            variant = make_variant(case, *key)
            path = Path(receipt['path'])
            record = json.loads(path.read_text())
            assert record['stimulus'] == variant.stimulus()
            assessment, errors = assess_events(variant, record['events'])
            assert assessment == record['assessment']
            assert errors == record['errors']
            assert record['status'] == receipt['status'] == ('FAIL' if errors else 'PASS')
            assert record['final_memory_effect_verified'] is False
            assert record['ordered_store_memory_order_verified'] is False
            for row in record['events']['flow_control']:
                expected = ready_values(key[1], row['cycle'])
                assert [row['ldu_ready'], row['sta_ready'], row['empty_ready']] == [list(values) for values in expected]
            if key[1] == 'stalled_sparse':
                assert record['events']['blocked_cycles'] > 0
            counts[receipt['status']] += 1
            counts['planned_uops'] += record['actual_sequence_uops']
            counts['admitted_uops'] += len(record['events']['admissions'])
            counts['writebacks'] += len(record['events']['writebacks'])
            counts['fired_requests'] += len(record['events']['requests'])
            counts['blocked_lane_cycles'] += record['events']['blocked_cycles']
            counts['lane_reassignments_diagnostic'] += len(record['events']['lane_reassignments'])
            profiles[key[1]] += 1
            operations[case.operation] += 1
            sequence_lengths[record['actual_sequence_uops']] += 1
            records[key] = dict(path=str(path), sha256=digest(path), status=record['status'],
                ordinal=key[0], profile=key[1], errors=errors, actual_sequence_uops=record['actual_sequence_uops'])
    if smoke:
        expected_shapes = []
        for operation in (0, 1, 4, 5, 6, 7):
            candidates = [item for item in shapes.items() if item[1].operation == operation]
            expected_shapes.extend((candidates[0][0], candidates[-1][0]))
    else:
        expected_shapes = list(shapes)
    assert set(records) == {(ordinal, profile) for ordinal in expected_shapes for profile in PROFILES}
    atomic_json(out / f'{name}-records.json', list(records.values()))
    return dict(manifest=manifest, junit=junit(run / 'pytest.xml'), counts=counts,
        variants=len(records), shapes=len(expected_shapes), profiles=profiles,
        operations=operations, actual_sequence_length_distribution=sequence_lengths), records


def audit_initial_smoke(out, replay):
    run = out / 'smoke'
    manifest = check_manifest(run / 'execution/manifest.json')
    assert manifest['pytest_exitstatus'] == 1
    frozen = json.loads((run / 'source-hashes.json').read_text())
    for name, expected in frozen.items():
        assert digest(run / 'sources' / name) == expected
    counts = Counter()
    for journal in (run / 'cases').rglob('variants.jsonl'):
        for line in journal.open():
            receipt = json.loads(line)
            key = receipt['ordinal'], receipt['profile']
            old = json.loads(Path(receipt['path']).read_text())
            new = json.loads(Path(replay[key]['path']).read_text())
            assert old['stimulus'] == new['stimulus']
            for field in ('admissions', 'data_admissions', 'requests', 'empty_requests',
                          'vrf_reads', 'std_outputs', 'writebacks', 'responses', 'flow_control'):
                assert old['events'][field] == new['events'][field], (key, field)
            assert old['assessment'] == new['assessment']
            assert old['assessment']['request_boundary_status'] == 'PASS'
            assert all(error.startswith(('lduReq[', 'staReq[')) for error in old['errors'])
            counts[old['status']] += 1
            counts['identical_physical_event_replays'] += 1
    assert counts['identical_physical_event_replays'] == 60
    assert counts['FAIL'] == 7 and counts['PASS'] == 53
    return dict(counts=counts, manifest=manifest, junit=junit(run / 'pytest.xml'),
        cause='New checker incorrectly imposed Irrevocable per-lane stability on Decoupled VAGQArbiter outputs',
        proof='Same 60 stimuli and actual physical events replay exactly; all raw byte/lifecycle checks already PASS',
        original_failures_preserved=True,
        spec_provenance_sha256=digest(out / 'protocol-spec/provenance.json'))


def audit_protection(out):
    baseline = json.loads((out / 'baseline.json').read_text())
    for field in ('protected', 'before_sources', 'historical_evidence'):
        for name, expected in baseline[field].items():
            assert digest(ROOT / name) == expected, f'{field} changed: {name}'
    for name, expected in baseline['before_sources'].items():
        assert digest(out / 'before' / name) == expected
    for name, expected in baseline['historical_native'].items():
        assert digest(Path(name)) == expected
    tested = json.loads((out / 'after/source-hashes.json').read_text())
    for name, expected in tested.items():
        assert digest(ROOT / name) == digest(out / 'after/sources' / name) == expected
    internal = ucv_paths.source_path_for(ROOT)
    for name, expected in json.loads((out / 'source-contracts/hashes.json').read_text()).items():
        assert digest(internal / name) == digest(out / 'source-contracts' / name) == expected
    protocol = json.loads((out / 'protocol-spec/provenance.json').read_text())
    assert protocol['chisel_version'] == '7.13.0'
    assert 'org.chipsalliance::chisel:7.13.0' in (internal / 'build.mill').read_text()
    for item in protocol['files']:
        assert digest(Path(item['path'])) == item['sha256']
    assert 'No requirements are placed on the signaling' in (out / 'protocol-spec/Decoupled.scala').read_text()
    assert "promises to not change" in (out / 'protocol-spec/Irrevocable.scala').read_text()
    assert subprocess.check_output(['git', 'status', '--short'], cwd=internal, text=True) == baseline['internal_status'] == ''
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=internal, text=True).strip() == baseline['internal_head']
    return dict(protected_rtl_native_oracle_files=len(baseline['protected']),
        untouched_preexisting_python_sources=len(baseline['before_sources']),
        historical_evidence_files=len(baseline['historical_evidence']),
        historical_native_artifacts=len(baseline['historical_native']), tested_sources=len(tested),
        source_epoch_sha256=digest(out / 'after/source-hashes.json'), internal_git_status='',
        internal_git_head=baseline['internal_head'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    protection = audit_protection(out)
    history = audit_history(out)
    smoke, replay = audit_run(out, 'smoke-r2', smoke=True)
    incident = audit_initial_smoke(out, replay)
    full, records = audit_run(out, 'full')
    assert full['variants'] == 2340 and full['shapes'] == 468
    waves = []
    for name in ('smoke', 'smoke-r2', 'full'):
        for fst in sorted((out / name / 'cases').rglob('VAGQ.fst')):
            vcd = out / 'decoded' / name / fst.relative_to(out / name / 'cases').with_suffix('.vcd')
            waves.append(audit_wave(fst, vcd))
    pure = {name: junit(out / name / 'pytest.xml') for name in ('pure', 'pure-r2')}
    assert pure['pure-r2']['passed'] == 74 and pure['pure-r2']['failures'] == pure['pure-r2']['errors'] == 0
    failures = [record for record in records.values() if record['status'] == 'FAIL']
    atomic_json(out / 'failures.json', failures)
    report = dict(format='vagq-nf0-focused-ut', version=1,
        generated_at=datetime.now(timezone.utc).isoformat(), history=history, pure=pure,
        initial_smoke_contract_error=incident, smoke=smoke, full=full, protection=protection,
        waves=waves, residual_failed_variants=len(failures),
        current_request_lifecycle_result='FAIL' if failures else 'PASS_FOR_TESTED_VARIANTS',
        whole_isa_acceptance='NOT_VERIFIED', actual_producer_rename='NOT_VERIFIED',
        final_data_and_memory_effect='NOT_VERIFIED', ordered_store_memory_effect='NOT_VERIFIED',
        rtl_coverage_totals_newly_merged=False, segment_active_entry_testing_expanded=False)
    atomic_json(out / 'report.json', report)
    atomic_json(out / 'evidence.json', dict(report_sha256=digest(out / 'report.json'),
        baseline_sha256=digest(out / 'baseline.json'), source_epoch_sha256=protection['source_epoch_sha256'],
        history_receipts_sha256=digest(out / 'historical-nf0-receipts.json'),
        full_records_sha256=digest(out / 'full-records.json'),
        failures_sha256=digest(out / 'failures.json'), generator_sha256=digest(Path(__file__))))
    destination = out / 'report-sources' / Path(__file__).name
    destination.parent.mkdir(exist_ok=True)
    shutil.copy2(Path(__file__), destination)
    counts = full['counts']
    lines = [
        '# VAGQ NF=0 UT 聚焦结果', '',
        f'**468 个 instruction-shape-compatible NF=0 shape × 5 个新 profile，共 2340 次完整序列尝试：{counts.get("PASS", 0)} PASS / {counts.get("FAIL", 0)} FAIL。**',
        '**这是 public 请求/生命周期检查，不是最终数据、实际 producer/rename 或整机 ISA 验收。**', '',
        '## 范围收敛', '',
        '- 当前 DecodeStage 仅对 nf=0 的 strided/indexed 设置 useVAGQ；segment 通过 useGather/PermUnit 的 zip/unzip 数据路径处理。',
        '- segment 的 native 请求仍可经过 VAGQArbiter 旁路；不能把整个顶层所有端口都限制成 nf=0。该旁路保留既有覆盖，本轮不扩展 segment 语义。',
        '- NF>0 强制 addrUop 注入的历史反例继续保留，不列为当前 active-entry 功能必须修复项；不因此删 FAIL、改历史分母或豁免 RTL 覆盖点。', '',
        '## 历史复用，而非重跑', '',
        '- 原 1450 个 NF=0 public shape 全部原始 PASS，receipt hash 和输入核验通过；本次复核新增 native execution=0。',
        '- 其中 468 个同时满足 ELEN=64 的实际 VSet vtype 约束和 indexed data EEW=SEW；126 个不受当前 VSet 支持，856 个 indexed data EEW!=SEW。',
        '- 该分类由指令/配置规则决定，不以失败为依据；全部 1450 条及原 8352 条结果保留。468 不等于已证明实际 decoder/rename 可达性的全集。', '',
        '## 新增真实执行', '',
        '- 每个 shape 实际驱动全部 producer uop、对应 index bank payload 和逐 data-register 的 byte-expanded v0 行；不重复固定 packet 冒充多 uop。',
        '- 五个 profile：全不选 mask、交替 mask、各 bank 不同 mask、部分 vl/vstart、稀疏 mask 加 LSU/empty 持续背压。全部保持 0<=vstart<vl，不把未证明的 VL=0 producer gate 当作输入事实。',
        f'- 实际序列长度分布（variant 次数）：{dict(full["actual_sequence_length_distribution"])}。',
        f'- 计划 uop {counts["planned_uops"]}；实际 admission {counts["admitted_uops"]}；writeback {counts["writebacks"]}；fired memory requests {counts["fired_requests"]}。',
        f'- 实际 blocked lane-cycle {counts["blocked_lane_cycles"]}；Decoupled lane 重新分配诊断 {counts["lane_reassignments_diagnostic"]} 次。',
        '- 独立 ISA oracle 计算 raw (element,address) 字节多重集；逐 uop owner/完成检查，真实 ready&&valid 后才 ACK，并复核每个实际驱动 ACK 对应前一拍 fire。',
        '- ordered load 检查公开请求元素顺序；不将 ordered store 的请求顺序或 synthetic ACK 说成真实 SQ/DCache/Uncache memory order。',
        f'- 完整矩阵 JUnit：{full["junit"]["passed"]} PASS / {full["junit"]["failures"]} FAIL / {full["junit"]["errors"]} ERROR；每个 pytest 节点含 130 个 variant。', '',
        '## 保留的初次 smoke 失败及 checker 修正', '',
        '- 初次 smoke 为 5 个 pytest FAIL / 1 PASS：60 个 variant 中 7 个因过强的逐 lane 保持断言失败，53 个通过。原 JSON/JUnit/FST/源码未覆盖。',
        '- 这 60 个 variant 的独立 raw byte 和 lifecycle 检查原本全部通过。原生波形表明未接受请求可从 lane1 重新分配到 lane0 后 fire，没有丢失或重复。',
        '- 当前实际依赖 Chisel 7.13.0：DecoupledIO 不提供 IrrevocableIO 的逐 lane 稳定承诺。官方两种类型源码、URL/hash 已保存在 protocol-spec/。',
        '- 修正仅限 VAGQArbiter 输出的过强断言：lane 变化继续作为诊断保存；请求丢失/重复、错误地址/元素、提前/无 fire ACK、缺数据半和重复 writeback 仍被拒绝。empty 注册 stage 的保持检查保留。',
        '- smoke-r2 的 60 个输入及所有实际请求、ACK、admission/writeback、ready/valid 事件与初次完全相同，6 个 pytest 节点通过；不是修改输入或 ISA 答案来迎合 DUT。',
        '- 纯资格初次 65 PASS，修正并增加 8 个注错后 74 PASS；不是 native 执行或 RTL 覆盖 credit。', '',
        '## 证据与未完成项', '',
        '- report.json / evidence.json / full-records.json / failures.json 保存可复核统计与每项输入输出定位。',
        '- full/cases/ 含 2340 份完整刺激和事件；smoke/ 保留原 FAIL，smoke-r2/ 保留相同输入重放。',
        f'- {len(waves)} 个实际 FST 解码并核对 clock/reset 活动，不由 JSON 事件重建波形；该检查不是逐 cycle ISA 证明。',
        f'- hash 核验 {protection["protected_rtl_native_oracle_files"]} 个 RTL/native/oracle、{protection["untouched_preexisting_python_sources"]} 个既有 Python 源码、{protection["historical_evidence_files"]} 个历史证据及 {protection["historical_native_artifacts"]} 个历史 native/FST 等文件未变；XiangShan-internal clean。',
        '- 本轮只添加 NF=0 工具/测试及报告，未改既有模型、设计 RTL、库或原独立 oracle，未提交或推送。',
        '- 仍未验证真实 producer/rename、最终 load/store 数据与真实存储效果；native line/branch/toggle 已落盘但未重新合并总表，没有满覆盖声明。', '',
        '实际命令见 RUNS.md；不可在已有 output/cases 目录原地重跑。仅重审证据：', '', '```sh',
        'python3 tools/build_nf0_focus_report.py results/vagq-nf0-focus-20261020-v1', '```',
    ]
    (out / 'README.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(dict(history=history, full_counts=counts,
        full_variants=full['variants'], full_junit=full['junit'],
        decoded_fsts=len(waves), protection=protection,
        report=str(out / 'README.md')), indent=2))


if __name__ == '__main__':
    main()
