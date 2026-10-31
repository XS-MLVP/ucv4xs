import ucv.runtime as ucv_paths
"""Audit the second reference repair and retain every residual correctness FAIL.

This consumes existing journals/manifests/native FSTs. It does not run the DUT,
waive a failure, change an ISA answer, or merge RTL coverage denominators.
"""
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_vagq_failure_review_report import check_manifest
from tools.build_vagq_reference_fix_report import (
    analyze_policy, audit_wave, historical_artifacts, junit, sparse_variants,
)
from tools.run_vagq_exhaustive import atomic_json, digest
from suites.vector.vagq.maskgen.flow_fixture import active_sites, flow_metadata, wide_flow
from suites.vector.vagq.maskgen.architectural import BoundDestination, DestinationBinding, DestinationInstruction
from suites.vector.vagq.maskgen.reference import MaskRequest, evaluate
from suites.vector.vagq.qualification.rvv_destination import Instruction as IndependentRegisterOracle
from suites.vector.vagq.split.model import idx_offset
from suites.vector.vagq.split.types import Entry
from suites.vector.vagq.vagq.model import _data_size, _slot_element
from suites.vector.vagq.vagq.types import AddrPacket
from suites.vector.vagq.waveform import read_public_samples


CONTRACTS = {
    'src/main/scala/xiangshan/backend/vector/vagq/SplitCtrl.scala': (52, 87),
    'src/main/scala/xiangshan/backend/vector/vagq/VagqInfoGen.scala': (41, 54),
    'src/main/scala/xiangshan/backend/vector/vagq/MaskGen.scala': (17, 66),
    'src/main/scala/xiangshan/backend/vector/Decoder/DecodeStage.scala': (195, 197),
    'src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala': (1931, 1941),
    'src/main/scala/xiangshan/mem/pipeline/NewStoreUnit.scala': (872, 881),
}


def audit_sources(out):
    baseline = json.loads((out / 'baseline.json').read_text())
    for name, expected in baseline['protected'].items():
        assert digest(ROOT / name) == expected, f'protected RTL/native/oracle changed: {name}'
    for name, expected in baseline['historical_evidence'].items():
        assert digest(ROOT / name) == expected, f'historical evidence changed: {name}'
    for name, expected in baseline['before_sources'].items():
        assert digest(out / 'before' / name) == expected
    tested = json.loads((out / 'after/source-hashes.json').read_text())
    for name, expected in tested.items():
        assert digest(ROOT / name) == digest(out / 'after/sources' / name) == expected
    docs = json.loads((out / 'before-docs/hashes.json').read_text())
    for name, expected in docs.items():
        assert digest(out / 'before-docs' / name) == expected
        destination = out / 'after' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    internal = ucv_paths.source_path_for(ROOT)
    assert subprocess.check_output(['git', 'status', '--short'], cwd=internal, text=True) == baseline['internal_status'] == ''
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=internal, text=True).strip() == baseline['internal_head']
    source_contracts = {}
    for name, lines in CONTRACTS.items():
        destination = out / 'source-contracts' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(internal / name, destination)
        source_contracts[name] = dict(sha256=digest(destination), relevant_lines=lines,
            scope='read-only implementation/consumer contract, not an architectural expected-value oracle')
    atomic_json(out / 'source-contracts/hashes.json', source_contracts)
    changed = {name: dict(before_sha256=baseline['before_sources'].get(name), after_sha256=value)
               for name, value in tested.items() if baseline['before_sources'].get(name) != value}
    atomic_json(out / 'after/changed-sources.json', changed)
    return dict(protected_files=len(baseline['protected']),
        historical_evidence_files=len(baseline['historical_evidence']), before_sources=len(baseline['before_sources']),
        tested_sources=len(tested), changed_sources=len(changed),
        source_epoch_sha256=digest(out / 'after/source-hashes.json'),
        internal_git_head=baseline['internal_head'], internal_git_status='',
        read_only_source_contracts=source_contracts)


def audit_qualification(out):
    directory = out / 'reference-qualification'
    result = json.loads((directory / 'summary.json').read_text())
    assert result['architecture_reference_status'] == 'PASS_FOR_DECLARED_BOUND_DESTINATION_DOMAIN'
    assert result['actual_rtl_producer_mapping'] == result['full_lsu_vrf_memory_effect'] == 'NOT_CLAIMED'
    assert not result['no_op_requires_unverified_upstream_gate']
    assert digest(directory / 'configurations.jsonl') == result['journal_sha256']
    count = Counter()
    configurations = []
    for line in (directory / 'configurations.jsonl').open():
        row = json.loads(line)
        assert row['fields'] >= 2
        count.update(row['counts'])
        count['configurations'] += 1
        configurations.append((row['data_eew'], row['index_eew'], row['emul'], row['fields']))
    assert len(set(configurations)) == len(configurations) == 401
    assert dict(count) == result['counts']
    assert count['noop_violations'] == count['running_violations'] == 0
    assert count['noop_checks'] == 186320 and count['running_checks'] == 255280
    assert result['mutations']['noop_ones_checks'] == result['mutations']['noop_ones_rejected'] > 0
    assert result['mutations']['active_clobber_rejected'] > 0
    for name, expected in json.loads((directory / 'source-hashes.json').read_text()).items():
        assert digest(ROOT / name) == digest(directory / 'sources' / name) == expected
    original_spec = ROOT / 'results/vagq-reference-fix-20261020-v1/semantic-qualification/spec'
    for path in original_spec.iterdir():
        if path.is_file():
            destination = directory / 'spec' / path.name
            destination.parent.mkdir(exist_ok=True)
            shutil.copy2(path, destination)
            assert digest(destination) == digest(path)
    return dict(**result,
        tested_domain='401 segment operand configurations (2..8 fields), sampled vl/vstart/masks/policies; not all bit patterns or nonsegment certification',
        overall_implementation_reference='NOT_CERTIFIED',
        immutable_oracle='qualification/rvv_destination.py',
        spec_provenance_sha256=digest(directory / 'spec/provenance.json'))


def audit_mask_journal(out):
    path = next((out / 'native-review/cases').rglob('maskgen-review.jsonl'))
    summary = json.loads(path.with_name('maskgen-review-summary.json').read_text())
    counts, failures, unique = Counter(), [], set()
    for line in path.open():
        row = json.loads(line)
        request = row['input']
        assert request['deew'] == request['ieew'] == 2 and request['emul'] == 0
        fragments = wide_flow(4, request['nf'] + 1, request['uop_idx'])
        metadata = flow_metadata(fragments)
        assert row['fragments'] == [asdict(fragment) for fragment in fragments]
        assert row['expected_metadata'] == metadata
        assert row['layout_validated'] and all(row['actual'][key] == value for key, value in metadata.items())
        expected = active_sites(fragments, vl=request['vl'], vstart=request['vstart'], element_mask=row['architectural_mask'])
        byte_mask = sum(0xF << (4 * bit) for bit in range(4) if row['architectural_mask'] >> bit & 1)
        assert byte_mask == request['v0_mask'] and expected == row['expected_active']
        assert row['matches'] == (row['actual']['elemActiveMask'] == expected)
        unique.add(tuple(sorted(request.items())))
        counts['samples'] += 1
        counts['active_matches'] += row['matches']
        # Source diagnosis only: full masks use the entire segment width,
        # not the actual fragment width. This is NOT the expected answer.
        source_first_cover = 0
        for fragment in fragments:
            first = next(other for other in fragments
                if other.site <= fragment.site < other.site + (request['nf'] + 1) * 4)
            if request['vstart'] <= fragment.element < request['vl'] and (row['architectural_mask'] >> first.element) & 1:
                source_first_cover |= 1 << fragment.site
        counts['first_cover_source_matches_native'] += source_first_cover == row['actual']['elemActiveMask']
        if not row['matches']:
            failures.append(row)
        if row['architectural_mask'] in (0, 15):
            assert row['matches']
            counts['all_on_off_controls'] += 1
    assert counts['samples'] == len(unique) == summary['samples'] == 7200
    assert len(failures) == summary['active_mismatches'] == 336
    assert counts['all_on_off_controls'] == summary['control_samples'] == 900
    assert summary['invalid_layout'] == 0 and summary['status'] == 'FAIL'
    assert counts['first_cover_source_matches_native'] == counts['samples']
    atomic_json(out / 'maskgen-independent-failures.json', failures)
    return dict(**counts, active_mismatches=len(failures), layout_mismatches=0,
        journal_path=str(path), journal_sha256=digest(path), overall_test_status='FAIL',
        expected_source='independent element-major stream, never candidate uop/MOP declarations')


def load_snapshot(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def audit_reference_defect_witnesses(out):
    """Run the ACTUAL frozen old functions, not merely invented bad variants."""
    old_mask = load_snapshot('suites.vector.vagq.maskgen._before_bound_repair',
        out / 'before/maskgen/reference.py')
    old_split = load_snapshot('suites.vector.vagq.split._before_bound_repair',
        out / 'before/split/model.py')
    old_top = load_snapshot('suites.vector.vagq.vagq._before_bound_repair',
        out / 'before/vagq/model.py')
    fragment = wide_flow(4, 5, 2)[1]
    entry = Entry(nf=4, deew=2, ieew=3, elem_base=2, start_byte=fragment.site)
    addr = AddrPacket(nf=4, deew=2, ieew=3)
    info = dict(elemBase=2, startByteOffset=fragment.site, startFieldOffset=0)
    witnesses = [
        dict(id='REF-03', property='wide first site offset', input=asdict(entry), site=fragment.site,
            independent_expected=0, frozen_before=old_split.idx_offset(fragment.site, entry),
            repaired=idx_offset(fragment.site, entry)),
        dict(id='REF-03', property='wide first site element', input=asdict(addr), metadata=info, site=fragment.site,
            independent_expected=fragment.element, frozen_before=old_top._slot_element(addr, info, fragment.site),
            repaired=_slot_element(addr, info, fragment.site)),
    ]
    special = AddrPacket(nf=6, deew=0, ieew=2)
    info = dict(elemBase=0, startByteOffset=0, startFieldOffset=0)
    sites = (0, 4, 8, 12)
    witnesses.append(dict(id='REF-03', property='special physical index-bank stride',
        input=asdict(special), sites=sites, independent_expected=[0, 1, 2, 3],
        frozen_before=[old_top._slot_element(special, info, site) for site in sites],
        repaired=[_slot_element(special, info, site) for site in sites]))
    for width, size in ((12, 4), (40, 4), (64, 4)):
        witnesses.append(dict(id='REF-04', property='size contains enabled bytes and is limited to one flow',
            request_bytes=width, independent_expected=size, frozen_before=old_top._data_size(width),
            repaired=_data_size(width)))
    instruction = DestinationInstruction(4, 1, 3, 0, 0, 0xF, 0, 1)
    bound = BoundDestination(instruction, DestinationBinding(1, 9, 1))
    request = MaskRequest(0xFFFF, 2, 2, 0, 0, 0, 0, 1, 1, 2)
    old_controls = old_mask.evaluate(old_mask.MaskRequest(**asdict(request)))
    repaired = evaluate(request, destination=bound)
    oracle = IndependentRegisterOracle(4, instruction.emul, 3, 0, 0, 0xF)
    register = oracle.registers()[1]
    old_errors = oracle.check_merge_controls(register,
        merge_mask=old_controls['mergeWriteMask'], agnostic_mask=old_controls['elemAgnosticMask'], vma=0, vta=1)
    new_errors = oracle.check_merge_controls(register,
        merge_mask=repaired.merge_write_mask, agnostic_mask=repaired.agnostic_byte_mask, vma=0, vta=1)
    assert old_errors and not new_errors and not repaired.destination_commit_allowed
    witnesses.append(dict(id='REF-02', property='no-op cannot apply component agnostic output as an ISA answer',
        request=asdict(request), independent_expected=0,
        frozen_before=old_controls['elemAgnosticMask'], repaired=repaired.agnostic_byte_mask,
        frozen_control_isa_violations=old_errors, repaired_isa_violations=new_errors,
        note='Raw protocol API remains separate; this rejects its old misuse as a complete architectural answer.'))
    assert all(row['frozen_before'] != row['independent_expected'] == row['repaired'] for row in witnesses)
    atomic_json(out / 'reference-defect-witnesses.json', witnesses)
    return witnesses


def split_wave_witness(vcd, requests):
    mapping = {'elem_idx': 'elemIdx', 'byte_offset': 'byteOffset',
               'data_mask': 'dataMask', 'data_size': 'dataSize', 'vaddr': 'vaddr'}
    names = [f'io_lsuReq_{lane}_{leaf}' for lane in range(3)
             for leaf in ('valid', *(f'bits_{value}' for value in mapping.values()))]
    samples = read_public_samples(vcd, names, module='SplitCtrlDut_top')
    witnesses = []
    for request in requests:
        hits = [dict(time=sample['time'], lane=lane) for sample in samples for lane in range(3)
                if sample['values'][f'io_lsuReq_{lane}_valid'] == 1
                and all(sample['values'][f'io_lsuReq_{lane}_bits_{leaf}'] == request[key]
                        for key, leaf in mapping.items())]
        assert hits, f'no actual native waveform witness for {request}'
        witnesses.append(dict(request=request, public_native_waveform_hits=hits))
    return witnesses


def mask_wave_journal_witness(vcd, journal):
    inputs = dict(v0_mask='in_v0ByteMask', deew='in_deew', ieew='in_ieew', emul='in_emul',
        vl='in_vl', vstart='in_vstart', vma='in_vma', vta='in_vta', uop_idx='in_uopIdx', nf='in_nf')
    outputs = ('elemValidMask', 'elemActiveMask', 'elemAgnosticMask', 'mergeWriteMask',
               'elemBase', 'startFieldOffset', 'startByteOffset', 'skipMerge')
    samples = read_public_samples(vcd, [*inputs.values(), *('out_' + name for name in outputs)],
        module='MaskGenDut_top')
    observed = Counter(tuple(sample['values'][name] for name in inputs.values())
        + tuple(sample['values']['out_' + name] for name in outputs) for sample in samples)
    logged = Counter(tuple(row['input'][name] for name in inputs)
        + tuple(row['actual'][name] for name in outputs)
        for row in (json.loads(line) for line in journal.open()))
    assert observed == logged and logged.total() == 7200
    return dict(logged_samples=logged.total(), native_timepoints=len(samples),
        all_input_and_output_tuples_match=True, missing_waveform_samples=0,
        scope='Actual native FST tuples, not reconstructed from JSON events; still not final memory effect')


def audit_primary_waves(out, split_rows, ack_rows):
    waves = []
    for name in ('split-protocol', 'native-review', 'top-sparse-canary'):
        for fst in sorted((out / name / 'cases').rglob('*.fst')):
            vcd = out / 'decoded' / name / fst.relative_to(out / name / 'cases').with_suffix('.vcd')
            receipt = audit_wave(fst, vcd)
            case = fst.parent
            if fst.stem == 'SplitCtrl' and (case / 'split-review.json').exists():
                receipt['public_output_witnesses'] = split_wave_witness(vcd, [split_rows[case.name]['actual']])
            if fst.stem == 'SplitCtrl' and (case / 'ack-contract-review.json').exists():
                row = ack_rows[case.name]
                receipt['public_output_witnesses'] = split_wave_witness(vcd, [row['first'], row['next']])
            if fst.stem == 'MaskGen' and (case / 'maskgen-review.jsonl').exists():
                receipt['public_input_output_journal_witness'] = mask_wave_journal_witness(vcd, case / 'maskgen-review.jsonl')
            waves.append(receipt)
    return waves


def audit_regression_waves(out):
    receipts = []
    for fst in sorted((out / 'regression/cases').rglob('*.fst')):
        base = dict(path=str(fst), sha256=digest(fst), size=fst.stat().st_size,
            scope='ordinary-regression attachment; not primary RTL-review proof')
        if fst.stat().st_size > 1_000_000:
            receipts.append(dict(**base, status='NOT_DECODED_LARGE_NON_TARGET', waveform_credit=False))
            continue
        vcd = out / 'decoded/regression' / fst.relative_to(out / 'regression/cases').with_suffix('.vcd')
        try:
            receipts.append(dict(**audit_wave(fst, vcd), status='READABLE', waveform_credit=True))
        except (AssertionError, RuntimeError) as error:
            receipts.append(dict(**base, status='UNREADABLE_OR_NO_ACTIVITY', error=str(error), waveform_credit=False))
    atomic_json(out / 'regression-waveforms.json', receipts)
    return receipts


def audit_historical_native(out):
    historical_artifacts(out)
    files = json.loads((out / 'protected-native-artifacts.json').read_text())
    previous = ROOT / 'results/vagq-reference-fix-20261020-v1'
    evidence = json.loads((previous / 'evidence.json').read_text())
    for manifest in evidence['native_manifests'].values():
        for item in manifest['artifacts']:
            files[item['path']] = item['sha256']
    for item in evidence['native_waveforms']:
        files[item['path']] = item['sha256']
        files[item['decoded_path']] = item['decoded_sha256']
    for name in ('target-waveform-gaps.json', 'non-target-waveform-audit.json'):
        for item in json.loads((previous / name).read_text()):
            files[item['path']] = item['sha256']
    for path, expected in files.items():
        assert digest(Path(path)) == expected, f'historical native/FST changed: {path}'
    atomic_json(out / 'protected-native-artifacts.json', files)
    return len(files)


def write_readme(out, report):
    tests, qualification = report['tests'], report['independent_reference_qualification']
    regression = tests['regression']
    lines = [
        '# 先修参考模型，再独立复核 RTL（第二轮）', '',
        '**已修复本轮识别的参考模型错误；RTL-01/02/03 与 INT-01 在独立预期下仍复现。未修改 RTL。**',
        '**新架构入口在显式绑定域通过独立语义检查；整个实现相关环境仍是 `NOT_CERTIFIED`。**', '',
        '## 参考模型改动', '',
        '- `maskgen/architectural.py` 只接受架构参数和显式 field/register 身份；不导入 RTL、MOP adapter 或资格 oracle。',
        '- `reference.evaluate()` 无显式 `BoundDestination` 时拒绝；有绑定时核对几何、ownership tag 和 v0 行，返回架构预期，而非 component 输出字典。',
        '- no-op 在参考自身处理：无 active memory elements、禁止目的提交、merge 保留全部、agnostic 为 0。不假设上游 gate。',
        '- 原 component 模型显式改名为 `evaluate_protocol()`，旧接口比较仍保留原输出域；不能把它当 ISA oracle。',
        '- SplitCtrl/顶层模型撤掉与 RTL 共有的 `site.orR` 错误，按独立字节流位置计算元素；顶层同时修正 special 步距和 request size 向上取整/饱和。',
        '- 无法来自合法首 MOP 的 fixture 会拒绝。替换了旧 protocol 测试中自相矛盾/不对齐的 fixture，修前代码完整保留；有效反例另行真实 FAIL。',
        '- SplitCtrl 功能分组升级为 v2，continuation 以 `startFieldOffset` 判定；不把旧 v1 覆盖混入新分母。', '',
        '## 独立资格，而非与 RTL 相等', '',
        f'- 所测 401 个 segment operand 配置：**{qualification["counts"]["running_checks"]} 次正常执行、{qualification["counts"]["noop_checks"]} 次 no-op，均零语义违规**。',
        '- 配置为 2..8 fields、VLEN=128、合法 EEW/EMUL/index ratio，含 fractional、多寄存器、mask/tail/agnostic、固定边界与定种子随机 profile；不是全部位模式穷举或非 segment 全域认证。',
        '- 绑定由未修改的独立 RVV register oracle 枚举，不能从候选返回的 window 标签反推身份。目的旧值/计算值/agnostic 允许集彼此可区分。',
        f'- 注错：no-op 全 1 错误 {qualification["mutations"]["noop_ones_rejected"]}/{qualification["mutations"]["noop_ones_checks"]} 被拒；active-clobber 在 {qualification["mutations"]["active_clobber_checks"]} 次检查中拒绝 {qualification["mutations"]["active_clobber_rejected"]} 次（没有 active 的实例本就不一定违规）。',
        f'- 本轮定向纯模型检查：**{tests["pure-final"]["passed"]} PASS**；另保留初次 {tests["pure"]["passed"]} PASS 的运行，不覆盖历史。',
        '- 固定答案验证 no-op、显式身份/错误 v0 行拒绝、同一身份更换 uop tag 不改答案，以及两种合法 agnostic 选择；reference 与 oracle 的依赖隔离均有检查。',
        '- `reference-defect-witnesses.json` 实际加载本轮修前冻结函数：旧的 wide 元素编号、special 步距、size 取整/饱和以及 no-op 答案均被独立固定语义拒绝；不是仅捏造一个错误变体。',
        '- 原独立 `rvv_destination.py` 与 `vagq/isa_reference.py` 内容 hash 未变。规范/provenance 复制自上一轮固定的官方 RVV v1.0 文件。', '',
        '## 修复后原生复核', '',
        '| 检查 | 结果 | 独立预期与实际 |',
        '| --- | --- | --- |',
        '| RTL-01：e64/5-field continuation | FAIL | field 2 后还剩 24 byte，当前请求应为非零完整 flow；实际 dataMask=0 |',
        '| 尾片控制组 | PASS | field 4 的尾片 mask 正确 |',
        '| RTL-02：非零首位置 | FAIL | 新 index bank 元素 2 从 site 8 开始，应为元素 2 / 0x8100；实际元素 3 / 0x8200 |',
        '| 零起点 index-bank 对照 | PASS | 元素/地址身份正确 |',
        '| request size 对照 | PASS | 12-byte mask 的 size=4，拒绝原顶层参考的 floor 预期 |',
        '| RTL-03：稀疏 v0 所有者 | FAIL | 7200 个独立字节流样本，0 个布局不一致、336 个 active 分歧；900 个全选/全不选对照通过 |',
        '| 非 segment ACK 对照 | PASS | 不会 ACK 未发元素，下一元素为 1 |',
        '| INT-01：special7 ACK | FAIL | 请求 0 的 0x007f ACK 提前覆盖 site 4，下一请求跳到元素 2 |', '',
        '**上述为 4 PASS / 4 FAIL，全部使用真实 generated RTL 和既有 picker+toffee 原生库。**',
        'SplitCtrl 的 fixture 先用独立流位置/固定 bank 身份确定 metadata，再核对原生 MaskGen producer；该 gate 通过后才评价下游。',
        '字节流 oracle 不使用 `allocated_uops()`/`mop_info()`，也不从 DUT active 输出推导预期。',
        'first-cover 源诊断等式与 7200 个 native 输出一致，但只作为根因定位，不作为正确性证明。336 是同一错误的样本数，不是 Bug 数。', '',
        '**顶层 sparse canary 又得到 1 个真实测试 FAIL：两组 variant 均请求 masked-off 元素。**',
        '`0x0f0f` / `0xf0f0` 的架构 mask 为 `0101` / `1010`；public 生命周期 PASS 不抵消其请求语义 FAIL。',
        '该顶层输入序列仍使用公开 producer adapter；独立字节/元素答案来自未修改 ISA oracle，与新的 component 独立 fixture 证据分开表述。', '',
        '## 回归不是全体验收', '',
        f'- 普通回归 `not vagq_isa_audit`：**{regression["passed"]} PASS、{regression["failures"]} FAIL、{regression["errors"]} ERROR、{regression["skipped"]} SKIP**。audit 测试未选入，不能用此数掩盖上述 5 个真实测试 FAIL。',
        '- 其中 scoped merge/window/agnostic 回归仍保存 9024 条全输出：目标字段全部相符，但完整输出仍有 56 个 active 分歧，`full_output_acceptance=false`。这项普通测试仅对修复字段 PASS，不是完整 MaskGen 功能 PASS。',
        '- 单独的 SplitCtrl protocol 回归 1 PASS；所有 native manifest 已 committed 且 coverage artifacts hash 有效。',
        '- 不用 XFAIL、waiver 或“失败数量符合预期”将 correctness FAIL 改记 PASS。报告中的 FAIL 是保留的功能反例，不是 infra ERROR。', '',
        '## 结论边界', '',
        '- RTL-01/02/03：高可信模块级潜在实现缺陷；INT-01：producer/request/consumer ACK 契约不一致，修复归属需统一。均未修 RTL。',
        '- INT-01 的 ACK 是按 NewLoadUnit/NewStoreUnit 源契约驱动，不是实际 LSU 仿真，更不是 SQ/Sbuffer/DCache/Uncache memory effect。',
        '- 所有异常反例为 nf>0；DecodeStage.scala:195-197 的 useVAGQ 仍要求 nf=0。本轮没有新确认的现行生产译码可触发整机 Bug。',
        '- 真实 decoder/rename 的 uop→架构寄存器绑定、v0 行来源及实际 no-op 不提交尚未贯通；新绑定 API 不构成这些桥接条件的证明。',
        '- 原 8352-shape 结果保持 6074 PASS / 2278 FAIL / 0 ERROR；本轮未重跑该全量 campaign，也不改旧判定。',
        '- 1598 个 narrow-spill/placement 差异不能升级为地址 Bug。没有以 raw 请求、synthetic ACK 或单 flow placement 冒充最终数据或整机 ISA PASS。',
        '- line/branch/toggle 分开保留 native artifacts，本轮未正式合并 RTL 总表或审查逐点 waiver；没有满覆盖声明。', '',
        '## 证据目录', '',
        '- `before/` / `baseline.json`：修前源码及保护清单；`after/sources/` / `source-hashes.json` / `changes.diff`：本轮被测 source epoch。',
        '- `reference-qualification/`：401 行配置记录、检查/注错统计、固定 oracle/spec 与资格源码快照。',
        '- `native-review/cases/`：7200 条输入/输出、5 个 split fixture 与 2 个 ACK 记录、真实 FST；`maskgen-independent-failures.json` 完整保存 336 条分歧。',
        '- `top-sparse-canary/`、`regression/`、`split-protocol/`：各自 JUnit/native/LCOV/manifest。',
        '- `decoded/` / `evidence.json`：真实 FST 解码及 SplitCtrl 输出 tuple 对应时间戳；不由事件日志重建波形。',
        '- MaskGen 的 7200 条完整输入/输出 tuple 与实际原生 FST 的 7200 个时间点多重集完全相符，不只检查文件非空。',
        f'- 主要运行共解码 {len(report["primary_waveforms"])} 个 FST，类型 {dict(Counter(item["quality"] for item in report["primary_waveforms"]))}；静态 clockless 快照不当动态证据。',
        f'- 普通回归附带波形状态：{report["regression_waveform_statuses"]}。不可读/未解码的 capture 不给波形 credit，INFRA-01 仍开放。',
        f'- 保护 hash：{report["source_audit"]["protected_files"]} 个 RTL/native/oracle、{report["source_audit"]["historical_evidence_files"]} 个历史证据和 {report["historical_native_artifacts_hash_verified"]} 个历史 native/FST 等文件均未变；XiangShan-internal status clean。',
        '- 未提交或推送；`RUNS.md` 给出实际命令。重跑仿真必须改用全新 output/cases 路径，不能让 pytest basetemp 覆盖本证据。', '',
        '只重审已有证据：', '', '```sh',
        'python3 tools/build_bound_reference_rtl_review_report.py results/vagq-reference-repair-rtl-rereview-20261020-v2',
        '```', '',
        '该审计工具不执行 DUT。旧报告的复核应使用对应冻结 source epoch，不能用当前源码直接续写旧目录。',
    ]
    (out / 'README.md').write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    source_audit = audit_sources(out)
    qualification = audit_qualification(out)
    reference_witnesses = audit_reference_defect_witnesses(out)
    names = ('split-protocol', 'native-review', 'regression', 'top-sparse-canary')
    manifests = {name: check_manifest(out / name / 'execution/manifest.json') for name in names}
    tests = {name: junit(out / name / 'pytest.xml') for name in (*names, 'pure', 'pure-final')}
    assert manifests['split-protocol']['pytest_exitstatus'] == manifests['regression']['pytest_exitstatus'] == 0
    assert tests['regression']['failures'] == tests['regression']['errors'] == 0
    assert tests['pure-final']['passed'] == 162 and tests['pure-final']['failures'] == tests['pure-final']['errors'] == 0
    assert manifests['native-review']['pytest_exitstatus'] == manifests['top-sparse-canary']['pytest_exitstatus'] == 1
    assert tests['native-review']['passed'] == tests['native-review']['failures'] == 4
    assert tests['top-sparse-canary']['failures'] == 1
    assert all(not item['errors'] and not item['skipped'] for item in tests.values())
    mask = audit_mask_journal(out)
    focused_journal = next((out / 'regression/cases').rglob('element-window-samples.jsonl'))
    focused_counts, focused_failures = analyze_policy(focused_journal)
    focused_summary = json.loads(focused_journal.with_name('element-window-summary.json').read_text())
    assert focused_summary['asserted_scope'] == 'fixed merge/agnostic/window fields ONLY'
    assert focused_summary['fixed_field_mismatches'] == 0
    assert focused_summary['full_output_mismatches'] == 56 and focused_summary['full_output_acceptance'] is False
    atomic_json(out / 'focused-regression-active-mismatches.json', focused_failures)
    split_rows = {path.parent.name: json.loads(path.read_text())
                  for path in (out / 'native-review/cases').rglob('split-review.json')}
    ack_rows = {path.parent.name: json.loads(path.read_text())
                for path in (out / 'native-review/cases').rglob('ack-contract-review.json')}
    assert len(split_rows) == 5 and len(ack_rows) == 2
    by_case = {row['case']: row for row in split_rows.values()}
    assert all(row['layout_validated'] for row in by_case.values())
    assert by_case['wide_zero_mask']['actual']['data_mask'] == 0
    assert by_case['wide_zero_mask']['expected']['data_mask'] == 0xFFFF
    assert by_case['nonzero_first']['actual']['elem_idx'] == 3
    assert by_case['nonzero_first']['expected']['elem_idx'] == 2
    assert by_case['nonzero_first']['actual']['vaddr'] == 0x8200
    assert by_case['nonzero_first']['expected']['vaddr'] == 0x8100
    assert Counter(row['status'] for row in split_rows.values()) == {'PASS': 3, 'FAIL': 2}
    for row in by_case.values():
        recomputed = {key: dict(expected=value, actual=row['actual'][key])
            for key, value in row['expected'].items() if row['actual'][key] != value}
        assert recomputed == row['differences']
        assert all(row['repaired_reference'][key] == value for key, value in row['expected'].items())
    special = next(row for row in ack_rows.values() if row['special'])
    control = next(row for row in ack_rows.values() if not row['special'])
    assert special['consumer_ack'] == 0x7F and special['prematurely_acked_active_sites'] == 0x10
    assert special['next']['elem_idx'] == 2 and special['status'] == 'FAIL'
    assert control['consumer_ack'] == 1 and control['prematurely_acked_active_sites'] == 0
    assert control['next']['elem_idx'] == 1 and control['status'] == 'PASS'
    for row in ack_rows.values():
        assert row['consumer_ack'] == (row['first']['data_mask'] << row['first']['byte_offset']) & 0xFFFF
        expected_sites = 0x1111 if row['special'] else 0xF
        assert row['producer_metadata']['elemValidMask'] == row['producer_metadata']['elemActiveMask'] == expected_sites
    sparse = sparse_variants(out / 'top-sparse-canary')
    atomic_json(out / 'sparse-top-variants.json', sparse)
    primary = audit_primary_waves(out, split_rows, ack_rows)
    regression_waves = audit_regression_waves(out)
    native_history = audit_historical_native(out)
    defects = [
        dict(id='REF-01', kind='reference', status='fixed-previous-round', title='Destination-window/field-major confusion', new_fix=False),
        dict(id='REF-02', kind='reference', status='fixed-for-explicit-bound-domain', title='Unbound identity and no-op protocol/ISA conflation', checks=qualification['counts'], producer_mapping_proven=False),
        dict(id='REF-03', kind='reference', status='fixed', title='Shared site.orR and special-stride element identity error'),
        dict(id='REF-04', kind='reference', status='fixed', title='Top-level request size floor and missing flow saturation'),
        dict(id='RTL-01', kind='latent-module-implementation', status='open', fixture=by_case['wide_zero_mask'], production_decode_reachable=False),
        dict(id='RTL-02', kind='latent-module-implementation', status='open', fixture=by_case['nonzero_first'], production_decode_reachable=False),
        dict(id='RTL-03', kind='latent-module-mask-ownership', status='open', sample_summary=mask, sparse_top=sparse, production_decode_reachable=False),
        dict(id='INT-01', kind='producer-request-consumer-contract', status='open', fixture=special, consumer_source_contract_only=True, real_lsu_executed=False, production_decode_reachable=False),
        dict(id='SCOPE-01', kind='overall-reference-qualification', status='NOT_CERTIFIED', blocker='Actual producer/rename architectural identity, v0 row provenance, actual no-op commit suppression and final LSU/VRF effects are not independently connected.'),
        dict(id='INFRA-01', kind='waveform-evidence', status='open', previous_gaps_preserved=True, current_ordinary_statuses=dict(Counter(row['status'] for row in regression_waves))),
    ]
    atomic_json(out / 'defects.json', defects)
    report = dict(format='bound-reference-repair-and-independent-native-rtl-review', version=2,
        generated_at=datetime.now(timezone.utc).isoformat(), source_audit=source_audit,
        independent_reference_qualification=qualification, tests=tests,
        actual_frozen_before_reference_witnesses=reference_witnesses,
        native_component_review=dict(PASS=4, FAIL=4, ERROR=0, XFAIL=0, waived=0),
        native_maskgen_samples=mask, native_top_variants=sparse,
        focused_merge_regression=dict(counts=focused_counts, full_output_mismatches=56,
            full_output_acceptance=False, journal_sha256=digest(focused_journal)),
        primary_waveforms=primary, regression_waveform_statuses=dict(Counter(row['status'] for row in regression_waves)),
        historical_native_artifacts_hash_verified=native_history,
        full_campaign_rerun=False, original_8352_outcomes=dict(PASS=6074, FAIL=2278, ERROR=0),
        historical_outcomes_unchanged=True, rtl_native_oracles_modified=False,
        overall_reference_certified=False, whole_chip_bug_confirmed=False,
        full_lsu_vrf_memory_effect_verified=False, rtl_coverage_totals_newly_merged=False,
        native_manifests=manifests, defects_sha256=digest(out / 'defects.json'))
    atomic_json(out / 'report.json', report)
    evidence = dict(baseline_sha256=digest(out / 'baseline.json'), source_audit=source_audit,
        primary_waveforms=primary, manifests=manifests,
        qualification_summary_sha256=digest(out / 'reference-qualification/summary.json'),
        actual_frozen_before_witnesses_sha256=digest(out / 'reference-defect-witnesses.json'),
        mask_journal_sha256=mask['journal_sha256'], mask_failures_sha256=digest(out / 'maskgen-independent-failures.json'),
        focused_merge_regression_journal_sha256=digest(focused_journal),
        focused_regression_active_mismatches_sha256=digest(out / 'focused-regression-active-mismatches.json'),
        top_variants_sha256=digest(out / 'sparse-top-variants.json'),
        regression_wave_audit_sha256=digest(out / 'regression-waveforms.json'),
        historical_native_protection_sha256=digest(out / 'protected-native-artifacts.json'),
        generator_sha256=digest(Path(__file__)))
    atomic_json(out / 'evidence.json', evidence)
    destination = out / 'report-sources' / Path(__file__).name
    destination.parent.mkdir(exist_ok=True)
    shutil.copy2(Path(__file__), destination)
    write_readme(out, report)
    print(json.dumps(dict(reference_qualification=qualification['counts'],
        tests={name: {key: item[key] for key in ('passed', 'failures', 'errors', 'skipped')} for name, item in tests.items()},
        source_audit={key: value for key, value in source_audit.items() if key != 'read_only_source_contracts'},
        native_mask_samples=mask, decoded_primary_fsts=len(primary),
        regression_waveforms=report['regression_waveform_statuses'],
        overall_reference_certified=False, rtl_modified=False, report=str(out / 'README.md')), indent=2))


if __name__ == '__main__':
    main()
