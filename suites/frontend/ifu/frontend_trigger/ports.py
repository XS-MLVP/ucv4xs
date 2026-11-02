"""All50 nonclock inputs and36 action outputs; PC units change only here."""
from toffee import Bundle

from suites.frontend.ifu.model.trigger import LANES, TRIGGERS, Trigger

from .types import Actions, Frame


SCALARS = {
    'reset': ('reset', 1),
    'update_valid': ('io_frontendTrigger_tUpdate_valid', 1),
    'update_index': ('io_frontendTrigger_tUpdate_bits_addr', 2),
    'match_type': ('io_frontendTrigger_tUpdate_bits_tdata_matchType', 2),
    'select': ('io_frontendTrigger_tUpdate_bits_tdata_select', 1),
    'action': ('io_frontendTrigger_tUpdate_bits_tdata_action', 4),
    'chain': ('io_frontendTrigger_tUpdate_bits_tdata_chain', 1),
    'tdata2': ('io_frontendTrigger_tUpdate_bits_tdata_tdata2', 64),
    'debug_mode': ('io_frontendTrigger_debugMode', 1),
    'can_raise_breakpoint': ('io_frontendTrigger_triggerCanRaiseBpExp', 1),
}


class TriggerPorts:
    def __init__(self, dut):
        def bind(name, width, *, output=False):
            signal = getattr(dut, name)
            if max(1, int(signal.mWidth)) != width:
                raise ValueError(f'{name}: expected native width {width}, got {signal.mWidth}')
            if ((output and not signal.IsOutIO())
                    or (not output and (not signal.IsInIO() or signal.IsOutIO()))):
                raise ValueError(f'{name}: wrong native port direction')
            return signal

        self.bits = Bundle(**{field: bind(name, width) for field, (name, width) in SCALARS.items()},
            enable=tuple(bind(f'io_frontendTrigger_tEnableVec_{i}', 1) for i in range(TRIGGERS)),
            pcs=tuple(bind(f'io_pc_{lane}_addr', 49) for lane in range(LANES)))
        self._outputs = Bundle(actions=tuple(bind(f'io_triggered_{lane}', 4, output=True)
                                            for lane in range(LANES)))
        bind('clock', 1)
        actual = {name for name, signal in vars(dut).items() if name not in {'dut', 'clock'}
                  and callable(getattr(signal, 'IsInIO', None)) and signal.IsInIO() and not signal.IsOutIO()}
        expected = {name for name, _ in SCALARS.values()} | {
            f'io_frontendTrigger_tEnableVec_{i}' for i in range(TRIGGERS)} | {
            f'io_pc_{lane}_addr' for lane in range(LANES)}
        if actual != expected:
            raise ValueError(f'FrontendTrigger input ownership mismatch: {actual ^ expected}')

    @staticmethod
    def encode(frame):
        if not isinstance(frame, Frame):
            raise TypeError('FrontendTrigger requires a semantic Frame')
        inputs, update = frame.inputs, frame.inputs.update
        trigger = update.trigger or Trigger()
        return dict(reset=frame.reset, update_valid=update.valid, update_index=update.index,
            match_type=trigger.match_type, select=trigger.select, action=trigger.action,
            chain=trigger.chain, tdata2=trigger.tdata2, debug_mode=inputs.debug_mode,
            can_raise_breakpoint=inputs.can_raise_breakpoint, enable=inputs.enable,
            pcs=tuple(pc >> 1 for pc in inputs.pcs))

    def capture(self, event):
        return Actions(tuple(int(value) for value in self._outputs.sample()['actions']))
