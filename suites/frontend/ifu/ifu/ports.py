"""Exact80-input/405-output contract. All encodings and units are private here."""
from toffee import Bundle

from suites.frontend.ifu.model.perf import FTQ_BITS

from .types import BusRequest, Enqueue, Frame, GpaWrite, Interface, Redirect, Snapshot


def encode(frame):
    if not isinstance(frame, Frame):
        raise TypeError('IFU requires a semantic Frame')
    r, t = frame.reasons, frame.trigger
    update, trigger = t.update, t.update.trigger
    values = dict(reset=frame.reset, io_fromICache_req_valid=int(frame.request is not None),
        io_toIBuffer_ready=frame.ibuffer_ready, io_backendEmpty=frame.backend_empty,
        io_ibufferEmpty=frame.ibuffer_empty, io_fromFtq_redirect_valid=frame.backend_redirect,
        io_fromFtq_flushFromBpu_s3_valid=int(frame.bpu_flush is not None),
        io_fromFtq_flushFromBpu_s3_bits_flag=(frame.bpu_flush or (0, 0))[0],
        io_fromFtq_flushFromBpu_s3_bits_value=(frame.bpu_flush or (0, 0))[1],
        io_csrFsIsOff=frame.fs_is_off, io_toUncache_req_ready=frame.uncache_ready,
        io_fromUncache_resp_valid=int(frame.reply is not None),
        io_fromUncache_resp_bits_data=frame.reply.data if frame.reply else 0,
        io_fromUncache_resp_bits_corrupt=frame.reply.corrupt if frame.reply else 0,
        io_fromUncache_resp_bits_denied=frame.reply.denied if frame.reply else 0,
        io_fromUncache_resp_bits_needResend=frame.reply.need_resend if frame.reply else 0,
        io_frontendTrigger_tUpdate_valid=update.valid, io_frontendTrigger_tUpdate_bits_addr=update.index,
        io_frontendTrigger_tUpdate_bits_tdata_matchType=trigger.match_type if trigger else 0,
        io_frontendTrigger_tUpdate_bits_tdata_select=trigger.select if trigger else 0,
        io_frontendTrigger_tUpdate_bits_tdata_action=trigger.action if trigger else 0,
        io_frontendTrigger_tUpdate_bits_tdata_chain=trigger.chain if trigger else 0,
        io_frontendTrigger_tUpdate_bits_tdata_tdata2=trigger.tdata2 if trigger else 0,
        io_frontendTrigger_debugMode=t.debug_mode,
        io_frontendTrigger_triggerCanRaiseBpExp=t.can_raise_breakpoint,
        io_fromICache_topdown_iCacheMissBubble=r.icache_miss,
        io_fromICache_topdown_itlbMissBubble=r.itlb_miss,
        io_fromICache_perf_isDoubleLine=frame.double_line)
    values.update((f'io_frontendTrigger_tEnableVec_{i}', t.enable[i]) for i in range(4))
    values.update((f'io_fromICache_corrupt_{i // 2}_{i % 2}', value) for i, value in enumerate(frame.corruption))
    values.update((f'io_fromICache_perf_hits_{i}', value) for i, value in enumerate(frame.cache_hits))
    values.update((f'io_fromFtq_topdownInfo_reasons_{bit}', (r.ftq_bits >> bit) & 1) for bit in FTQ_BITS)
    for field, suffix in [('backend_redirect', 'backendRedirect'), ('control_flow_redirect', 'controlFlowRedirect'),
            ('memory_violation_redirect', 'memoryViolationRedirect'), ('tage_miss', 'tageMissBubble'),
            ('ittage_miss', 'ittageMissBubble'), ('ras_miss', 'rasMissBubble')]:
        values['io_backendRedirectTopdown_' + suffix] = getattr(r, field)
    w = frame.request.window if frame.request else None
    values['io_fromICache_req_bits_firstRange'] = (1 << w.size0) - 1 if w else 0
    values['io_fromICache_req_bits_totalRange'] = (1 << (w.size0 + w.size1)) - 1 if w else 0
    values['io_fromICache_req_bits_maybeRvcMap'] = w.map if w else 0
    for block in range(2):
        prefix = f'io_fromICache_req_bits_info_{block}_'
        size = (w.size0 if block == 0 else w.size1) if w else 0
        start = (w.start0_pc if block == 0 else w.start1_pc) if w else 0
        # The inactive block has no address contract. Encode a fixed zero, not
        # silent native truncation of a speculative out-of-range successor PC.
        active = w is not None and (block == 0 or w.block1_valid)
        values[prefix + 'startVAddr_addr'] = (start >> 1) if active else 0
        values[prefix + 'size'] = size
        ptr = (w.ftq0 if block == 0 else w.ftq1) if w else (0, 0)
        values[prefix + 'ftqIdx_flag'], values[prefix + 'ftqIdx_value'] = ptr
        values[prefix + 'takenCfiOffset_valid'] = (w.taken0_valid if block == 0 else w.taken1_valid) if w else 0
        values[prefix + 'takenCfiOffset_bits'] = max(0, size - 1)
        values[prefix + 'data'] = sum(half << (16 * i) for i, half in enumerate(w.line0 if block == 0 else w.line1)) if w else 0
        values[prefix + 'icacheMeta_exception_value'] = (w.exc0 if block == 0 else w.exc1) if w else 0
        values[prefix + 'icacheMeta_gpAddr_addr'] = ((w.gp0 if block == 0 else w.gp1) >> 1) if w else 0
        values[prefix + 'icacheMeta_isForVSnonLeafPTE'] = (w.vs0 if block == 0 else w.vs1) if w else 0
        if block:
            values[prefix + 'valid'] = w.block1_valid if w else 0
        else:
            for suffix, field in [('pmpMmio', 'pmp0'), ('itlbPbmt', 'pbmt0'), ('hasSatpFlush', 'satp0'),
                                  ('isBackendException', 'backend_exc0')]:
                values[prefix + 'icacheMeta_' + suffix] = getattr(w, field) if w else 0
            values[prefix + 'icacheMeta_pAddr_addr'] = frame.request.physical_address >> 1 if w else 0
    return values


INPUT_WIDTHS = {name: 1 for name in encode(Frame())}
INPUT_WIDTHS.update(io_fromFtq_flushFromBpu_s3_bits_value=6,
    io_fromICache_req_bits_firstRange=32, io_fromICache_req_bits_totalRange=32,
    io_fromICache_req_bits_maybeRvcMap=32, io_fromUncache_resp_bits_data=32,
    io_frontendTrigger_tUpdate_bits_addr=2, io_frontendTrigger_tUpdate_bits_tdata_matchType=2,
    io_frontendTrigger_tUpdate_bits_tdata_action=4, io_frontendTrigger_tUpdate_bits_tdata_tdata2=64)
for _block in range(2):
    _prefix = f'io_fromICache_req_bits_info_{_block}_'
    for _field, _width in [('data', 512), ('size', 6), ('startVAddr_addr', 50), ('ftqIdx_value', 6),
            ('takenCfiOffset_bits', 5), ('icacheMeta_exception_value', 3), ('icacheMeta_gpAddr_addr', 55)]:
        INPUT_WIDTHS[_prefix + _field] = _width
INPUT_WIDTHS['io_fromICache_req_bits_info_0_icacheMeta_pAddr_addr'] = 47
INPUT_WIDTHS['io_fromICache_req_bits_info_0_icacheMeta_itlbPbmt'] = 2

LANES = {'instrs': ('instrs_{}', 32), 'is_rvc': ('isRvc_{}', 1), 'foldpc': ('foldpc_{}', 10),
    'ftq_flag': ('ftqPtr_{}_flag', 1), 'ftq_value': ('ftqPtr_{}_value', 6),
    'end_off': ('instrEndOffset_{}_offset', 5), 'pred': ('instrEndOffset_{}_predTaken', 1),
    'triggered': ('triggered_{}', 4)}
BEAT = {'valid': ('valid', 36), 'enq': ('enqEnable', 36), 'prev_count': ('prevInstrCount', 6),
    'exception_type': ('exceptionType_value', 3), 'exception_mask': ('exceptionMask', 36),
    'exception_cross': ('exceptionCrossPage', 1), 'is_backend_exception': ('isBackendException', 1),
    'has_satp_flush': ('hasSatpFlush', 1)}
REDIRECT = {'ftq_flag': ('ftqIdx_flag', 1), 'ftq_value': ('ftqIdx_value', 6), 'can_train': ('canTrain', 1),
    'pc': ('pc', 50), 'taken': ('taken', 1), 'offset': ('ftqOffset', 5), 'is_rvc': ('isRVC', 1),
    'branch_type': ('attribute_branchType', 2), 'ras_action': ('attribute_rasAction', 2), 'target': ('target', 51)}


class IfuPorts:
    def __init__(self, dut):
        def bind(name, width, output=False):
            signal = getattr(dut, name)
            if max(1, int(signal.mWidth)) != width:
                raise ValueError(f'{name}: expected native width{width}, got {signal.mWidth}')
            if ((output and not signal.IsOutIO()) or
                    (not output and (not signal.IsInIO() or signal.IsOutIO()))):
                raise ValueError(f'{name}: wrong native port direction')
            return signal

        self.bits = Bundle(**{name: bind(name, width) for name, width in INPUT_WIDTHS.items()})
        bind('clock', 1)
        widths = {'io_fromICache_req_ready': 1, 'io_toIBuffer_valid': 1, 'io_toFtq_wbRedirect_valid': 1,
            'io_toUncache_req_valid': 1, 'io_toUncache_req_bits_addr_addr': 47,
            'io_toUncache_req_bits_memBackTypeMM': 1, 'io_toUncache_req_bits_memPageTypeNC': 1,
            'io_toBackend_gpAddrMem_wen': 1, 'io_toBackend_gpAddrMem_waddr': 6,
            'io_toBackend_gpAddrMem_wdata_gpaddr': 56, 'io_toBackend_gpAddrMem_wdata_isForVSnonLeafPTE': 1}
        widths.update((f'io_toIBuffer_bits_{suffix}', width) for suffix, width in BEAT.values())
        widths.update((f'io_toIBuffer_bits_{pattern.format(i)}', width)
            for key, (pattern, width) in LANES.items() for i in range(35 if key == 'pred' else 36))
        widths.update((f'io_toFtq_wbRedirect_bits_{suffix}', width) for suffix, width in REDIRECT.values())
        widths.update((f'io_toIBuffer_bits_topdownInfo_reasons_{i}', 1) for i in range(76))
        widths.update((f'io_perf_{i}_value', 6) for i in range(13))
        self._outputs = Bundle(**{name: bind(name, width, True) for name, width in widths.items()})
        self.input_count, self.output_count = len(INPUT_WIDTHS), len(widths)
        self.interface = Interface(input_count=self.input_count, output_count=self.output_count)
        if hasattr(dut, 'io_toIBuffer_bits_instrEndOffset_35_predTaken'):
            raise ValueError('proven pruned lane35 predTaken=0 now exists; migrate explicitly')
        actual_in, actual_out = set(), set()
        for name, signal in vars(dut).items():
            if name == 'dut' or not callable(getattr(signal, 'IsInIO', None)):
                continue
            if signal.IsOutIO():
                actual_out.add(name)
            elif signal.IsInIO() and name != 'clock':
                actual_in.add(name)
        if actual_in != set(INPUT_WIDTHS) or actual_out != set(widths):
            raise ValueError(f'IFU port set changed: inputs{actual_in ^ set(INPUT_WIDTHS)}, outputs{actual_out ^ set(widths)}')

    encode = staticmethod(encode)

    def capture(self, event):
        values = {name: int(value) for name, value in self._outputs.sample().items()}
        beat = redirect = bus = gpa = None
        if values['io_toIBuffer_valid']:
            fields = {key: values['io_toIBuffer_bits_' + suffix] for key, (suffix, _) in BEAT.items()}
            fields.update((key, tuple(values['io_toIBuffer_bits_' + pattern.format(i)]
                for i in range(35 if key == 'pred' else 36))) for key, (pattern, _) in LANES.items())
            fields['pred'] += (0,)
            fields['ftq'] = tuple(zip(fields.pop('ftq_flag'), fields.pop('ftq_value')))
            beat = Enqueue(**fields)
        if values['io_toFtq_wbRedirect_valid']:
            fields = {key: values['io_toFtq_wbRedirect_bits_' + suffix] for key, (suffix, _) in REDIRECT.items()}
            fields['ftq'] = (fields.pop('ftq_flag'), fields.pop('ftq_value'))
            redirect = Redirect(**fields)
        if values['io_toUncache_req_valid']:
            bus = BusRequest(values['io_toUncache_req_bits_addr_addr'] << 1,
                values['io_toUncache_req_bits_memBackTypeMM'], values['io_toUncache_req_bits_memPageTypeNC'])
        if values['io_toBackend_gpAddrMem_wen']:
            gpa = GpaWrite(values['io_toBackend_gpAddrMem_waddr'], values['io_toBackend_gpAddrMem_wdata_gpaddr'],
                           values['io_toBackend_gpAddrMem_wdata_isForVSnonLeafPTE'])
        return Snapshot(values['io_fromICache_req_ready'], beat, redirect, bus, gpa,
            sum(values[f'io_toIBuffer_bits_topdownInfo_reasons_{i}'] << i for i in range(76)),
            tuple(values[f'io_perf_{i}_value'] for i in range(13)))
