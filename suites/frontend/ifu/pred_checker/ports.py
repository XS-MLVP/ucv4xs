"""All real pins, exact widths and pruned constants of PredChecker belong here."""
from toffee import Bundle

from suites.frontend.ifu.model.pred_checker import LANES, PC_BITS, PC_MASK, Redirect

from .types import BeforeEdge, Frame, Interface


INSTR_FIELDS = {
    'valid': ('instrVec_{lane}_valid', 1),
    'is_rvc': ('instrVec_{lane}_isRvc', 1),
    'is_pred_taken': ('instrVec_{lane}_isPredTaken', 1),
    'invalid_taken': ('instrVec_{lane}_invalidTaken', 1),
    'block_sel': ('instrVec_{lane}_blockSel', 1),
    'end_offset': ('instrVec_{lane}_endOffset', 5),
    'branch_type': ('pdInfoVec_{lane}_brAttribute_branchType', 2),
    'ras_action': ('pdInfoVec_{lane}_brAttribute_rasAction', 2),
}
REDIRECT_FIELDS = {
    'target': ('bits_target_addr', PC_BITS - 1),
    'taken': ('bits_taken', 1),
    'invalid_taken': ('bits_invalidTaken', 1),
    'not_cfi_taken': ('bits_notCfiTaken', 1),
    'is_rvc': ('bits_isRVC', 1),
    'block_sel': ('bits_blockSel', 1),
    'branch_type': ('bits_attribute_branchType', 2),
    'ras_action': ('bits_attribute_rasAction', 2),
    'end_offset': ('bits_endOffset', 5),
    'is_cross_block': ('bits_isCrossBlockInstr', 1),
}
PRUNED = (
    'io_req_bits_instrVec_34_isCrossBlockInstr',
    'io_req_bits_instrVec_35_valid',
    'io_resp_stage1Out_fixedInstrValid_35',
)


class PredCheckerPorts:
    interface = Interface()

    def __init__(self, dut):
        self._inputs = {}

        def bind(name, width, *, output=False):
            signal = getattr(dut, name)  # Missing is a binding error, never a zero.
            if max(1, int(signal.mWidth)) != width:
                raise ValueError(f'{name}: expected native width {width}, got {signal.mWidth}')
            if ((output and not signal.IsOutIO())
                    or (not output and (not signal.IsInIO() or signal.IsOutIO()))):
                raise ValueError(f'{name}: wrong native port direction')
            if not output:
                self._inputs[name] = signal
            return signal

        bind('reset', 1)
        bind('io_req_valid', 1)
        for lane in range(LANES):
            for suffix, width in INSTR_FIELDS.values():
                bind('io_req_bits_' + suffix.format(lane=lane), width)
            bind(f'io_req_bits_pdInfoVec_{lane}_isRVC', 1)
            bind(f'io_req_bits_instrPcVec_{lane}_addr', PC_BITS - 1)
            bind(f'io_req_bits_jumpOffsetVec_{lane}_addr', PC_BITS - 1)
            if lane < LANES - 1:
                bind(f'io_req_bits_instrVec_{lane}_isCrossBlockInstr', 1)
        bind(f'io_req_bits_instrPcVec_{LANES}_addr', PC_BITS - 1)
        self.bits = Bundle(**self._inputs)
        self._fixed = Bundle({f'lane_{lane}': bind(
            f'io_resp_stage1Out_fixedInstrValid_{lane}', 1, output=True) for lane in range(LANES)})
        self._redirect = Bundle(valid=bind('io_resp_stage2Out_checkerRedirect_valid', 1, output=True), **{
            field: bind('io_resp_stage2Out_checkerRedirect_' + suffix, width, output=True)
            for field, (suffix, width) in REDIRECT_FIELDS.items()
        })
        for name in PRUNED:
            if hasattr(dut, name):
                raise ValueError(f'{name}: expected a proven pruned constant, but port exists')
        actual_inputs = {
            name for name, signal in vars(dut).items()
            if name not in {'clock', 'dut'} and callable(getattr(signal, 'IsInIO', None))
            and signal.IsInIO() and not signal.IsOutIO()
        }
        if actual_inputs != self._inputs.keys():
            raise ValueError(f'PredChecker input ownership mismatch: {actual_inputs ^ self._inputs.keys()}')

    def encode(self, frame):
        if not isinstance(frame, Frame):
            raise TypeError('PredChecker driver requires a Frame')
        values = {'reset': int(frame.reset), 'io_req_valid': frame.request.valid}
        for lane, instruction in enumerate(frame.request.instrs[:LANES]):
            for field, (suffix, _) in INSTR_FIELDS.items():
                values['io_req_bits_' + suffix.format(lane=lane)] = getattr(instruction, field)
            values[f'io_req_bits_pdInfoVec_{lane}_isRVC'] = instruction.is_rvc
            values[f'io_req_bits_instrPcVec_{lane}_addr'] = instruction.pc >> 1
            values[f'io_req_bits_jumpOffsetVec_{lane}_addr'] = (instruction.jump_offset & PC_MASK) >> 1
            if lane < LANES - 1:
                values[f'io_req_bits_instrVec_{lane}_isCrossBlockInstr'] = instruction.is_cross_block
        values[f'io_req_bits_instrPcVec_{LANES}_addr'] = frame.padding_pc >> 1
        if values.keys() != self._inputs.keys():
            raise ValueError('PredChecker encoder must drive every owned input exactly once')
        return values

    def capture_redirect(self, event):
        snapshot = self._redirect.sample()  # Framework sampler calls fresh native getters.
        if not int(snapshot['valid']):
            return Redirect()  # Invalid payload has no contractual value.
        fields = {field: int(snapshot[field]) for field in REDIRECT_FIELDS}
        fields['target'] <<= 1  # Public API uses guarded byte addresses, not [50:1].
        return Redirect(valid=1, **fields)

    def capture_before(self, event):
        return BeforeEdge(tuple(int(value) for value in self._fixed.sample().values()),
                          self.capture_redirect(event))
