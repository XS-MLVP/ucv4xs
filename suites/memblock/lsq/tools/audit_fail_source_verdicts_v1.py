import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Closed source adjudication of all 228 frozen failed nodes. Never runs a DUT.

The decision is whether the failed obligation identifies a real RTL defect in
the supported interface, not whether an ISA failure has been demonstrated.
Source mechanisms and concrete public histories are both required. Issue names
are NOT used to decide a verdict. All original results stay immutable.
"""
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess

from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases, failure_digest
from run_summary import aggregate

ROOT = Path(__file__).resolve().parents[1]
REPO = ucv_paths.source_path_for(ROOT)
COMMIT = '893e1580b705d81f113c30c7a05734e09a08050e'
OUT = ROOT / 'results/fail-source-adjudication-01'
RUNS = ('lsq-progress-regression-15', 'replay-cause-lifetimes-contributor-regression-03')


def load(path):
    return json.loads(path.read_text())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def source(relative, start, end, *required):
    if relative.endswith('.scala'):
        name = 'src/main/scala/xiangshan/' + relative
        path = REPO / name
        raw = subprocess.check_output(['git', 'show', f'{COMMIT}:{name}'], cwd=REPO)
        assert path.read_bytes() == raw, ('not pinned source', path)
        display = 'XiangShan/' + name
    else:
        path = ROOT / relative
        raw = path.read_bytes()
        display = 'memblock-hash/lsq/' + relative
        if relative.startswith('rtl/'):
            assert digest(raw) == load(path.parent / 'source.json')['files'][path.name]
    snippet = '\n'.join(raw.decode().splitlines()[start - 1:end]) + '\n'
    assert all(token in snippet for token in required), (display, start, end, required)
    return dict(path=display, start=start, end=end, source_SHA256=digest(raw),
        snippet_SHA256=digest(snippet.encode()), code=snippet, checked_expressions=list(required))


def protected():
    before = load(ROOT / 'results/fail-review-baseline-01/preflight-guard-v1.json')
    for name, old in before['protected_SHA256s'].items():
        assert digest((ROOT / name).read_bytes()) == old, ('old evidence changed', name)
    exclude = {'tests/fail_review/conftest.py', 'tests/fail_review/test_public_contracts.py',
        'tools/audit_fail_review_v1.py', 'tools/fail_source_capture_v1.py', 'tools/audit_fail_source_verdicts_v1.py'}
    for group, expected in before['old_source_groups'].items():
        path = ROOT / ('docs/contracts' if group == 'docs' else group)
        paths = path.rglob('*') if path.is_dir() else (path,)
        entries = [(str(p.relative_to(ROOT)), digest(p.read_bytes())) for p in paths if p.is_file()
            and '__pycache__' not in p.parts and p.suffix != '.pyc' and str(p.relative_to(ROOT)) not in exclude]
        assert aggregate(entries) == expected, ('old verification source changed', group)
    return dict(old_artifacts=141, all_old_artifact_bytes_equal=True,
        all_preexisting_RTL_model_fixture_tests_manifest_and_indices_unchanged=True)


def root_definitions():
    sq = 'mem/lsqueue/NewStoreQueue.scala'
    roots = {}

    def add(key, bug, title, why, obligation, *refs):
        roots[key] = dict(is_RTL_bug=bug, verdict='是RTL bug' if bug else '不是RTL bug', title=title,
            root_cause=why, expected_behavior=obligation, source_evidence=list(refs))

    add('FWD-ALIAS-001', True, 'PA别名跨16B覆盖被VA相对重叠域漏掉',
        '物理CAM之前使用的overlapCandidate由VA派生的next16B决定坐标；别名VA的年轻Store尾段从物理候选中被删掉，VA/PA掩码比较也发现不了它，最终允许旧字节无阻塞地前递。',
        '旧Store写0xabc010..13，新Store从0xabc00c连续写8B；Load读0xabc010时必须得到新Store的0x22或要求重放，不能无条件接受旧0x11。',
        source(sq, 462, 476, 'dataEntry.vaddrPageTag === s1LoadVaddrTag'),
        source(sq, 487, 511, 'val loadInNext16B   = s1Next16BMatchVec(j)', 's1OverlapMask & addrValidVec'),
        source(sq, 606, 625, '}).asUInt & s2OverlapCandidateVec', '(s2PaddrMatchVec ^ s2VaddrForward).orR'),
        source('rtl/forward_module/ForwardModule.sv', 3118, 3123, 'io_dataEntriesIn_0_vaddr[49:12] == s1LoadVaddr[45:8]'),
        source('rtl/forward_module/ForwardModule.sv', 11323, 11330, 's2OverlapCandidateVec ^ s2VaddrForward'))
    add('FWD-RANGE-001', True, '循环旋转mask折回未写PA字节',
        'byteSelectOffset是4bit模16减法，mask被循环旋转并仅与Load掩码相与；缺少Store在当前物理16B段实际字节范围的裁剪。',
        '8B Store起于offset12，读首段只能mask0xf000，读尾段只能mask0x000f；实际0xf00f含不存在的producer。',
        source(sq, 606, 606, 's2LoadStart - s2SelectDataEntry.byteStart'),
        source(sq, 627, 644, 'rotateByteRight(s2SelectDataEntry.byteMask, j)', 's2OutMask'),
        source('rtl/forward_module/ForwardModule.sv', 991, 991, "4'(s2LoadStart - s2SelectDataEntry_vaddr[3:0])"),
        source('rtl/forward_module/ForwardModule.sv', 1450, 1498, 's2SelectDataEntry_byteMask'),
        source(sq, 1931, 1949, 'dataEntries(stWbIdx).byteMask', 'CalculateSelectMask'))
    add('FWD-SQID-001', True, '物理窗口裁剪后依赖沿用Load的SQ代号',
        '地址掩码已裁到physicalUpper，但命中低半区时operation_flag仍直接拷贝Load的flags，而不是命中Store所属的deq窗口代号。',
        'deq60/upper124/Load128，slot48是SQ112，不是SQ176；缺数据依赖必须指向真实Store。',
        source(sq, 390, 395, 'Mux(s0LoadOutOfRange, s0PhysicalQueueUpperMask, s0LoadMask)'),
        source(sq, 548, 564, 's1LoadSqIdx.operation_flag', 'RegEnable(s1DataInvalidSqIdx'),
        source('rtl/forward_module/ForwardModule.sv', 5158, 5161, '{s1LoadSqIdx_first_flag, s1LoadSqIdx_second_flag}'))
    add('LQU-SID-001', True, '外部SID归还后旧entry仍接收同SID响应',
        'slaveAccept只在取消/重新分配/Load消费时清除，未在原响应到达时清除；父级按slaveAccept和SID路由，entry在任何resp.fire时重写数据/错误，即使已在wait状态。',
        'A响应后未消费，B合法重用已归还SID；A后续有效bypass仍必须保留A的数据和错误。',
        source('mem/lsqueue/LoadQueueUncache.scala', 94, 109, 'slaveAccept := true.B', 'writeback'),
        source('mem/lsqueue/LoadQueueUncache.scala', 190, 197, 'when (io.uncache.resp.fire)', 'uncacheData := io.uncache.resp.bits.data'),
        source('mem/lsqueue/LoadQueueUncache.scala', 432, 440, 'e.io.slaveId.valid && e.io.slaveId.bits'),
        source('cache/dcache/Uncache.scala', 493, 499, 'when(resp.fire)', 'updateReturn'),
        source('rtl/load_queue_uncache/UncacheEntry.sv', 247, 252, 'slaveAccept <= ~_GEN_0 & (slaveAck | ~writeback & slaveAccept);'),
        source('rtl/load_queue_uncache/UncacheEntry.sv', 325, 330, 'uncacheData <= io_uncache_resp_bits_data;'))
    add('LRQ-STRICT-001', True, '未入队的lane可清除活动strict状态',
        '索引由无效feedback的schedIndex或不可用allocateSlot决定，strict的otherwise写没有enqFireBase门控；因此没有事务的lane仍能清活动entry，随后地址位图错误放行。',
        'strict owner在真实指针/匹配执行唤醒之前，不能被无效feedback或单个ready位提前调度。',
        source('mem/lsqueue/LoadQueueReplay.scala', 393, 402, '!strict(i) && stAddrReadyVec', 'storeAddrWakeupVec'),
        source('mem/lsqueue/LoadQueueReplay.scala', 825, 837, 'val enqIndex = Mux', 'val enqFireBase'),
        source('mem/lsqueue/LoadQueueReplay.scala', 861, 865, '}.otherwise{', 'strict(enqIndex) := false.B'),
        source('rtl/load_queue_replay/LoadQueueReplay.sv', 11212, 11221, 'enqIndex ==', 'io_enq_0_bits_schedIndex'),
        source('rtl/load_queue_replay/LoadQueueReplay.sv', 24112, 24114, '_GEN_1580 = ~_GEN_4 & strict_0'))
    add('RAR-REL-001', True, 'release valid比地址多一级寄存',
        'release2Cycle本身已是RegEnable寄存器，又把其valid的D端接到一个RegNext的Q端，形成两级valid延迟；地址仍只在原release有效时保存。孤立脉冲的关联窗口因此从当前/前拍变成当前/前两拍。',
        '前拍同line release必须与得到数据的年轻Load关联。过期额外nuke是窗口/性能错误，不单独宣称ISA数据破坏。',
        source('mem/lsqueue/LoadQueueRAR.scala', 130, 138, 'val release2Cycle = RegEnable', 'release2Cycle.valid := RegNext'),
        source('mem/lsqueue/LoadQueueRAR.scala', 181, 189, 'release2Cycle.valid', 'release1Cycle.valid'),
        source('rtl/load_queue_rar/LoadQueueRAR.sv', 11865, 11868, 'release2Cycle_valid <= release2Cycle_valid_REG;', 'release2Cycle_valid_REG <= io_release_valid;'))
    add('DEQ-WB-001', True, 'Cache/IO错误在WB背压时无条件清除',
        '错误寄存器在writeback状态就清0，而状态退出要等writeBack.fire。ready=0时有效WB仍在，payload错误已被清掉；Cache denied/corrupt路径在Scala和SV都如此。',
        '已接受响应的错误必须保持到该原owner的实际WB.fire，而不是只在首次valid时正确。',
        source(sq, 1082, 1117, 'hasHardwareError := false.B', 'hasAccessFault := false.B', 'io.writeBack.valid := writeBackValid'),
        source('rtl/deq_module/DeqModule.sv', 373, 378, 'io_writeBack_ready & writeBackValid', '_GEN_5 = _GEN_4 | _GEN_0'),
        source('rtl/deq_module/DeqModule.sv', 406, 415, '~_GEN_5 & hasHardwareError', '~_GEN_5 & hasAccessFault'),
        source('mem/MemBlock.scala', 1028, 1034, 'sqStoutLatch.ready := !storeUnits(i).io.stout.toRob.valid'))
    add('DEQ-SPLIT-WLINE-001', True, 'split尾段的数据owner与wline owner不同',
        'lane1的地址/数据/mask被headCross16B切到head尾段，但wline仍取lane1相邻entry；相邻CBO.zero因而把普通Store尾段标成整line写。',
        'split首尾控制都必须属于原普通Store；wline是有效整line写控制，不是无效payload。',
        source(sq, 1180, 1188, 'Mux(headCross16B, outData(0)', 'vaddrHigh'),
        source(sq, 1243, 1248, '(headCross16B && toSbufferValid(0))'),
        source(sq, 1262, 1272, 'port.bits.wline    := ctrlEntry.isCbo && isCboZero(dataEntry.cboType)'),
        source('rtl/deq_module/DeqModule.sv', 490, 510, '.io_fromDeqModule_1_bits_wline', 'io_rdataCtrlEntries_1_isCbo'),
        source('mem/sbuffer/Sbuffer.scala', 148, 156, 'line_write_buffer_wline', 'mask(line)(word)(byte) := true.B'))
    add('DEQ-ZERO-001', True, 'CBO.zero误借旧FIFO请求的fire完成自身零写',
        'writeZero用外部Sbuffer lane0的任意fire退出；但本CBO的入FIFO条件要求dataQueue为空。旧普通Store出FIFO的那拍，zero尚不能入队，却被当成zero已经写出。',
        'CBO.zero必须有自己的零写/整line传输，不能只有旧Store的fire就进入flush/WB/释放。',
        source(sq, 975, 983, 'when(io.writeToSbuffer.req.head.fire)', 'CboState.flushSb'),
        source(sq, 1212, 1219, 'cboState === CboState.writeZero && dataQueue.io.empty'),
        source(sq, 1289, 1294, 'io.writeToSbuffer    <> dataQueue.io.toSbuffer'),
        source('rtl/deq_module/DeqModule.sv', 324, 329, "cboState == 3'h1 & _dataQueue_io_empty"),
        source('rtl/deq_module/DeqModule.sv', 385, 390, 'io_writeToSbuffer_req_0_ready & _dataQueue_io_toSbuffer_req_0_valid'))
    add('DEQ-FINISH-ORDER-001', True, '无身份PopCount越过未完成的老SQ项',
        'deq窗口两个entry的handleFinish与Sbuffer credits直接相加，没有保证它们构成从head起的连续完成前缀。rdata可领先deq，年轻特殊项完成能为仍未消费的老普通项提供错误的释放数。',
        'SQ回收必须是连续已完成前缀。不是简单把晚完成项数量加到旧head上；提前清除addrValid/dataValid还会丢失Forward来源。',
        source(sq, 1296, 1324, 'uncacheMove = VecInit', 'io.sqDeqCnt := PopCount'),
        source(sq, 1658, 1659, 'handleFinishSet = rdataPtrExt.head.value'),
        source(sq, 1698, 1701, 'elsewhen(deqCancel || needCancel(i))', 'addrValid    := false.B'),
        source('rtl/deq_module/DeqModule.sv', 343, 360, 'io_deqCtrlEntries_1_handleFinish', '_io_sqDeqCnt_T_15'))
    add('LSQ-BUS-OWNERSHIP-001', True, '旧NC响应无身份解锁后来串行事务',
        'NC outstanding事务不占pendingstate，但其旧响应仍可在后来IO Store占用s_store时令其归idle；response方向只用于路由，没有用于判断串行owner是否完成。',
        '旧NC Load的返回不能清除仍欠自己响应的IO Store串行占用。外部Uncache e0也没有必先排空所有旧NC才接受另一block IO的门控。',
        source('mem/lsqueue/LSQWrapper.scala', 282, 300, 'io.uncacheOutstanding && io.uncache.req.bits.nc', 'when(io.uncache.resp.fire)'),
        source('mem/lsqueue/LSQWrapper.scala', 311, 325, 'io.uncache.resp.bits.is2lq'),
        source('cache/dcache/Uncache.scala', 365, 384, 'val e0_reject', 'req_ready := !e0_reject'),
        source('rtl/lsq_wrapper/LsqWrapper.sv', 1499, 1508, 'io_uncache_resp_valid', "pendingstate <= 2'h0"))
    add('NOT-VSQ-DOMAIN', False, '同拍dispatch+redirect违反固定上游互斥',
        '用例要求VSQ处理普通producer不会同时送达的组合。LsqEnqCtrl先!redirect门控再打一拍dispatch，MemBlock对同源redirect打一拍，因此LSQ收到两者互斥；不是当前正常producer路径的RTL bug。',
        '保留接口压力FAIL，但不能把违反上游互斥的ghost判断当作正常RTL缺陷。',
        source('mem/lsqueue/LSQWrapper.scala', 499, 502, '!io.redirect.valid', 'RegNext(do_enq)'),
        source('mem/MemBlock.scala', 494, 494, 'RegNextWithEnable(io.redirect)'),
        source('mem/MemBlock.scala', 1055, 1058, 'lsq.io.enq', 'lsq.io.brqRedirect'),
        source('mem/lsqueue/VirtualStoreQueue.scala', 151, 164, 'val enqSet', '!io.redirect.valid'))
    add('NOT-MMIO-DOMAIN', False, 'pending越过未完成MMIO的非法许可',
        '测试把pending直接推进到第二个未完成MMIO之后，制造多个selector。真实pending由ROB deq头产生；未完成的前一条MMIO不能被提交并越过，所要求的多selector保序不是正常许可历史。',
        'pending必须维持最老未完成ROB位置，不是可任意驱动的多个MMIO授权位。',
        source('backend/rob/Rob.scala', 1248, 1258, 'val pendingPtrInput = WireInit(deqPtr)', 'io.lsq.pendingPtr'),
        source('mem/lsqueue/LoadQueueUncache.scala', 122, 126, 'isNotAfterSlot(pendingPtr)'),
        source('mem/lsqueue/LoadQueueUncache.scala', 421, 453, 'mmioSelect'),
        source('tests/load_uncache/test_timing_boundaries.py', 105, 123, 'UNIT-INTERFACE', 'pending'))
    add('NOT-RAR-REPLAY-ROUTING', False, '验证producer把RAR回滚错接成C_NK重放',
        'MixedOwners把RAR nuke也赋成Cause.VIOLATION，再把同一个老Load送回Replay而不flush年轻已released的Load；同一个RAR冲突永远存在，造成5000拍超时。RTL按给定C_NK正常重放，不是RTL死锁。',
        '真实LDU的RAR违约走flushAfter回滚；C_NK来自较老STA同拍nuke，二者不能混用。',
        source('tests/lsq_wrapper/mixed_owners.py', 316, 328, 'rarNukeQuery', 'Cause.VIOLATION'),
        source('tests/lsq_wrapper/mixed_owners.py', 224, 231, 'causes=0 if cause is None else 1 << cause'),
        source('mem/pipeline/NewLoadUnit.scala', 1020, 1031, 'io.staNukeQueryReq', 'val nuke ='),
        source('mem/pipeline/NewLoadUnit.scala', 1118, 1125, 'cause(C_NK) := troubleMaker && nuke'),
        source('mem/pipeline/NewLoadUnit.scala', 1496, 1504, 's3RarViolation', 'RedirectLevel.flushAfter'))
    add('NOT-CBO-SIZE-PRODUCER', False, '原混合seed28928伪造8B CBO.zero',
        '首次physical-byte断言中的年轻slot6是CBO.zero，但旧SpecialStore沿用size3/mask0xff，只在byte0..7进入重叠域；检查器却按整line zero认为它覆盖byte12。实际StoreUnit CBO包固定size QB=4、mask0xffff；修正元数据后该first-failure条件消失。不是新增第13个Forward alias bug。',
        '必须先使用真实CBO生产者size/mask，再检查其整line语义。不能把这个错误刺激当作普通跨VA Store的别名反例。',
        source('tests/lsq_wrapper/special_owners.py', 18, 33, 'class SpecialStore', 'StoreOwner.words'),
        source('tests/lsq_wrapper/mixed_owners.py', 83, 84, 'else 3'),
        source('tests/lsq_wrapper/mixed_owners.py', 115, 119, 'cbo=cbo'),
        source('mem/pipeline/NewStoreUnit.scala', 430, 438, 'toSqAddr.size := Mux(isCbo, MemorySize.QB.U, size)'),
        source('mem/MemCommon.scala', 169, 171, 'case object QB extends Size(BitPat("b100"))'),
        source('tests/lsq_wrapper/normal_owners.py', 24, 31, 'size=4', 'mask=65535'))
    add('NOT-HEAD-CANCEL-PRODUCER', False, '用例撤销已获不可撤回许可的无异常普通Store',
        '测试令同一无异常scalar Store到ROB头、STA/STD/S2全完成并给出precommit后，又人为flushSelf并把其owner删除。已入EnterSbufferQueue的数据没有redirect撤回协议。正常分支/Load回滚不能撤销最老Store；Store自己的异常/trigger在S2阻止commit，singleStep项根本不发给IQ，含Store的ROB entry禁止IRQ。因而本用例不是合法未提交取消，也不是FIFO漏清bug；StopIteration来自actor删除了仍有副作用义务的owner。',
        '在许可前测试可取消项；已不可撤回的Store必须保留消费义务，不能重用其UID或期待FIFO消失。此裁定仅覆盖该无异常scalar反例，不把它扩大为任意vector/压缩/异常重定向定理。',
        source('vsq_cancel_capacity.py', 115, 126, 'advance_rob=False', 'head_permit', 'actor.cancel'),
        source('mem/lsqueue/VirtualStoreQueue.scala', 282, 284, 'isSameSlot(robHeadPtr)'),
        source(sq, 1995, 2007, '!ctrlEntries(ptr).hasException', '!ctrlEntries(ptr).waitStoreS2'),
        source(sq, 727, 735, 'val fromDeqModule', 'val toSbuffer'),
        source('backend/dispatch/Dispatch.scala', 594, 595, '!fromRenameUpdate(i).bits.singleStep'),
        source('mem/pipeline/NewStoreUnit.scala', 476, 478, 'hasException || isDebugMode || isBreakPoint'),
        source('backend/rename/CompressUnit.scala', 94, 96, '!CommitType.isLoadStore'),
        source('backend/rename/CompressUnit.scala', 233, 235, 'in.valid && !allow'),
        source('backend/rename/CompressUnit.scala', 296, 300, 'entryInterruptSafeByToken'),
        source('backend/rob/Rob.scala', 768, 768, 'deqPtrEntry.interruptSafe'),
        source('store_queue/actor.py', 330, 340, 'del self.live[self.all[uid].position]'))
    return roots


def read_capture(item):
    packed = (ROOT / item['path']).read_bytes()
    assert digest(packed) == item['gzip_SHA256']
    raw = gzip.decompress(packed)
    assert digest(raw) == item['raw_SHA256'] and len(raw) == item['raw_bytes']
    return json.loads(raw)


def decide(node, exc):
    if 'test_same_cycle_dispatch_redirect_' in node:
        return 'NOT-VSQ-DOMAIN'
    if 'test_multiple_mmio_selectors_' in node:
        return 'NOT-MMIO-DOMAIN'
    if 'test_real_cancel_capacity_' in node:
        return 'NOT-HEAD-CANCEL-PRODUCER'
    if 'mixed fair drain' in exc:
        return 'NOT-RAR-REPLAY-ROUTING'
    if 'test_one_global_rob_full_mixed_domain_original_obligations_and_fair_drain[28928]' in node:
        return 'NOT-CBO-SIZE-PRODUCER'
    if 'no physical producer' in exc:
        return 'FWD-RANGE-001'
    if 'newest physical' in exc:
        return 'FWD-ALIAS-001'
    if 'dataInvalid_bits_first_flag' in exc:
        return 'FWD-SQID-001'
    if 'wline' in exc:
        return 'DEQ-SPLIT-WLINE-001'
    if any(s in exc for s in ('flushSbuffer_valid', 'sbufferCtrl_req_flush', 'zero WB', 'zero Sbuffer')):
        return 'DEQ-ZERO-001'
    if any(s in exc for s in ('io_sqDeqPtr', 'io_sqDeqCnt', 'young special completion released', 'later special finish released', 'young NC/IO finish')):
        return 'DEQ-FINISH-ORDER-001'
    if any(s in exc for s in ('WB.fire', 'exceptionVec_7', 'writeback errors', 'writeBack_bits_exceptionVec',
            'io_exceptionInfo_bits_exceptionVec_19', 'io_mmioStout_bits_exceptionVec_19')) and 'load_uncache' not in node:
        return 'DEQ-WB-001'
    if 'io_uncache_req_valid' in exc:
        return 'LSQ-BUS-OWNERSHIP-001'
    if 'response.nuke' in exc or 'rarNukeQuery' in exc:
        return 'RAR-REL-001'
    if 'io_replay_0_valid' in exc:
        return 'LRQ-STRICT-001'
    if any(s in exc for s in ('s2Resp_bits_data', 'ldExceptionInfo', 'parent-cycle')):
        return 'LQU-SID-001'
    raise AssertionError(('no adjudication rule', node, exc[:300]))


def extra_proofs(extras):
    timeouts = []
    alias = []
    for item in extras:
        w = read_capture(item)
        if 'mixed fair drain' in w['original_exception']:
            rows = next(iter(w['last_public_windows'].values()))
            evidence = []
            assert all(not row['input']['redirect']['valid'] and not any(a['valid'] for a in row['input']['addresses']) for row in rows)
            for i, row in enumerate(rows):
                for lane, q in enumerate(row['input']['rar_queries']):
                    if not q['valid']:
                        continue
                    assert row['after'][f'io_ldu_rarNukeQuery_{lane}_resp_valid'] == 1
                    assert row['after'][f'io_ldu_rarNukeQuery_{lane}_resp_bits_nuke'] == 1
                    for later in rows[i + 1:]:
                        for load in later['input']['loads']:
                            req = load['execution']
                            if req['valid'] and req['uop']['rob'] == q['rob']:
                                assert req['causes'] == 1 << 11 and req['need_replay']
                                evidence.append(dict(RAR_tick=row['post_tick'], S3_tick=later['post_tick'],
                                    ROB=q['rob'], actual_RAR_valid=1, actual_RAR_nuke=1, injected_cause=2048,
                                    actual_STA_absent=True, required_flushAfter_missing=True))
            assert evidence
            timeouts.append(dict(nodeid=w['nodeid'], capture=item, directly_observed_misrouting=evidence))
        else:
            assert 'newest physical' in w['original_exception']
            answer = w['forward_public_input_ledger_for_diagnosis'][0]['stage2'][1]
            store = answer['bank'][6]
            query = answer['job']['query']
            assert store['cache_operation'] and store['cbo'] == 3 and store['size'] == 3 and store['mask'] == 255
            assert not store['cross_word'] and store['vaddr'] % 16 == 0 and query['vaddr'] % 16 == 12
            assert answer['selected'] == 61 and 6 not in answer['virtual'] and 6 not in answer['potential']
            assert store['vaddr'] // 64 == query['vaddr'] // 64
            # Exact source overlap: end=start+ByteOffset(size). Only this
            # incorrect8B CBO package misses bytes12..13; the real16B one hits.
            assert not (0 <= 13 and 7 >= 12) and (0 <= 13 and 15 >= 12)
            alias.append(dict(nodeid=w['nodeid'], capture=item, original_selected=61, purported_newest=6,
                purported_newest_public_input_ledger=store, query=query, real_CBO_size=4, real_CBO_mask=65535,
                original_overlap=False, corrected_source_overlap=True,
                note='This is diagnostic public-input bookkeeping, independently checked against actual StoreUnit Scala ABI; not a private DUT-state oracle.'))
    assert len(timeouts) == 2 and len(alias) == 1
    return dict(two_timeouts_are_verification_routing_errors=timeouts, original_random_alias_claim_is_invalid_CBO_stimulus=alias)


def scalar_counterexamples():
    # Independent byte/identity arithmetic, not calls to any LSQ reference.
    mask = 255
    rotated = ((mask >> 4) | (mask << 12)) & 65535
    assert rotated == 0xf00f
    first = sum(1 << b for b in range(16) if 12 <= b < 20)
    second = sum(1 << b for b in range(16) if 12 <= b + 16 < 20)
    assert (first, second) == (0xf000, 0xf)
    actual_dependency = 128 + 48
    correct_dependency = 60 + (48 - 60) % 64
    assert (actual_dependency, correct_dependency) == (176, 112)
    gate_rows = 0
    for red in range(2):
        for request in range(2):
            for recovery in range(2):
                for iq in range(2):
                    for alloc in range(2):
                        enq_next = request and not red and not recovery and iq and alloc
                        assert not (enq_next and red)
                        gate_rows += 1
    return dict(FWD_rotated_mask=hex(rotated), FWD_correct_masks=[hex(first), hex(second)],
        SQ_actual=actual_dependency, SQ_expected=correct_dependency, VSQ_same_source_one_cycle_gate_rows=gate_rows)


def audit():
    guard = protected()
    root = root_definitions()
    supplemental = load(OUT / 'extra-captures-index-v1.json')['cases']
    independent_details = extra_proofs(supplemental)
    algebra = scalar_counterexamples()
    index = load(OUT / 'captures-index-v1.json')['cases']
    assert len(index) == 228 and len({i['nodeid'] for i in index}) == 228
    datasets = {name: cases(name) for name in RUNS}
    fail_union = set().union(*({node for node, row in data.items() if row['outcome'] == 'FAIL'} for data in datasets.values()))
    rows = []
    for item in index:
        w = read_capture(item)
        node = w['nodeid'].replace('.py::', '::').replace('/', '.')
        assert node in fail_union and w['nodeid'] == item['nodeid']
        key = decide(node, w['original_exception'])
        definition = root[key]
        windows = w['last_public_windows']
        terminal = [records[-1] for records in windows.values() if records]
        observed = [dict(journal=name, pre_tick=records[-1].get('pre_tick'), post_tick=records[-1].get('post_tick'),
            error=records[-1].get('error'), difference_before=records[-1].get('difference_before'),
            difference_after=records[-1].get('difference_after')) for name, records in windows.items() if records]
        histories = [dict(run=name, first_failure=data[node]['detail'].splitlines()[0],
            full_failure_detail_SHA256=digest(data[node]['detail'].encode())) for name, data in datasets.items()
            if node in data and data[node]['outcome'] == 'FAIL']
        # In staged failures compare the actual contract/tick/phase, not just
        # an issue name, random seed, or coincident pin. Old stack lines differ.
        pattern = r"\('([^']+)', (\d+), '(before|after)'"
        now = re.search(pattern, w['original_exception'])
        if now:
            for history in histories:
                old = re.search(pattern, history['first_failure'])
                assert old is not None and old.groups() == now.groups(), (node, history, w['original_exception'])
        note = 'Supported module-interface defect; full-core/ISA consequence is not the decision criterion.'
        if 'test_seeded_in_window_nonalias_concurrent_byte_queries' in node:
            note = ('Original arbitrary-hole mask is interface stress, not a real PSQ mask. Its erroneous wrapped byte remains set if the mask is replaced by the legal continuous size mask: candidate selection does not depend on byteMask. The legal8B directed cases establish the SAME RTL range defect; this case is not counted as a separate bug or as normal-source history.')
        if not definition['is_RTL_bug']:
            note = definition['root_cause']
        rows.append(dict(nodeid=node, verdict=definition['verdict'], is_RTL_bug=definition['is_RTL_bug'],
            root_id=key, error_description=definition['title'], source_root_cause=definition['root_cause'],
            original_results=histories, concrete_failure_capture=item,
            captured_actual_first_exception=w['original_exception'], public_failure_edge=observed,
            domain_and_decision_scope=note))
    assert {r['nodeid'] for r in rows} == fail_union
    counts = Counter(r['root_id'] for r in rows)
    expected = {'DEQ-WB-001': 50, 'DEQ-ZERO-001': 15, 'DEQ-FINISH-ORDER-001': 20,
        'LQU-SID-001': 29, 'LSQ-BUS-OWNERSHIP-001': 6, 'LRQ-STRICT-001': 11,
        'FWD-RANGE-001': 28, 'FWD-ALIAS-001': 12, 'DEQ-SPLIT-WLINE-001': 16,
        'FWD-SQID-001': 15, 'RAR-REL-001': 19, 'NOT-VSQ-DOMAIN': 2, 'NOT-MMIO-DOMAIN': 1,
        'NOT-HEAD-CANCEL-PRODUCER': 1, 'NOT-RAR-REPLAY-ROUTING': 2, 'NOT-CBO-SIZE-PRODUCER': 1}
    assert counts == expected, counts
    for key, value in root.items():
        value['failed_node_count'] = counts[key]
        value['nodeids'] = sorted(r['nodeid'] for r in rows if r['root_id'] == key)
    summary = dict(unique_failed_nodes=228, adjudicated=228, unclassified=0,
        RTL_bug_nodes=sum(r['is_RTL_bug'] for r in rows), not_RTL_bug_nodes=sum(not r['is_RTL_bug'] for r in rows),
        distinct_RTL_roots=sum(value['is_RTL_bug'] for value in root.values()), per_root=dict(counts), per_run={})
    for name, data in datasets.items():
        nodes = [r for r in rows if any(h['run'] == name for h in r['original_results'])]
        summary['per_run'][name] = dict(total_nodes=len(data), frozen_failures=len(nodes),
            RTL_bug_nodes=sum(r['is_RTL_bug'] for r in nodes), not_RTL_bug_nodes=sum(not r['is_RTL_bug'] for r in nodes),
            frozen_failure_SHA256=failure_digest(data))
    assert summary['RTL_bug_nodes'] == 221 and summary['not_RTL_bug_nodes'] == 7
    independent = load(ROOT / 'results/fail-review-baseline-01/first-batch-review-v1.json')
    supplemental_failures = []
    independent_count = 0
    for family in independent['roots']:
        key = family['issue']
        assert key in root and root[key]['is_RTL_bug']
        for item in family['independent_reproduction']['rows']:
            independent_count += 1
            assert digest((ROOT / item['path']).read_bytes()) == item['SHA256']
            if item['verdict'] == 'FAIL':
                node = item['nodeid'].replace('.py::', '::').replace('/', '.')
                assert node not in fail_union
                supplemental_failures.append(dict(nodeid=node, verdict='是RTL bug', is_RTL_bug=True,
                    root_id=key, error_description=root[key]['title'], witness=item['path'],
                    witness_SHA256=item['SHA256'], source_root_cause=root[key]['root_cause']))
    assert independent_count == 32 and len(supplemental_failures) == 10
    summary['additional_independent_probes'] = dict(total_nodes=32, current_FAIL=10, current_PASS=22,
        current_FAILs_all_linked_to_the_same_four_confirmed_RTL_roots=True)
    summary['including_additional_independent_failed_nodes'] = dict(total=238, RTL_bug_nodes=231, not_RTL_bug_nodes=7,
        distinct_RTL_roots=11, unclassified=0)
    assert protected() == guard
    report = dict(format='lsq-all-fail-binary-source-verdicts-v1', fixed_commit=COMMIT, summary=summary,
        definition='Binary RTL-defect adjudication in the supported module interface. Not an ISA failure count, not a claim that each legacy producer field was upstream legal, and not a regression pass/coverage signoff.',
        roots=root, failed_nodes=sorted(rows, key=lambda r: r['nodeid']), independent_source_discriminators=independent_details,
        supplemental_current_independent_failed_nodes=sorted(supplemental_failures, key=lambda r: r['nodeid']),
        independent_scalar_counterexamples=algebra, preservation=guard,
        capture_receipts=dict(first_run='fail-source-reproduction-01', first_run_exit=3,
            first_run_note='A new passive formatter could not XOR structured RAR list responses. This run is INCOMPLETE, never a completed-native-regression receipt.175completed bounded first-failure captures are source-diagnostic evidence only.',
            continuation_run='fail-source-reproduction-02', continuation_nodes=53,
            no_first_failure_dropped=True, all_228_have_bounded_failure_capture=True,
            supplemental_runs=['fail-source-timeout-cause-01', 'fail-source-alias-cause-01'],
            scope='Only missing causal facts, not full regressions. No coverage denominator/numerator is combined or backfilled.'),
        supersedes='The partial first-batch candidate inventory, especially the three incorrectly nominated Deq mixed seeds and the unclassified63mixed/head nodes. Old reports and failures remain unmodified.',
        original_failure_outcomes_unchanged=True, RTL_or_reference_fix_applied=False,
        no_skip_xfail_suppression=True, no_unknown_verdict_or_unreviewed_fail=True)
    write_report(OUT / 'all-fail-verdicts-v1.json', report)
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['scope', 'nodeid', 'is_RTL_bug', 'verdict', 'root_id', 'error_description', 'evidence'])
    for row in sorted(rows, key=lambda r: r['nodeid']):
        writer.writerow(['frozen_regression_union', row['nodeid'], str(row['is_RTL_bug']).lower(), row['verdict'],
            row['root_id'], row['error_description'], row['concrete_failure_capture']['path']])
    for row in sorted(supplemental_failures, key=lambda r: r['nodeid']):
        writer.writerow(['supplemental_independent_probe', row['nodeid'], 'true', row['verdict'],
            row['root_id'], row['error_description'], row['witness']])
    path = OUT / 'all-fail-verdicts-v1.csv'
    raw = stream.getvalue().encode('utf-8-sig')
    if path.exists():
        assert path.read_bytes() == raw, 'Do not silently overwrite an existing decision CSV'
    else:
        with path.open('xb') as f:
            f.write(raw)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    audit()
