"""Integration and public-boundary verification coverage.

The original ``Coverage.group`` is the stable 48-bin VAGQ contract.  The
additional groups below are deliberately separate metrics: handshake
combinations, abstract public lifecycle stages/transitions, and boundary value
classes are not silently folded into that contract score.
"""
from toffee import Bin, CoverGroupDef, CoverPointDef

from .isa_reference import vlmax


_HANDSHAKE_STATES = ('v0r0', 'v0r1', 'v1r0', 'v1r1')
_LIFECYCLE_STATES = (
    'empty', 'allocated', 'request', 'blocked', 'retry', 'acknowledged',
    'writeback', 'flushed',
)
_LIFECYCLE_TRANSITIONS = (
    'empty->allocated',
    'allocated->request', 'allocated->blocked', 'allocated->acknowledged',
    'allocated->writeback', 'allocated->flushed',
    'request->blocked', 'request->acknowledged', 'request->retry',
    'request->writeback', 'request->flushed',
    'blocked->request', 'blocked->acknowledged', 'blocked->retry',
    'blocked->writeback', 'blocked->flushed',
    'retry->request', 'retry->blocked', 'retry->acknowledged',
    'retry->writeback', 'retry->flushed',
    'acknowledged->writeback', 'acknowledged->flushed',
    'other',
)
_VALUE_BINS = {
    'vl': ('none', 'zero', 'one', 'middle', 'max'),
    'vstart': ('none', 'zero', 'middle', 'ge-vl'),
    'mask': ('none', 'zero', 'one-hot', 'multi-bit', 'all-ones'),
    'segment': ('none', 'non-segment', 'segment-narrow', 'segment-wide'),
    'stride': ('none', 'negative', 'zero', 'positive'),
    'payload': ('none', 'zero', 'mixed', 'all-ones'),
    'uop_position': ('none', 'first', 'middle', 'last'),
    'rob': ('none', 'zero', 'interior', 'max'),
}


def _point(name, values):
    return CoverPointDef(name, {value: Bin.values(value) for value in values})


class _HandshakeCoverage:
    def __init__(self):
        points = [
            _point(f'ldu_lane_{lane}', _HANDSHAKE_STATES)
            for lane in range(3)
        ] + [
            _point(f'sta_lane_{lane}', _HANDSHAKE_STATES)
            for lane in range(2)
        ] + [
            _point(f'empty_lane_{lane}', _HANDSHAKE_STATES)
            for lane in range(2)
        ]
        self.group = CoverGroupDef(
            'vagq_handshake_matrix_v1', tuple(points),
        ).instantiate(
            'vagq.handshake.checked',
            contract='public valid/ready combinations by lane/v1',
        )

    @staticmethod
    def _state(valid, ready):
        return f'v{int(bool(valid))}r{int(bool(ready))}'

    def sample(self, outputs, beat):
        values = {}
        for lane in range(3):
            values[f'ldu_lane_{lane}'] = self._state(
                outputs.get(f'io_lduReq_{lane}_valid', 0),
                beat.ldu_ready[lane],
            )
        for lane in range(2):
            values[f'sta_lane_{lane}'] = self._state(
                outputs.get(f'io_staReq_{lane}_valid', 0),
                beat.sta_ready[lane],
            )
            values[f'empty_lane_{lane}'] = self._state(
                outputs.get(f'io_lsqEmptyReq_{lane}_valid', 0),
                beat.empty_ready[lane],
            )
        self.group.sample(values)


class _BoundaryValueCoverage:
    def __init__(self):
        self.group = CoverGroupDef(
            'vagq_boundary_value_classes_v1',
            tuple(_point(name, values) for name, values in _VALUE_BINS.items()),
        ).instantiate(
            'vagq.boundary_values.checked',
            contract='public packet boundary value classes/v1',
        )

    @staticmethod
    def _packet(beat):
        return next((packet for packet, valid in zip(beat.addr, beat.addr_valid)
                     if valid and packet is not None), None)

    @staticmethod
    def _data(beat):
        return next((packet for packet, valid in zip(beat.stride, beat.stride_valid)
                     if valid and packet is not None), None) or next(
            (packet for packet, valid in zip(beat.index, beat.index_valid)
             if valid and packet is not None), None)

    @staticmethod
    def _mask(value):
        if value is None:
            return 'none'
        if value == 0:
            return 'zero'
        if value == 0xFFFF:
            return 'all-ones'
        if value & (value - 1) == 0:
            return 'one-hot'
        return 'multi-bit'

    @staticmethod
    def _signed(value):
        value &= (1 << 64) - 1
        return value - (1 << 64) if value & (1 << 63) else value

    def sample(self, beat):
        addr = self._packet(beat)
        data = self._data(beat)
        if addr is None:
            values = {
                'vl': 'none', 'vstart': 'none', 'mask': 'none',
                'segment': 'none', 'uop_position': 'none', 'rob': 'none',
            }
        else:
            try:
                maximum = vlmax(vsew=addr.vsew, vlmul=addr.vlmul)
            except ValueError:
                maximum = None
            values = {
                'vl': (
                    'zero' if addr.vl == 0 else
                    'one' if addr.vl == 1 else
                    'max' if maximum is not None and addr.vl == maximum else
                    'middle'
                ),
                'vstart': (
                    'zero' if addr.vstart == 0 else
                    'ge-vl' if addr.vstart >= addr.vl else 'middle'
                ),
                'mask': self._mask(addr.v0_byte_mask),
                'segment': (
                    'non-segment' if addr.nf == 0 else
                    'segment-narrow' if (addr.nf + 1) * (1 << addr.deew) <= 16
                    else 'segment-wide'
                ),
                'uop_position': (
                    'first' if addr.uop_idx == 0 and addr.last_uop else
                    'first' if addr.uop_idx == 0 else
                    'last' if addr.last_uop else 'middle'
                ),
                'rob': (
                    'zero' if addr.rob_value == 0 else
                    'max' if addr.rob_value == 0x1FF else 'interior'
                ),
            }
        if data is None:
            values['stride'] = 'none'
            values['payload'] = 'none'
        else:
            signed = self._signed(data.op2_data)
            values['stride'] = (
                'none' if addr is not None and addr.uop_type >= 4 else
                'negative' if signed < 0 else
                'zero' if signed == 0 else 'positive'
            )
            values['payload'] = (
                'zero' if data.op2_data == 0 else
                'all-ones' if data.op2_data in ((1 << 64) - 1, (1 << 128) - 1)
                else 'mixed'
            )
        self.group.sample(values)


class _LifecycleCoverage:
    def __init__(self):
        self.group = CoverGroupDef(
            'vagq_public_lifecycle_v1',
            (
                _point('state', _LIFECYCLE_STATES),
                _point('transition', _LIFECYCLE_TRANSITIONS),
            ),
        ).instantiate(
            'vagq.lifecycle.checked',
            contract='abstract public-boundary lifecycle and transition coverage/v1',
        )
        self.previous = {}

    def reset(self):
        self.previous.clear()

    @staticmethod
    def _response_for(beat, entry_idx):
        for response in beat.ldu_resp + beat.sta_resp:
            if response.valid and response.entry_idx == entry_idx:
                return response
        for response in beat.empty_resp:
            if response.valid and response.entry_idx == entry_idx:
                return response
        return None

    @staticmethod
    def _output_stage(outputs, beat, entry_idx):
        for group, count, ready in (
            ('lduReq', 3, beat.ldu_ready),
            ('staReq', 2, beat.sta_ready),
        ):
            for lane in range(count):
                prefix = f'io_{group}_{lane}_'
                if (outputs.get(prefix + 'valid', 0)
                        and outputs.get(prefix + 'bits_meta_valid', 0)
                        and outputs.get(prefix + 'bits_meta_entryIdx') == entry_idx):
                    return 'request' if ready[lane] else 'blocked'
        for lane in range(2):
            prefix = f'io_lsqEmptyReq_{lane}_'
            if (outputs.get(prefix + 'valid', 0)
                    and outputs.get(prefix + 'bits_entryIdx') == entry_idx):
                return 'request' if beat.empty_ready[lane] else 'blocked'
        return None

    def _stage(self, plan, outputs, beat):
        entry_idx = plan.addr.entry_idx
        if plan.flushed:
            return 'flushed'
        if plan.writeback_seen:
            return 'writeback'
        response = self._response_for(beat, entry_idx)
        if response is not None:
            if response.is_nack and not response.exception:
                return 'retry'
            return 'acknowledged'
        output_stage = self._output_stage(outputs, beat, entry_idx)
        if output_stage is not None:
            return output_stage
        previous = self.previous.get(entry_idx)
        if previous in ('retry', 'acknowledged'):
            return previous
        if plan.data_seen:
            return 'acknowledged'
        return 'allocated'

    def sample(self, model, outputs, beat):
        if not model.plans:
            self.group.sample({'state': 'empty', 'transition': 'other'})
            return
        current = {}
        for entry_idx, plan in model.plans.items():
            stage = self._stage(plan, outputs, beat)
            current[entry_idx] = stage
            previous = self.previous.get(entry_idx)
            admitted_this_cycle = any(
                valid and packet is not None and packet.entry_idx == entry_idx
                for packet, valid in zip(beat.addr, beat.addr_valid)
            ) or any(
                valid and packet is not None and packet.entry_idx == entry_idx
                for packet, valid in zip(beat.stride, beat.stride_valid)
            ) or any(
                valid and packet is not None and packet.entry_idx == entry_idx
                for packet, valid in zip(beat.index, beat.index_valid)
            )
            transition = (
                'empty->allocated'
                if previous is None and admitted_this_cycle else
                'other' if previous is None else f'{previous}->{stage}'
            )
            if transition not in _LIFECYCLE_TRANSITIONS:
                transition = 'other'
            self.group.sample({'state': stage, 'transition': transition})
        self.previous = current


class Coverage:
    def __init__(self):
        self.group = CoverGroupDef('vagq_integration_contract_v1', (
            CoverPointDef('admission', {name: Bin.values(name) for name in (
                'reset-idle', 'address-only', 'data-only', 'same-cycle pair',
                'indexed pair', 'occupied-pressure')}),
            CoverPointDef('vector_window', {name: Bin.values(name) for name in (
                'body', 'prestart', 'tail/inactive', 'agnostic', 'multi-uop/segment')}),
            CoverPointDef('route', {name: Bin.values(name) for name in (
                'stride-load', 'indexed-load', 'stride-store', 'indexed-store',
                'empty-marker')}),
            CoverPointDef('flow', {name: Bin.values(name) for name in (
                'load-multi', 'store-multi', 'native+active', 'LDU-blocked',
                'STA-blocked', 'empty-blocked', 'fire/retry')}),
            CoverPointDef('response', {name: Bin.values(name) for name in (
                'success', 'NACK', 'load-exception', 'store-exception',
                'empty-response')}),
            CoverPointDef('store_residency', {name: Bin.values(name) for name in (
                'no-read-before-ACK', 'VRF-read', 'STD-available', 'STD-busy')}),
            CoverPointDef('merge', {name: Bin.values(name) for name in (
                'skip/no-old-vd', 'old-vd-read', 'agnostic-merge', 'shared-VRF')}),
            CoverPointDef('completion', {name: Bin.values(name) for name in (
                'success', 'exception', 'load-wakeup', 'store-no-wakeup')}),
            CoverPointDef('redirect', {name: Bin.values(name) for name in (
                'no-flush', 'younger-flush', 'older-survives', 'pending-pipeline-flush')}),
            CoverPointDef('capacity', {name: Bin.values(name) for name in (
                'empty', 'one-entry', 'multiple-ROB', 'eight-entry-pressure')}),
        )).instantiate(
            'vagq.integration.checked',
            contract='top-level admission-to-completion composition/v1',
        )
        self.handshake = _HandshakeCoverage()
        self.boundary_values = _BoundaryValueCoverage()
        self.lifecycle = _LifecycleCoverage()

    def reset(self):
        """Reset only per-test temporal bookkeeping, not global bin counts."""
        self.lifecycle.reset()

    def sample(self, beat, outputs, model):
        addr = [packet for packet, valid in zip(beat.addr, beat.addr_valid) if valid and packet]
        stride = [packet for packet, valid in zip(beat.stride, beat.stride_valid) if valid and packet]
        index = [packet for packet, valid in zip(beat.index, beat.index_valid) if valid and packet]
        active = [plan for plan in model.plans.values() if not plan.flushed]

        occupied = any(not outputs.get(f'io_addrUop_{i}_ready', 0) for i in range(2))
        if (addr or stride or index) and occupied:
            admission = 'occupied-pressure'
        elif not addr and not stride and not index and not active:
            admission = 'reset-idle'
        elif addr and (stride or index):
            admission = 'indexed pair' if index else 'same-cycle pair'
        elif addr:
            admission = 'address-only'
        elif stride or index:
            admission = 'data-only'
        else:
            admission = 'one-entry'

        if not active:
            vector_window = 'body'
        else:
            plan = active[0]
            if plan.addr.vstart:
                vector_window = 'prestart'
            elif plan.addr.vma or plan.addr.vta:
                vector_window = 'agnostic'
            elif plan.addr.uop_idx or plan.addr.nf:
                vector_window = 'multi-uop/segment'
            elif plan.empty:
                vector_window = 'tail/inactive'
            else:
                vector_window = 'body'

        has_active_output = any(
            outputs.get(f'io_lduReq_{i}_valid', 0) and
            outputs.get(f'io_lduReq_{i}_bits_meta_valid', 0)
            for i in range(3)
        ) or any(
            outputs.get(f'io_staReq_{i}_valid', 0) and
            outputs.get(f'io_staReq_{i}_bits_meta_valid', 0)
            for i in range(2)
        )
        has_empty_output = any(
            outputs.get(f'io_lsqEmptyReq_{i}_valid', 0) for i in range(2)
        )
        if active:
            plan = active[0]
            if plan.addr.uop_type >= 4:
                route = 'indexed-load' if plan.is_load else 'indexed-store'
            else:
                route = 'stride-load' if plan.is_load else 'stride-store'
            if has_empty_output and not has_active_output:
                route = 'empty-marker'
        else:
            route = 'stride-load'

        native = any(packet.valid for packet in beat.issue_lda + beat.issue_sta)
        blocked_load = any(
            outputs.get(f'io_lduReq_{i}_valid', 0) and not beat.ldu_ready[i]
            for i in range(3)
        )
        blocked_store = any(
            outputs.get(f'io_staReq_{i}_valid', 0) and not beat.sta_ready[i]
            for i in range(2)
        )
        if native and has_active_output:
            flow = 'native+active'
        elif blocked_load:
            flow = 'LDU-blocked'
        elif blocked_store:
            flow = 'STA-blocked'
        elif any(outputs.get(f'io_lduReq_{i}_valid', 0) and
               outputs.get(f'io_lduReq_{i}_bits_meta_valid', 0)
               for i in range(3)):
            flow = 'load-multi' if sum(
                outputs.get(f'io_lduReq_{i}_valid', 0) and
                outputs.get(f'io_lduReq_{i}_bits_meta_valid', 0)
                for i in range(3)
            ) > 1 else 'fire/retry'
        elif any(outputs.get(f'io_staReq_{i}_valid', 0) and
                 outputs.get(f'io_staReq_{i}_bits_meta_valid', 0)
                 for i in range(2)):
            flow = 'store-multi' if sum(
                outputs.get(f'io_staReq_{i}_valid', 0) and
                outputs.get(f'io_staReq_{i}_bits_meta_valid', 0)
                for i in range(2)
            ) > 1 else 'fire/retry'
        elif any(outputs.get(f'io_lsqEmptyReq_{i}_valid', 0) for i in range(2)):
            flow = 'empty-blocked' if not any(beat.empty_ready) else 'fire/retry'
        elif native:
            flow = 'native+active'
        elif not all(beat.ldu_ready):
            flow = 'LDU-blocked'
        elif not all(beat.sta_ready):
            flow = 'STA-blocked'
        else:
            flow = 'fire/retry'

        response = 'success'
        if any(resp.valid and resp.is_nack for resp in beat.ldu_resp + beat.sta_resp):
            response = 'NACK'
        elif any(resp.valid and resp.exception for resp in beat.ldu_resp):
            response = 'load-exception'
        elif any(resp.valid and resp.exception for resp in beat.sta_resp):
            response = 'store-exception'
        elif any(resp.valid for resp in beat.empty_resp):
            response = 'empty-response'

        if any(beat.std_busy):
            store_residency = 'STD-busy'
        elif any(outputs.get(f'io_vrfReadReq_valid', 0) for _ in (0,)):
            store_residency = 'VRF-read'
        elif any(outputs.get(f'io_vagqStdData_{i}_valid', 0) for i in range(2)):
            store_residency = 'STD-available'
        else:
            store_residency = 'no-read-before-ACK'

        load_plan = next((plan for plan in active if plan.is_load), None)
        if outputs.get('io_vrfReadReq_valid', 0) and load_plan is not None:
            merge = 'old-vd-read'
        elif load_plan is not None and load_plan.info.get('mergeWriteMask', 0) == 0:
            merge = 'skip/no-old-vd'
        elif load_plan is not None and (load_plan.addr.vma or load_plan.addr.vta):
            merge = 'agnostic-merge'
        else:
            merge = 'shared-VRF'

        if outputs.get('io_vpWakeUp_valid', 0):
            completion = 'load-wakeup'
        elif outputs.get('io_robWriteback_valid', 0):
            exception = outputs.get('io_robWriteback_bits_exception', 0)
            completion = 'exception' if exception else 'success'
        elif active and not active[0].is_load and active[0].data_seen:
            completion = 'store-no-wakeup'
        else:
            completion = 'success'

        redirect = 'no-flush'
        if beat.redirect.valid:
            matched = any(
                plan.addr.rob_value == beat.redirect.rob_value
                for plan in model.plans.values()
            )
            survivor = any(
                not plan.flushed and plan.addr.rob_value != beat.redirect.rob_value
                for plan in model.plans.values()
            )
            if matched and survivor:
                redirect = 'older-survives'
            elif matched:
                redirect = 'pending-pipeline-flush'
            else:
                redirect = 'younger-flush'

        capacity = (
            'empty' if not active else
            'one-entry' if len(active) == 1 else
            'eight-entry-pressure' if len(active) >= 8 else
            'multiple-ROB'
        )
        self.group.sample({
            'admission': admission,
            'vector_window': vector_window,
            'route': route,
            'flow': flow,
            'response': response,
            'store_residency': store_residency,
            'merge': merge,
            'completion': completion,
            'redirect': redirect,
            'capacity': capacity,
        })
        self.handshake.sample(outputs, beat)
        self.boundary_values.sample(beat)
        self.lifecycle.sample(model, outputs, beat)
