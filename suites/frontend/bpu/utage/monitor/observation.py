"""suites.frontend.bpu.utage.monitor.observation components."""

from suites.frontend.bpu.runtime.memory_direct import memory_signal
from suites.frontend.bpu.runtime.memory_direct import memory_signal_names
from hashlib import sha256
from toffee import Bundle
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.utage.bundle.values import _plain


class UtageUsefulMonitor(CycleMonitor):
    def __init__(self, agent):
        self.prefixes, self.cells, controls = self._bind(agent)
        self.public_payload = agent.ports.training_observation.bits
        self.latest = None
        self.sample_count = 0
        self._was_active = False
        super().__init__(PortBinding(agent.dut.clock, Bundle(reset=agent.dut.reset,
            enable=agent.ports.control.bits.enable, public_valid=agent.ports.training.valid, tables=controls),
            'utage.useful_observation'), decoder=self._decode)

    @staticmethod
    def _bind(agent):
        cached = getattr(agent, '_utage_useful_bindings_v1', None)
        if cached is not None:
            return cached
        dut = agent.dut
        names = tuple(memory_signal_names(dut))
        cells, controls, prefixes = [], [], []
        for table in range(2):
            suffix = '' if table == 0 else '_1'
            ending = f'MicroTageTable{suffix}.wbuffer.enqPtr_value'
            matches = [name for name in names if name.endswith(ending)]
            if len(matches) != 1:
                raise RuntimeError(f'unique MicroTAGE table{table} memory-direct binding required; got{matches!r}')
            prefix = matches[0].split('.', 1)[1].removesuffix('enqPtr_value')
            prefixes.append(prefix)

            def signal(field, prefix=prefix):
                return memory_signal(dut, prefix + field)

            cells.extend(signal(f'usefulEntries_{index % 4}_{index // 4}_value') for index in range(512))
            controls.append(Bundle(index=signal('t1_trainIndex'), allocate=signal('io_train_t1_alloc_valid'),
                update=signal('io_train_t1_update_valid'), useful_valid=signal('io_train_t1_update_bits_usefulValid'),
                increase=signal('io_train_t1_update_bits_needUseful'), age=signal('io_usefulReset')))
        cached = (tuple(prefixes), Bundle(counters=tuple(cells)), tuple(controls))
        agent._utage_useful_bindings_v1 = cached
        return cached

    def _decode(self, snapshot):
        result = _plain(snapshot)
        valid = result.pop('public_valid')
        result['public'] = dict(valid=valid, bits=_plain(self.public_payload.sample()) if valid else None)
        active = any(table['allocate'] or table['update'] and table['useful_valid'] or table['age']
                     for table in result['tables'])
        if self.latest is None or active or self._was_active:
            current = _plain(self.cells.sample())['counters']
            if len(current) != 1024 or any(value not in range(4) for value in current):
                raise RuntimeError('useful observation requires1024two-bit counters')
            previous = (0,) * 1024 if self.latest is None else self.latest
            result['changes'] = tuple((index, old, new)
                for index, (old, new) in enumerate(zip(previous, current, strict=True)) if old != new)
            result['all_cells_sha256'] = sha256(bytes(current)).hexdigest()
            self.latest = tuple(current)
            self.sample_count += 1
        self._was_active = active
        return result
