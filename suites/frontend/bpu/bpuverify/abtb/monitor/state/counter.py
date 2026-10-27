"""Coherent static Bundle monitor, direct comparison, and exact public intent association."""
from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import memory_signal_names
from collections import deque
from copy import deepcopy
from dataclasses import asdict
from dataclasses import replace

from toffee import Bundle
from toffee import CheckContext
from toffee import RisingEdge
from toffee import Scoreboard
from toffee import ScoreboardMode
from toffee import on
from bpuverify.abtb.bundle.values import _plain
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.monitor.cycle import CycleMonitor


class CounterMonitor(CycleMonitor):
    @staticmethod
    def decode(snapshot):
        row=_plain(snapshot)
        if not row['training']['valid']:
            row['training']['bits']=None
        return row

    def __init__(self,agent):
        dut=agent.dut
        names=tuple(memory_signal_names(dut))
        candidates=[name for name in names if name.endswith('.takenCounter_0_0_0_value')]
        if len(candidates)!=1:
            raise RuntimeError(f'unique ABTB counter hierarchy required: {candidates!r}')
        prefix=candidates[0].split('.',1)[1].removesuffix('takenCounter_0_0_0_value')

        def signal(name):
            value=memory_signal(dut, prefix+name)
            if value is None:
                raise RuntimeError(f'counter memory-direct leaf unavailable: {prefix+name}')
            return value

        def write(bank):
            base=f'banks_{bank}.io_writeResp'
            return Bundle(valid=signal(base+'_valid'),set_index=signal(base+'_bits_setIdx'),
                way=signal(base+'_bits_wayIdx'),reset_counter=signal(base+'_bits_needResetCtr'))

        super().__init__(PortBinding(dut.clock,Bundle(reset=dut.reset,enable=agent.ports.control.bits.enable,
            training=Bundle(valid=agent.ports.training.valid,bits=agent.ports.training.bits),
            writes=tuple(write(b) for b in range(4)),
            cells=tuple(signal(f'takenCounter_{b}_{s}_{w}_value')
                for b in range(4) for s in range(64) for w in range(4))),
            'abtb.counter_observation'),decoder=self.decode)

    def start(self,execution,*,observer):
        if self._subscription is not None or execution.reactor is None:
            raise RuntimeError('counter monitor requires a new active subscription')
        def capture(event):
            observer(self.sample_at(event))
        async def delivered(_):
            pass
        spec=on(RisingEdge(self.binding.clock),delivery='lossless',capacity=self.capacity,
                capture=capture)(delivered)
        self._subscription=execution.subscribe(spec.bind())
        self._execution=execution
        return self


def public_transaction(bits):
    branch=bits['branch']
    return dict(pc=bits['start_pc'],target=branch['target'],taken=branch['taken'],
        position=branch['position'],branch_type=branch['branch_type'],meta=bits['meta'],
        ras_action=branch['ras_action'],mispredict=branch['mispredict'])
