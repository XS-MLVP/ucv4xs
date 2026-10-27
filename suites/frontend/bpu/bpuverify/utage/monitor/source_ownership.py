"""Bounded actual samples, including publicly decoded input lineage."""
from collections import deque
from dataclasses import dataclass

from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.monitor.cycle import CycleMonitor
from bpuverify.utage.bundle.values import _plain
from bpuverify.utage.monitor.decode import _decode
from bpuverify.utage.monitor.shadow import UtageShadowMonitor


@dataclass(frozen=True, slots=True)
class SourceObservation:
    tick: int
    inputs: object
    prediction: object
    shadow: dict


class SourceOwnershipMonitor(CycleMonitor):
    def __init__(self, agent):
        self.agent = agent
        self.records = deque(maxlen=64)
        shadow = UtageShadowMonitor(agent, table=0).binding.bits
        super().__init__(PortBinding(agent.dut.clock, Bundle(prediction=agent.ports.prediction.bits,
            shadow=shadow), 'utage.saved-source-observation'), decoder=lambda row:
            (agent.reference_monitor.last_inputs, _decode(row.prediction), _plain(row.shadow)))

    def observe(self, observation):
        inputs, prediction, shadow = observation.value
        # These Events are decoded by the existing @on public-input monitor,
        # not copied from golden frame/memory state or repaired from outputs.
        # Freeze identity in the synchronous capture/decoder above. Lossless
        # async delivery may happen after the input monitor has advanced.
        self.records.append(SourceObservation(observation.event.tick, inputs, prediction, shadow))

    async def __aenter__(self):
        self.start(self.agent._execution, observer=self.observe)
        return self

    async def __aexit__(self, *error): await self.aclose()

    def recovery_rows(self, program):
        rows = tuple(self.records)
        matches = [i for i, row in enumerate(rows) if row.inputs is not None
                   and row.inputs.override == program.stage]
        if len(matches) != 1 or matches[0] < 3:
            raise AssertionError(dict(point='one observed recovery after three actual inputs',
                program=program.state(), observed=rows, matches=matches))
        index = matches[0]
        return rows[index-3:index+1]
