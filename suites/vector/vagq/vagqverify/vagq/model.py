"""Externally observable VAGQ public-contract model.

The model composes vector-window and address semantics, then tracks only the
top-level lifecycle visible at the VAGQIO boundary.  It does not copy the
generated entry-table or child RTL state machines.  ISA-oriented claims are
kept separate in ``vagq.isa_reference`` and ``docs/vagq-isa-audit.md``.
"""
from dataclasses import dataclass, field

from vagqverify.addrgen.reference import AddressContext, IndexedAddress, StridedAddress, address
from vagqverify.maskgen.reference import MaskRequest, evaluate_protocol

from .probe import output, valid
from .types import AddrPacket, Beat, DataPacket


FLOW_BYTES = 16
ALL_BYTES = (1 << FLOW_BYTES) - 1


def _u64_signed(value):
    value &= (1 << 64) - 1
    return value - (1 << 64) if value & (1 << 63) else value


def _onehot(value):
    return value != 0 and value & (value - 1) == 0


def _data_size(data_width):
    # A request size must CONTAIN its enabled bytes (ceil, not floor), and
    # the public dataMask holds at most one 16-byte request.
    width = min(FLOW_BYTES, max(1, data_width))
    return (width - 1).bit_length()


def _index_values(data, ieew):
    width = 1 << ieew
    count = 128 // (width * 8)
    return tuple((data >> (i * width * 8)) & ((1 << (width * 8)) - 1)
                  for i in range(count))


def _slot_element(addr, info, site):
    if site < info['startByteOffset']:
        raise ValueError('selected site precedes the first MOP')
    if addr.nf == 6 and addr.deew == 0 and addr.ieew == 2:
        # Physical special-layout stride; memory/request width remains seven.
        return info['elemBase'] + ((site - info['startByteOffset']) >> addr.ieew)
    data_width = (addr.nf + 1) << addr.deew
    relative = site - info['startByteOffset'] + (info['startFieldOffset'] << addr.deew)
    return info['elemBase'] + relative // data_width


@dataclass(slots=True)
class Plan:
    addr: AddrPacket
    data: DataPacket
    info: dict
    active: dict[int, dict]
    empty: set[int]
    emitted_active: set[int] = field(default_factory=set)
    emitted_empty: set[int] = field(default_factory=set)
    acknowledged: int = 0
    exception: bool = False
    exception_number: int = 0
    fault_elem_idx: int = 0
    data_seen: bool = False
    writeback_seen: bool = False
    flushed: bool = False

    @property
    def is_load(self):
        return (self.addr.uop_type & 1) == 0

    @property
    def valid_mask(self):
        return self.info['elemValidMask'] & ALL_BYTES

    @property
    def complete(self):
        return self.acknowledged & self.valid_mask == self.valid_mask and (
            self.is_load or self.data_seen
        )

    @property
    def outstanding(self):
        return self.valid_mask & ~self.acknowledged


class IntegrationModel:
    def __init__(self):
        self.plans: dict[int, Plan] = {}
        self.previous_blocked: dict[tuple[str, int], tuple] = {}
        self.events = []

    @staticmethod
    def _mask_info(addr: AddrPacket):
        # Allocation slots are deliberately separate from architectural VLMAX.
        # Fractional padding must be acknowledged via empty markers, not LSU.
        return evaluate_protocol(MaskRequest(
            v0_mask=addr.v0_byte_mask,
            deew=addr.deew,
            ieew=addr.ieew,
            emul=addr.emul,
            vl=addr.vl,
            vstart=addr.vstart,
            vma=addr.vma,
            vta=addr.vta,
            uop_idx=addr.uop_idx,
            nf=addr.nf,
        ))

    @staticmethod
    def _address(
        addr: AddrPacket, data: DataPacket, elem_idx: int, *, first_field=0,
    ):
        context = AddressContext(
            base=addr.base_addr,
            element=elem_idx,
            offset=0,
            data_bytes=1 << addr.deew,
            # AddrGen applies the starting field only to the first element
            # of a MOP.  A later element starts at field zero again.
            first_field=first_field,
        )
        if addr.uop_type >= 4:
            return address(IndexedAddress(
                context,
                _index_values(data.op2_data, addr.ieew),
            ))
        return address(StridedAddress(context, _u64_signed(data.op2_data)))

    @classmethod
    def make_plan(cls, addr: AddrPacket, data: DataPacket):
        info = cls._mask_info(addr)
        active_mask = info['elemActiveMask'] & ALL_BYTES
        valid_mask = info['elemValidMask'] & ALL_BYTES
        empty_mask = valid_mask & ~active_mask & ALL_BYTES
        data_width = (addr.nf + 1) * (1 << addr.deew)
        full_data_mask = ALL_BYTES if data_width >= FLOW_BYTES else (
            (1 << data_width) - 1
        )
        active = {}
        first_elem = info['elemBase']
        for site in range(FLOW_BYTES):
            if not active_mask & (1 << site):
                continue
            elem_idx = _slot_element(addr, info, site)
            # byteOffset identifies the placement; dataMask describes the
            # width at byte zero for the LSU, so it is not shifted.
            data_mask = full_data_mask
            request_width = data_width
            # When a wide segment MOP begins at a later field, the first
            # request contains only the remaining fields of that element.
            # SplitCtrl uses site==0 as the corresponding first-MOP marker.
            if addr.nf and info['startFieldOffset'] and site == 0:
                remaining_width = (
                    (addr.nf + 1 - info['startFieldOffset']) << addr.deew
                )
                data_mask = ALL_BYTES if remaining_width >= FLOW_BYTES else (
                    (1 << remaining_width) - 1
                )
                request_width = remaining_width
            first_field = info['startFieldOffset'] if elem_idx == first_elem else 0
            active[site] = {
                'entry_idx': addr.entry_idx,
                'rob_flag': addr.rob_flag,
                'rob_value': addr.rob_value,
                'byte_offset': site,
                'elem_idx': elem_idx,
                'data_mask': data_mask,
                'data_size': _data_size(request_width),
                'vaddr': cls._address(
                    addr, data, elem_idx, first_field=first_field,
                ),
                'is_load': (addr.uop_type & 1) == 0,
            }
        return Plan(addr, data, info, active, {
            site for site in range(FLOW_BYTES) if empty_mask & (1 << site)
        })

    def admit(self, addr: AddrPacket, data: DataPacket):
        if (addr.entry_idx, addr.rob_flag, addr.rob_value) != (
            data.entry_idx, data.rob_flag, data.rob_value
        ):
            raise AssertionError('address/data admission ownership does not match')
        if addr.entry_idx in self.plans and not self.plans[addr.entry_idx].flushed:
            raise AssertionError(f'entry {addr.entry_idx} admitted twice')
        self.plans[addr.entry_idx] = self.make_plan(addr, data)

    def _plan_for(self, entry_idx):
        plan = self.plans.get(entry_idx)
        if plan is None:
            raise AssertionError(f'output references unknown VAGQ entry {entry_idx}')
        if plan.flushed:
            raise AssertionError(f'flushed entry {entry_idx} produced output')
        return plan

    def _check_native_hold(self, outputs, key, signature, blocked):
        previous = self.previous_blocked.get(key)
        if previous is not None and blocked and previous != signature:
            raise AssertionError(f'blocked {key} payload changed')
        if blocked:
            self.previous_blocked[key] = signature
        else:
            self.previous_blocked.pop(key, None)

    def _response_updates(self, beat: Beat):
        for response in beat.ldu_resp + beat.sta_resp:
            if not response.valid:
                continue
            plan = self._plan_for(response.entry_idx)
            if response.issue_mask & ~plan.valid_mask:
                raise AssertionError('LSU response acknowledges a non-window byte')
            if response.is_nack and not response.exception:
                for site in range(FLOW_BYTES):
                    if response.issue_mask & (1 << site):
                        plan.emitted_active.discard(site)
                        plan.emitted_empty.discard(site)
            else:
                plan.acknowledged |= response.issue_mask
            if response.exception:
                plan.exception = True
                if not plan.exception_number or response.fault_elem_idx < plan.fault_elem_idx:
                    plan.exception_number = response.exception_number
                    plan.fault_elem_idx = response.fault_elem_idx
        for response in beat.empty_resp:
            if not response.valid:
                continue
            plan = self._plan_for(response.entry_idx)
            if response.issue_mask & ~plan.valid_mask:
                raise AssertionError('empty response acknowledges a non-window byte')
            if response.is_nack:
                for site in range(FLOW_BYTES):
                    if response.issue_mask & (1 << site):
                        plan.emitted_empty.discard(site)
            else:
                plan.acknowledged |= response.issue_mask

    def _active_event(self, outputs, beat, group, lane):
        prefix = f'io_{group}_{lane}_'
        if not valid(outputs, prefix + 'valid'):
            return None
        if not valid(outputs, prefix + 'bits_meta_valid'):
            # Native issue output is outside this integration plan; its own
            # public payload is checked by the native-issue scenario.
            return None
        entry_idx = output(outputs, prefix + 'bits_meta_entryIdx')
        plan = self._plan_for(entry_idx)
        site = output(outputs, prefix + 'bits_meta_byteOffset')
        if site not in plan.active:
            raise AssertionError(f'{group}[{lane}] selected non-active byte {site}')
        expected = plan.active[site]
        is_load = group == 'lduReq'
        if expected['is_load'] != is_load:
            raise AssertionError(f'{group}[{lane}] changed load/store class')
        checks = {
            'bits_meta_elemIdx': expected['elem_idx'],
            'bits_meta_dataMask': expected['data_mask'],
            'bits_meta_dataSize': expected['data_size'],
            'bits_req_robIdx_flag': expected['rob_flag'],
            'bits_req_robIdx_value': expected['rob_value'],
            'bits_req_data_src_0': expected['vaddr'],
            'bits_req_ctrl_isRVC': 0,
            'bits_req_ctrl_ftqIdx_flag': plan.addr.ftq_flag,
            'bits_req_ctrl_ftqIdx_value': plan.addr.ftq_value,
            'bits_req_ctrl_ftqOffset': plan.addr.ftq_offset,
            'bits_req_lqIdx_flag': plan.addr.lq_flag,
            'bits_req_lqIdx_value': plan.addr.lq_value + (
                expected['elem_idx'] - plan.info['elemBase'] if is_load else 0
            ),
            'bits_req_sqIdx_first_flag': plan.addr.sq_first_flag,
            'bits_req_sqIdx_second_flag': plan.addr.sq_second_flag,
            'bits_req_sqIdx_value': plan.addr.sq_value + (
                expected['elem_idx'] - plan.info['elemBase'] if not is_load else 0
            ),
        }
        if is_load:
            checks['bits_req_ctrl_vecWen'] = 1
            checks['bits_req_toRF_pdest'] = plan.addr.pdest
        for suffix, expected_value in checks.items():
            actual = output(outputs, prefix + suffix)
            if actual != expected_value:
                raise AssertionError(
                    f'{prefix}{suffix}: expected {expected_value}, got {actual}'
                )
        target_ready = beat.ldu_ready[lane] if is_load else beat.sta_ready[lane]
        signature = tuple(output(outputs, prefix + suffix) for suffix in (
            'bits_meta_entryIdx', 'bits_meta_byteOffset', 'bits_meta_elemIdx',
            'bits_meta_dataMask', 'bits_req_data_src_0', 'bits_req_robIdx_value'))
        self._check_native_hold(outputs, (group, lane), signature, not target_ready)
        if target_ready:
            if site in plan.emitted_active:
                raise AssertionError(f'{group}[{lane}] duplicated fired byte {site}')
            plan.emitted_active.add(site)
        return expected

    def _empty_event(self, outputs, beat, lane):
        prefix = f'io_lsqEmptyReq_{lane}_'
        if not valid(outputs, prefix + 'valid'):
            return None
        entry_idx = output(outputs, prefix + 'bits_entryIdx')
        plan = self._plan_for(entry_idx)
        issue_mask = output(outputs, prefix + 'bits_issueMask')
        if not _onehot(issue_mask) or issue_mask & ~sum(1 << site for site in plan.empty):
            raise AssertionError('empty request must select one unused allocated slot')
        checks = {
            'bits_robIdx_flag': plan.addr.rob_flag,
            'bits_robIdx_value': plan.addr.rob_value,
            'bits_isLoad': int(plan.is_load),
        }
        site = issue_mask.bit_length() - 1
        offset = _slot_element(plan.addr, plan.info, site) - plan.info['elemBase']
        if plan.is_load:
            # The empty-marker public schema has no LQ flag leaf.
            checks['bits_lqIdx_value'] = (plan.addr.lq_value + offset) & 0x7f
        else:
            checks['bits_sqIdx_value'] = (plan.addr.sq_value + offset) & 0x3f
        for suffix, expected_value in checks.items():
            if output(outputs, prefix + suffix) != expected_value:
                raise AssertionError(f'empty request {suffix} disagrees with allocated slot owner/index')
        target_ready = beat.empty_ready[lane]
        signature = (entry_idx, issue_mask, output(outputs, prefix + 'bits_robIdx_value'))
        self._check_native_hold(outputs, ('empty', lane), signature, not target_ready)
        if target_ready:
            for site in range(FLOW_BYTES):
                if issue_mask & (1 << site):
                    if site in plan.emitted_empty:
                        raise AssertionError(f'empty byte {site} emitted twice')
                    plan.emitted_empty.add(site)
        return issue_mask

    def validate(self, outputs, beat: Beat):
        self._response_updates(beat)
        active = []
        empty = []
        for lane in range(3):
            event = self._active_event(outputs, beat, 'lduReq', lane)
            if event is not None:
                active.append(event)
        for lane in range(2):
            event = self._active_event(outputs, beat, 'staReq', lane)
            if event is not None:
                active.append(event)
            issue_mask = self._empty_event(outputs, beat, lane)
            if issue_mask is not None:
                empty.append(issue_mask)

        for lane in range(2):
            prefix = f'io_vagqStdData_{lane}_'
            if valid(outputs, prefix + 'valid'):
                matching = [plan for plan in self.plans.values()
                            if not plan.flushed and not plan.is_load]
                if not matching:
                    raise AssertionError('STD output without a live store plan')
                plan = matching[0]
                plan.data_seen = True
                sq_value = output(outputs, prefix + 'bits_sqIdx_value')
                max_offset = max(plan.active, default=0)
                if not plan.active or not plan.addr.sq_value <= sq_value <= plan.addr.sq_value + max_offset:
                    raise AssertionError('STD output SQ pointer left the entry flow window')

        if valid(outputs, 'io_vrfReadReq_valid'):
            entry_idx = output(outputs, 'io_vrfReadReq_bits_entryIdx')
            plan = self._plan_for(entry_idx)
            if plan.is_load and not plan.info.get('mergeWriteMask', 0):
                raise AssertionError('load without an old-vd merge mask requested VRF data')
            if output(outputs, 'io_vrfReadReq_bits_robIdx_value') != plan.addr.rob_value:
                raise AssertionError('VRF read selected the wrong ROB owner')

        if valid(outputs, 'io_vrfWriteReq_valid'):
            entry_idx = output(outputs, 'io_vrfWriteReq_bits_entryIdx')
            plan = self._plan_for(entry_idx)
            if output(outputs, 'io_vrfWriteReq_bits_pdest') != plan.addr.pdest:
                raise AssertionError('VRF write selected the wrong destination')
            if plan.is_load and output(outputs, 'io_vrfWriteReq_bits_mask') != plan.info.get('mergeWriteMask', 0):
                raise AssertionError('VRF write mask disagrees with vector merge window')

        for plan in self.plans.values():
            if plan.flushed:
                continue
            prefix = 'io_robWriteback_'
            if valid(outputs, prefix + 'valid'):
                if output(outputs, prefix + 'bits_entryIdx') != plan.addr.entry_idx:
                    raise AssertionError('ROB writeback selected the wrong entry')
                if output(outputs, prefix + 'bits_robIdx_value') != plan.addr.rob_value:
                    raise AssertionError('ROB writeback selected the wrong ROB age')
                if not plan.complete:
                    raise AssertionError('ROB writeback occurred before all required work completed')
                if output(outputs, prefix + 'bits_exception') != int(plan.exception):
                    raise AssertionError('ROB writeback exception bit disagrees with response history')
                plan.writeback_seen = True
                if plan.is_load and not plan.exception:
                    if not valid(outputs, 'io_vpWakeUp_valid'):
                        raise AssertionError('successful load writeback did not wake its destination')
                    if output(outputs, 'io_vpWakeUp_bits') != plan.addr.pdest:
                        raise AssertionError('load wakeup selected the wrong destination')
                elif valid(outputs, 'io_vpWakeUp_valid'):
                    raise AssertionError('store/exception writeback produced a wakeup')

        if beat.redirect.valid:
            for plan in self.plans.values():
                younger = plan.addr.rob_value > beat.redirect.rob_value
                if younger or (
                    beat.redirect.level and
                    plan.addr.rob_value == beat.redirect.rob_value
                ):
                    plan.flushed = True
        return active, empty
