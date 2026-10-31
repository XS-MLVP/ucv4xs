"""Same-event native table state and public prediction sampling for TAGE."""
from suites.frontend.bpu.models.configuration import *

from suites.frontend.bpu.runtime.memory_direct import memory_signal
from suites.frontend.bpu.runtime.memory_direct import memory_signal_names
from dataclasses import replace

from toffee import Bundle

from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.tage.model.pair import TageTableState


class TageSelectorMonitor(CycleMonitor):
    """Read-only five-bit ``useAltOnNa`` registers, indexed by (table, altConf)."""

    def __init__(self, dut):
        names = tuple(memory_signal_names(dut))

        def signal(index):
            suffix = f'.Tage.useAltOnNaVec_{index}_value'
            matches = [name for name in names if name.endswith(suffix)]
            if len(matches) != 1:
                raise RuntimeError(
                    f'TAGE selector register {index} needs one memory-direct binding; '
                    f'found {len(matches)}: {matches}')
            return memory_signal(dut, matches[0].split('.', 1)[1])

        self.fields = tuple(signal(index) for index in range(2*TAGE_TABLES))
        binding = PortBinding(dut.clock,
            Bundle(registers=tuple(self.fields)), 'tage.selectors')
        super().__init__(binding, decoder=lambda sample: tuple(value.as_int() for value in sample.registers))


class TagePredictionStateMonitor(CycleMonitor):
    """A read-only optional binding; the existing Scoreboard owns scheduling."""
    def __init__(self, dut, prediction_binding, base_decoder):
        names = tuple(memory_signal_names(dut))

        def signal(suffix):
            matches = [name for name in names if name.endswith('.Tage.'+suffix)]
            if len(matches) != 1:
                raise RuntimeError(f'TAGE state signal {suffix} needs one memory-direct binding; found {len(matches)}: {matches}')
            return memory_signal(dut, matches[0].split('.', 1)[1])

        hit_masks = tuple(tuple(signal(f's2_hits_{slot}_{table}') for table in range(TAGE_TABLES)) for slot in range(RESULT_SLOTS))
        table_entries = tuple(tuple(Bundle(
            counter=signal(f's2_readResp_{table}_entries_{way}_takenCtr_value'),
            useful=signal(f's2_readResp_{table}_usefulCtrs_{way}_value'),
        ) for way in range(2)) for table in range(TAGE_TABLES))
        alternate_counters = tuple(signal(f'alt_{slot}_takenCtr_value' if slot else 'alt_takenCtr_value')
                                   for slot in range(RESULT_SLOTS))
        binding = PortBinding(dut.clock, Bundle(prediction=prediction_binding.bits,
            hit_masks=hit_masks, table_entries=table_entries, alternate_counters=alternate_counters), 'tage.prediction_state')

        def decode(sample):
            states = []
            for branch_masks in sample.hit_masks:
                branch = []
                for table, mask in enumerate(branch_masks):
                    bits = mask.as_int()
                    if not bits:
                        branch.append(None)
                    else:
                        way = (bits & -bits).bit_length()-1
                        entry = sample.table_entries[table][way]
                        branch.append(TageTableState(bits, entry.counter.as_int(), entry.useful.as_int()))
                states.append(tuple(branch))
            return replace(base_decoder(sample.prediction), table_states=tuple(states),
                           alternate_counters=tuple(value.as_int() for value in sample.alternate_counters))

        super().__init__(binding, decoder=decode)
