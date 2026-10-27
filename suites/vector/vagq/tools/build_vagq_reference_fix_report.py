import ucv.runtime as ucv_paths
"""Audit the reference repair without turning residual RTL failures into PASS."""
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_vagq_failure_review_report import check_manifest
from tools.run_vagq_exhaustive import atomic_json, digest
from vagqverify.maskgen.reference import MaskRequest, allocated_uops, evaluate_protocol
from vagqverify.vagq.exhaustive import U64_MASK, assess_shape_boundaries, build_shape_sequence
from vagqverify.vagq.isa_reference import architectural_accesses
from vagqverify.vagq.scenario_matrix import FeatureCase, legal_public_feature_cases
from vagqverify.waveform import convert_fst, read_public_samples


def junit(path):
    suites = list(ET.parse(path).getroot().iter('testsuite'))
    counts = {name: sum(int(suite.attrib.get(name, 0)) for suite in suites)
              for name in ('tests', 'failures', 'errors', 'skipped')}
    counts['passed'] = counts['tests'] - counts['failures'] - counts['errors'] - counts['skipped']
    return dict(path=str(path), sha256=digest(path), **counts)


def audit_wave(fst, vcd):
    vcd.parent.mkdir(parents=True, exist_ok=True)
    convert_fst(fst, vcd)
    module = fst.stem + 'Dut_top'
    scopes, names = [], []
    with vcd.open() as stream:
        for line in stream:
            fields = line.split()
            if not fields:
                continue
            if fields[0] == '$scope':
                scopes.append(fields[2])
            elif fields[0] == '$upscope':
                scopes.pop()
            elif fields[0] == '$var' and scopes and scopes[-1] == module:
                names.append(fields[4])
            elif fields[0] == '$enddefinitions':
                break
    assert names, f'no public native signals in {fst}'
    selected = ['clock', 'reset'] if {'clock', 'reset'} <= set(names) else names[:2]
    quality = 'ADVANCING_NATIVE_CAPTURE'
    try:
        samples = read_public_samples(vcd, selected, module=module)
        timepoints = len(samples)
    except AssertionError as error:
        # A one-vector CLOCKLESS test can legitimately capture one timestamp.
        # Keep that weaker evidence distinct from dynamic activity; never use
        # this exception for a clocked DUT or an unreadable/empty capture.
        if 'clock' in selected or str(error) != 'FST contains no advancing native waveform timestamps':
            raise
        with vcd.open() as stream:
            timestamps = {int(line[1:].strip()) for line in stream if line.startswith('#')}
        assert len(timestamps) == 1, f'no readable clockless snapshot: {fst}'
        quality, timepoints = 'READABLE_STATIC_SNAPSHOT', 1
    if 'clock' in selected:
        assert {sample['values']['clock'] for sample in samples} == {0, 1}
        assert {sample['values']['reset'] for sample in samples} == {0, 1}
    return dict(path=str(fst), sha256=digest(fst), size=fst.stat().st_size,
        decoded_path=str(vcd), decoded_sha256=digest(vcd), native_timepoints=timepoints,
        selected_leaves=selected, quality=quality,
        scope='Native FST decode/timestamp activity, not cycle-exact ISA proof')


def analyze_policy(path):
    counts = Counter()
    failures = []
    for line in path.open():
        row = json.loads(line)
        request = MaskRequest(**row['request'])
        assert row['expected'] == evaluate_protocol(request)
        mops = allocated_uops(request)[request.uop_idx]
        independent = source_first_cover = 0
        witnesses = []
        for mop in mops:
            if not mop.valid_bit or not request.vstart <= mop.index < request.vl:
                continue
            if (request.v0_mask >> mop.mask_index) & 1:
                independent |= mop.valid_bit
            first = next(item for item in mops if item.full_mask & (1 << mop.byte))
            if (request.v0_mask >> first.mask_index) & 1:
                source_first_cover |= mop.valid_bit
            if first.mask_index != mop.mask_index:
                witnesses.append(dict(site=mop.byte, element=mop.index,
                    expected_mask_index=mop.mask_index, source_first_mask_index=first.mask_index))
        counts['samples'] += 1
        assert independent == row['expected']['elemActiveMask']
        assert source_first_cover == row['actual']['elemActiveMask']
        assert row['semantic_merge'] == row['expected']['mergeWriteMask'] == row['actual']['mergeWriteMask']
        assert row['semantic_agnostic'] == row['expected']['elemAgnosticMask'] == row['actual']['elemAgnosticMask']
        different = [name for name in row['expected'] if row['expected'][name] != row['actual'][name]]
        assert set(different) <= {'elemActiveMask'}
        if different:
            failures.append(dict(request=row['request'], expected_active=independent,
                native_active=row['actual']['elemActiveMask'], source_first_cover=source_first_cover,
                wrong_owner_witnesses=witnesses))
        counts['full_output_matches'] += not different
        counts['merge_and_agnostic_semantics_match'] += 1
        counts['independent_active_matches_reference'] += 1
        counts['first_cover_source_matches_native'] += 1
    assert counts['samples'] == 9024 and len(failures) == 56
    return dict(counts), failures


def sparse_variants(run):
    rows = []
    for path in sorted((run / 'cases').rglob('sparse-*-result.json')):
        result = json.loads(path.read_text())
        case = FeatureCase(**result['stimulus']['case'])
        ordinal = result['ordinal']
        original = build_shape_sequence(case, ordinal)
        byte_mask = result['byte_mask']
        derived_arch_mask = 0
        for element in range(case.vlmax):
            field_width = 1 << case.data_eew
            bits = (byte_mask >> (element * field_width)) & ((1 << field_width) - 1)
            assert bits in (0, (1 << field_width) - 1), 'not a replicated element mask'
            derived_arch_mask |= bool(bits) << element
        assert derived_arch_mask == result['architectural_mask']
        accesses = architectural_accesses(kind='strided', base=original.base,
            vsew=case.vsew, vlmul=case.vlmul, vl=case.vlmax, vstart=0,
            mask=derived_arch_mask, data_eew=case.data_eew, nf=case.nf, stride=original.stride)
        expected = Counter((access.element, (access.address + byte) & U64_MASK)
                           for access in accesses for byte in range(1 << case.data_eew))
        plan = replace(original, packets=tuple((replace(addr, v0_byte_mask=byte_mask), data)
            for addr, data in original.packets), expected_bytes=expected)
        assert result['stimulus'] == plan.stimulus()
        assessment = assess_shape_boundaries(plan, result['events'])
        assert assessment == result['assessment'] and assessment['request_boundary_status'] == 'FAIL'
        inactive = sorted({request['element'] for request in result['events']['requests']
                           if request['data_mask'] and not ((derived_arch_mask >> request['element']) & 1)})
        assert inactive, 'must prove actual masked-off element requests, not just a raw projection mismatch'
        rows.append(dict(path=str(path), sha256=digest(path), variant_id=result['variant_id'],
            byte_mask=byte_mask, architectural_mask=derived_arch_mask,
            requested_masked_off_elements=inactive, assessment=assessment,
            production_decode_reachable=False))
    assert len(rows) == 2
    return rows


def historical_artifacts(out):
    files = {}
    original = json.loads((ROOT / 'results/vagq-exhaustive-20261020-v1/evidence.json').read_text())
    for artifact in original['native_artifacts']:
        files[artifact['path']] = artifact['sha256']
    for wave in original['native_waveforms']:
        files[wave['path']] = wave['sha256']
    review = json.loads((ROOT / 'results/vagq-exhaustive-review-20261020-v1/evidence.json').read_text())
    for manifest in review['native_manifests']:
        for artifact in manifest['artifacts']:
            files[artifact['path']] = artifact['sha256']
    for wave in review['native_waveforms']:
        files[wave['path']] = wave['sha256']
        files[wave['decoded_path']] = wave['decoded_sha256']
    producer = json.loads((ROOT / 'results/vagq-exhaustive-review-20261020-v1/producer-model-review.json').read_text())
    for artifact in producer['manifest']['artifacts']:
        files[artifact['path']] = artifact['sha256']
    for path, expected in files.items():
        assert digest(Path(path)) == expected, f'historical native evidence changed: {path}'
    atomic_json(out / 'protected-native-artifacts.json', files)
    return len(files)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    baseline = json.loads((out / 'baseline.json').read_text())
    for name, expected in baseline['unchanged_required'].items():
        assert digest(ROOT / name) == expected, f'protected RTL/native/oracle changed: {name}'
    for name, expected in baseline['historical_evidence'].items():
        assert digest(ROOT / name) == expected, f'historical evidence changed: {name}'
    for name, expected in baseline['before_sources'].items():
        assert digest(out / 'before' / name) == expected
    after = json.loads((out / 'after/source-hashes.json').read_text())
    for name, expected in after.items():
        assert digest(ROOT / name) == digest(out / 'after/sources' / name) == expected
    assert digest(ROOT / 'vagqverify/maskgen/reference.py') != baseline['before_sources']['vagqverify/maskgen/reference.py']

    runs = {name: check_manifest(out / name / 'execution/manifest.json')
            for name in ('producer-recheck', 'directed', 'regression', 'extended-canaries')}
    assert runs['producer-recheck']['pytest_exitstatus'] == runs['regression']['pytest_exitstatus'] == 0
    assert runs['extended-canaries']['pytest_exitstatus'] == 1
    assert runs['extended-canaries']['tests'] == {'FAIL': 2}
    assert runs['directed']['tests'] == {'FAIL': 1, 'PASS': 1}
    qualifications = {name: junit(out / name / 'pytest.xml') for name in runs}
    qualifications['pure'] = junit(out / 'pure-qualification/pytest.xml')
    assert qualifications['pure']['passed'] == 101 and qualifications['pure']['failures'] == 0
    assert qualifications['regression']['failures'] == qualifications['regression']['errors'] == 0
    producer = json.loads((out / 'producer-recheck/review/summary.json').read_text())
    assert producer['shapes'] == producer['matching_shapes'] == 2278 and producer['uops'] == 13536
    assert not producer['mismatches']
    producer_journal = out / 'producer-recheck/review/metadata.jsonl'
    assert digest(producer_journal) == producer['journal_sha256']
    producer_rows = [json.loads(line) for line in producer_journal.open()]
    assert len(producer_rows) == 2278
    for row in producer_rows:
        assert row['all_match']
        for sample in row['samples']:
            assert sample['expected'] == sample['actual'] == evaluate_protocol(MaskRequest(**sample['request']))

    policy_path = next((out / 'extended-canaries/cases').rglob('element-window-samples.jsonl'))
    policy, policy_failures = analyze_policy(policy_path)
    atomic_json(out / 'sparse-mask-failures.json', policy_failures)
    sparse = sparse_variants(out / 'extended-canaries')
    atomic_json(out / 'sparse-top-variants.json', sparse)
    repaired_policy = next((out / 'regression/cases').rglob('element-window-samples.jsonl'))
    repaired_counts, repaired_failures = analyze_policy(repaired_policy)
    assert repaired_counts == policy and repaired_failures == policy_failures
    boundary_summary = next((out / 'directed/cases').rglob('assessment-summary.json'))
    boundary_rows = json.loads(boundary_summary.read_text())
    assert len(boundary_rows) == 8
    for row in boundary_rows:
        path = boundary_summary.with_name(f'{row["ordinal"]:05d}-assessment.json')
        record = json.loads(path.read_text())
        plan = build_shape_sequence(tuple(legal_public_feature_cases())[row['ordinal']], row['ordinal'])
        assert assess_shape_boundaries(plan, record['events']) == record['assessment']
        assert record['full_acceptance_credit'] is False

    reassessment = json.loads((out / 'reassessment/summary.json').read_text())
    assert reassessment['reassessed_records'] == 8352 and reassessment['new_native_shape_executions'] == 0
    assert digest(out / 'reassessment/reassessed-shapes.json') == reassessment['reassessed_table_sha256']
    assert reassessment['counts']['legacy_v2'] == {'PASS': 6074, 'FAIL': 2278}
    protected_native = historical_artifacts(out)
    waves, other_waves, target_wave_gaps = [], [], []
    for name in runs:
        fsts = sorted((out / name / 'cases').rglob('*.fst'))
        assert fsts
        for fst in fsts:
            if name == 'regression' and fst.stem != 'MaskGen':
                # The model repair does not require gigabytes of unrelated
                # random-stress VCD exports. Keep explicit readability gaps;
                # do not infer a waveform PASS from a nonempty file.
                item = dict(path=str(fst), sha256=digest(fst), size=fst.stat().st_size,
                    scope='Non-target ordinary-regression waveform')
                if fst.stat().st_size <= 1_000_000:
                    process = subprocess.run(['fst2vcd', str(fst)], stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE, text=True)
                    item.update(status='READABLE_ONLY' if process.returncode == 0 else 'UNREADABLE',
                        reader_returncode=process.returncode, reader_stderr=process.stderr,
                        note='Readability only, no timestamp/ISA activity acceptance')
                else:
                    item.update(status='NOT_DECODED_LARGE_NON_TARGET',
                        note='No waveform readability/activity claim')
                other_waves.append(item)
                continue
            vcd = out / 'decoded' / name / fst.relative_to(out / name / 'cases').with_suffix('.vcd')
            try:
                waves.append(audit_wave(fst, vcd))
            except AssertionError as error:
                # Do not relax any primary proof capture. An unrelated
                # structural-sweep capture from ordinary regression is kept
                # as an explicit evidence gap, not counted as decoded.
                if name != 'regression' or fst.parent == repaired_policy.parent:
                    raise
                target_wave_gaps.append(dict(path=str(fst), sha256=digest(fst),
                    size=fst.stat().st_size, status='UNREADABLE_OR_NO_ACTIVITY',
                    error=str(error), scope='Other ordinary-regression MaskGen capture; no waveform credit'))
    atomic_json(out / 'non-target-waveform-audit.json', other_waves)
    atomic_json(out / 'target-waveform-gaps.json', target_wave_gaps)
    semantic = json.loads((out / 'semantic-qualification/summary.json').read_text())
    assert semantic['running_merge_policy_qualified']
    assert semantic['frozen_old_reference_rejected']
    assert semantic['legal_different_agnostic_policy_accepted']
    assert semantic['whole_reference_correctness'] == 'NOT_CERTIFIED'
    for name, expected in json.loads((out / 'semantic-qualification/source-hashes.json').read_text()).items():
        assert digest(ROOT / name) == digest(out / 'semantic-qualification/sources' / name) == expected
    semantic_junit = junit(out / 'semantic-qualification/pytest.xml')
    assert semantic_junit['passed'] == 9 and semantic_junit['failures'] == semantic_junit['errors'] == 0
    internal = ucv_paths.source_path_for(ROOT)
    assert subprocess.check_output(['git', 'status', '--short'], cwd=internal, text=True) == baseline['internal_status'] == ''
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=internal, text=True).strip() == baseline['internal_head']

    defects = [
        dict(id='REF-01', status='fixed', kind='reference-model',
            title='Destination register offset confused with element window',
            native_requalified_shapes=2278, native_requalified_uops=13536,
            independent_merge_policy_samples=9024, rtl_modified=False),
        dict(id='RTL-01', status='open-latent-module', kind='RTL implementation',
            title='Wide continuation zero dataMask from shift underflow',
            original_primary_shapes=600, current_production_decode_reachable=False,
            reproduction='original full shape 419; prior replay and ACK-only diagnosis retained'),
        dict(id='RTL-02', status='open-latent-module', kind='RTL implementation',
            title='Nonzero first site misidentified by site.orR',
            original_shapes=28, overlaps_zero_mask=12, current_production_decode_reachable=False,
            reproduction='original shape 2171; native boundary requalification retained'),
        dict(id='INT-01', status='open-interface-inconsistency', kind='producer/consumer contract',
            title='4-byte special layout versus 7-byte request/ACK coverage',
            original_shapes=64, current_production_decode_reachable=False,
            reproduction='original shapes 1326 and 5014'),
        dict(id='RTL-03', status='open-latent-module', kind='RTL mask ownership',
            title='First-cover mopFullMask maps a later element to a previous v0 bit',
            native_policy_mismatches=56, native_policy_samples=9024,
            independent_mop_answer_matches_reference=9024,
            first_cover_source_equation_matches_native=9024,
            native_top_sparse_variants=sparse, current_production_decode_reachable=False,
            source='VagqInfoGen.scala:50-54,176-181; no RTL fix or waiver'),
        dict(id='SCOPE-01', status='not-certified-as-whole-isa-oracle', kind='reference scope',
            title='Component merge controls require independent no-op suppression and uop identity proof',
            independently_qualified_running_checks=semantic['counts']['running_instruction_checks'],
            no_op_without_gate_violations=semantic['counts']['noop_without_producer_gate_violations'],
            note='These are semantic qualification checks, NOT hardware bug counts. Do not use the protocol adapter as a complete ISA oracle.'),
    ]
    if target_wave_gaps or any(item['status'] == 'UNREADABLE' for item in other_waves):
        defects.append(dict(id='INFRA-01', status='open-evidence-gap', kind='non-target waveform',
            title='Some ordinary-regression FSTs are not readable; native test PASS is not waveform proof',
            captures=target_wave_gaps + [item for item in other_waves if item['status'] == 'UNREADABLE'],
            note='No RTL/native binding changes made in this model-repair task'))
    atomic_json(out / 'defects.json', defects)
    report = dict(format='vagq-reference-fix-and-boundary-requalification', version=1,
        generated_at=datetime.now(timezone.utc).isoformat(), reference_bug_fixed=True,
        native_original_failure_uops=dict(shapes=2278, uops=13536, all_outputs_match=True),
        native_extended_policy=dict(**policy, full_output_mismatches=56),
        independent_semantic_qualification=semantic,
        independent_semantic_oracle_tests=semantic_junit,
        native_top_boundary_cases=8, native_new_sparse_variants=2,
        test_results=qualifications, reassessment=reassessment,
        original_full_campaign_outcomes=dict(PASS=6074, FAIL=2278, ERROR=0),
        original_full_campaign_statuses_unchanged=True,
        residual_canary_tests=dict(FAIL=2, XFAIL=0, waived=0),
        no_claim_of_all_output_or_isa_acceptance=True,
        current_nf_gt_zero_production_path_opened=False,
        rtl_native_and_independent_isa_oracle_unchanged=True,
        native_waveforms_decoded=len(waves), native_artifacts_preserved=True,
        target_waveform_qualities=dict(Counter(item['quality'] for item in waves)),
        target_waveform_decode_gaps=len(target_wave_gaps),
        non_target_waveform_statuses=dict(Counter(item['status'] for item in other_waves)),
        historical_files_hash_verified=len(baseline['historical_evidence']),
        historical_native_artifacts_hash_verified=protected_native,
        defect_ledger_sha256=digest(out / 'defects.json'))
    atomic_json(out / 'report.json', report)
    evidence = dict(before_baseline_sha256=digest(out / 'baseline.json'),
        tested_after_source_epoch_sha256=digest(out / 'after/source-hashes.json'),
        tested_after_sources_verified=len(after), native_manifests=runs,
        native_waveforms=waves, policy_journal_sha256=digest(policy_path),
        corrected_field_regression_journal_sha256=digest(repaired_policy),
        producer_journal_sha256=digest(producer_journal),
        sparse_failure_list_sha256=digest(out / 'sparse-mask-failures.json'),
        reassessment_table_sha256=digest(out / 'reassessment/reassessed-shapes.json'),
        protected_history_files=len(baseline['historical_evidence']),
        internal_git_head=baseline['internal_head'], internal_git_status='',
        generator_sha256=digest(Path(__file__)))
    evidence.update(semantic_qualification_sha256=digest(out / 'semantic-qualification/summary.json'),
        independent_spec_provenance_sha256=digest(out / 'semantic-qualification/spec/provenance.json'),
        target_waveform_gaps_sha256=digest(out / 'target-waveform-gaps.json'),
        non_target_waveform_audit_sha256=digest(out / 'non-target-waveform-audit.json'))
    atomic_json(out / 'evidence.json', evidence)
    for path in (Path(__file__), ROOT / 'tools/reassess_vagq_shape_boundaries.py'):
        target = out / 'report-sources' / path.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(path, target)
    write_readme(out, report)
    print(json.dumps({key: value for key, value in report.items() if key not in ('reassessment', 'test_results')}, indent=2))


def write_readme(out, report):
    regression = report['test_results']['regression']
    pure = report['test_results']['pure']
    counts = report['reassessment']['counts']
    lines = [
        '# 参考模型修复、分层检查与原生重新资格检查', '',
        '**参考模型的元素窗口错误已修复；原 2278 个失败 shape 的 13536 个 MaskGen uop 全输出 native 重验通过。**',
        '**扩展 canary 仍有 2 个真实 FAIL：56 个 MaskGen active-mask 分歧及 2 个顶层 sparse-mask 反例，未改成 XFAIL 或 waiver。**', '',
        '**native 一致不是正确性证明。另用官方 RVV v1.0 和不读取 RTL/MOP 表的寄存器 oracle 做独立语义资格检查，见下节。整个实现相关参考模型尚未认证。**', '',
        '## 已修改', '',
        '- `mop_info().destination_window` 使用字段内的元素窗口，不再混用 field-major 目标寄存器偏移；skip-merge 仍保留窗口身份。',
        '- 固定答案覆盖多字段、LMUL 多窗口、fractional、mask/tail/agnostic 与 skip-merge；不是从 DUT 输出反推答案。',
        '- 新 `assess_shape_boundaries()` 分开给出 raw 字节 Counter、public 生命周期与单 flow projection；旧 v2 checker 保留不变。',
        '- 新潜在缺陷台账见 `defects.json` 和项目 `docs/vagq-known-limitations.md`；RTL、原生库和生产译码不改。',
        '', '## 回归与资格检查', '',
        f'- 纯模型/反例资格检查：**{pure["passed"]} PASS**。',
        f'- 普通回归（显式 `not vagq_isa_audit`）：**{regression["passed"]} PASS、{regression["skipped"]} SKIP、0 FAIL、0 ERROR**。',
        '- 原失败集合的 MaskGen 全输出：2278/2278 shape、13536/13536 uop 匹配。旧的 10596 个 merge-mask 分歧消失。',
        '- 扩展策略矩阵：9024/9024 的 merge/window/agnostic 独立答案匹配；全输出仅 8968/9024 匹配，剩余 56 个 active-mask 分歧保留。',
        '- 实际顶层边界资格：8 个原输入重放，输入/事件与旧结果一致；分别保留地址、生命周期和 placement 结论。资格测试 PASS 不代表这些失败输入功能通过。',
        '- 扩展全输出/稀疏顶层 canary：**2 个 pytest FAIL**，正常结束并提交 native evidence；不是执行错误、未完成运行或被豁免。',
        '- 普通回归只验修复目标的策略测试也保存全部 56 个分歧；不能只引用普通回归 PASS 而省略 canary。',
        '', '## 8352 项既有事件的分层重审（不是重跑 8352 项）', '',
        '| 检查口径 | 一致/局部 PASS | 不一致/局部 FAIL |',
        '| --- | ---: | ---: |',
        f'| 原始 v2 composite（不改判） | {counts["legacy_v2"]["PASS"]} | {counts["legacy_v2"]["FAIL"]} |',
        f'| raw `(element,address)` 字节多重集 | {counts["raw_architectural_counter"]["PASS"]} | {counts["raw_architectural_counter"]["FAIL"]} |',
        f'| public admission/writeback/owner/timeout | {counts["public_lifecycle"]["PASS"]} | {counts["public_lifecycle"]["FAIL"]} |',
        f'| 单 flow projection 与架构字节比较（仅诊断） | {counts["single_flow_projection"]["MATCH"]} | {counts["single_flow_projection"]["DIFF"]} |',
        '',
        '1598 个旧失败的 raw 字节和生命周期均正确，但 placement 有差异；不能把它们报为地址 bug，也不能因此给完整功能 PASS。',
        '**另有 416 个旧 v2 PASS 的 raw Counter 不一致而 placement 一致**，是 wide fragment 原始范围和 flow 截取的差别；',
        '同样不能把它们自动报为 416 个新缺陷。新指标不替代旧指标，不用任何局部 PASS 冒充真实 LSU memory effect。',
        '每项整体 ISA/data acceptance 均为 `NOT_VERIFIED`。旧结果仍是 6074 PASS / 2278 FAIL / 0 ERROR。',
        '', '## 新增潜在缺陷 RTL-03：稀疏 mask 归属', '',
        '`VagqInfoGen.Uop.maskIdx` 使用第一个覆盖字节的 MOP；wide continuation 的 full mask 与后续元素起点重叠，',
        '后者因此错误使用前一个元素的 v0 位。独立逐 MOP 元素答案与参考模型 9024/9024 一致，',
        'first-cover 源等式与 native DUT 9024/9024 一致，二者的分歧恰好是 56 个 active-mask 样本。',
        '',
        '又在真实顶层运行 e32 / LMUL=1 / 5 fields / VL=4：`v0ByteMask=0x0f0f`、`0xf0f0`，',
        '对应元素 mask `0101`、`1010`。两组均实际发出 masked-off 元素请求，不只是一项 projection 差异。',
        '完整输入、原生事件、独立 ISA 字节答案及缺失/多余请求保存在 `sparse-top-variants.json` 与 canary cases。',
        '这些是新 variant，不加入旧 8352 inventory，不把 56 个样本或两个 variant 当作 58 个不同 bug。',
        '', '## 缺陷与生产边界', '',
        '- REF-01：已修复的参考模型错误。',
        '- RTL-01：零 mask／ACK 停滞；RTL-02：非零首 site 元素编号；INT-01：7-field 布局与请求/ACK 不一致；RTL-03：新增 sparse mask 归属。',
        '- 后四项保留为未修复模块级潜在缺陷/接口问题；它们的反例都是 nf>0，而当前 DecodeStage 的 useVAGQ 仍要求 nf=0。',
        '- 没有据此新增“当前生产译码可触发整机 ISA Bug”的结论；没有开放 segment、改 RTL、改 oracle、删失败或添加 waiver。',
        '- 最终 segment 数据、真实 SQ/Sbuffer/DCache/Uncache memory effect 和全芯片 ISA 验收仍未证明。',
        '', '## 证据与保留', '',
        '- `baseline.json`、`before/`：修前源码、RTL/native/oracle hash 和历史证据固定。',
        '- `after/source-hashes.json`、`after/sources/`：被测修后 source epoch。',
        '- `producer-recheck/`、`directed/`、`regression/`、`extended-canaries/`：独立 native/LCOV/manifest/FST/JUnit；初次扩展的真实失败也保留。',
        '- `reassessment/reassessed-shapes.json`、`.csv`：8352 项逐项分层结果，明确 `new_native_execution=false`。',
        '- `sparse-mask-failures.json`、`sparse-top-variants.json`、`defects.json`：全部新分歧与根因台账。',
        f'- `{report["native_waveforms_decoded"]}` 个目标相关原生 FST 有实际解码输出，类型为 `{report["target_waveform_qualities"]}`；另有 {report["target_waveform_decode_gaps"]} 个普通回归附带 capture 的明确解码缺口。主要修复/资格矩阵的 capture 均可读；单点 clockless 快照不冒充动态活动，全部均非逐 cycle ISA 证明。',
        f'- 核验 {report["historical_files_hash_verified"]} 个历史证据文件，以及 {report["historical_native_artifacts_hash_verified"]} 个历史 native/FST 等文件的 hash 未变。',
        '- 当前模型改变后，旧 exhaustive/review 工具应拒绝直接在旧 source epoch 续跑；需要重现旧代码时使用历史 source 快照。',
        '- 本轮保留 native coverage，但没有重新合并 RTL line/branch/toggle 总表，也没有满覆盖或 waiver 声明。',
        f'- 非模型目标波形另行记录：{report["non_target_waveform_statuses"]}。无法解码的 FST 不算波形证据，未解码的大型 stress capture 不宣称可读或有活动。',
        '', '## 复现', '', '```sh',
        'python3 tools/build_vagq_reference_fix_report.py results/vagq-reference-fix-20261020-v1',
        '```', '', '上述命令重审既有证据，不重跑仿真。实际 native 命令见 RUNS.md；重新执行必须使用全新的 output/cases 目录。',
    ]
    semantic = report['independent_semantic_qualification']
    lines.extend([
        '', '## 独立的参考模型语义资格（不以 RTL 为答案）', '',
        '- 规范来自官方 riscv/riscv-v-spec 的 v1.0 文档，内容/hash/条款保存在 `semantic-qualification/spec/`。',
        '- Oracle 只导入 dataclasses/fractions，输入架构 field/register/EEW/EMUL/vl/vstart/element-mask；不读取 RTL、MOP、native 结果或被测模型。',
        '- 通过架构寄存器逐元素旧值/计算值/允许的 agnostic 值检查 merge 的效果，而非要求模型复现 RTL 选中的位模式。',
        f'- 实际检查统计：`{semantic["counts"]}`；9 个 oracle 固定答案/隔离测试通过。',
        '- 修前的真实冻结模型被架构窗口数量/范围不变量拒绝；5 个额外错误变体被拒绝。',
        '- 保留旧值而不写全 1 的另一种 agnostic 策略被接受，尽管它与当前 RTL 选值不同；这用于证明 checker 没有把 RTL 位一致当作规范。',
        '- `vstart>=vl` 的无操作输入在没有 producer 抑制时存在语义分歧，完整保留在资格结果；不能把 component mask 输出直接作为该域的 ISA 答案。',
        '- 每个真实 uop 的 decoder/rename 架构寄存器身份、所有路径的 no-op 抑制、MOP/LSU/VRF 最终效果仍未独立证明。',
        '**可支持的结论仅是本次元素窗口修复及正常执行域的 merge 保留策略具有独立语义证据；不能说整个参考模型已经正确。**',
        '- 逐配置证据：`semantic-qualification/architectural-checks.json`；注错结果：`mutation-results.json`；执行摘要：`summary.json`。',
    ])
    (out / 'README.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
