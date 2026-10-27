"""bpuverify.bpu.monitor.bypass.monitor components."""

from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import memory_signal_names
from contextlib import suppress
import asyncio
from toffee import Bundle
from toffee import DriveStable
from toffee import RisingEdge
from toffee import Transfer
from toffee import on
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.plain_sampler import compile_plain


class BypassMonitor:
    def __init__(self, agent):
        self.agent = agent
        dut = agent.dut
        names = tuple(memory_signal_names(dut))
        self.prefixes = []
        tables = []
        for table in range(2):
            suffix = '' if table == 0 else '_1'
            ending = f'MicroTageTable{suffix}.wbuffer.enqPtr_value'
            matches = [name for name in names if name.endswith(ending)]
            if len(matches) != 1:
                raise RuntimeError(f'unique integrated shadow table{table} required: {matches!r}')
            prefix = matches[0].split('.', 1)[1].removesuffix('enqPtr_value')
            self.prefixes.append(prefix)
            def signal(field, prefix=prefix):
                value = memory_signal(dut, prefix + field)
                if value is None:
                    raise RuntimeError(f'integrated shadow leaf unavailable: {prefix + field}')
                return value
            def data(base):
                return dict(data_valid=signal(base + '_valid'), tag=signal(base + '_tag'),
                    position=signal(base + '_cfiPosition'), counter=signal(base + '_takenCtr_value'))
            cells = tuple(Bundle(valid=signal(f'entries_{slot}_valid'), index=signal(f'entries_{slot}_index'),
                payload_valid=signal(f'entries_{slot}_entryData_valid'),
                **data(f'entries_{slot}_entryData_bits')) for slot in range(8))
            state = Bundle(cells=cells, status=tuple(Bundle(valid=signal(f'statusEntries_{slot}_valid'),
                dirty=signal(f'statusEntries_{slot}_dirty')) for slot in range(8)),
                useful=tuple(signal(f'usefulEntries_{index % 4}_{index // 4}_value') for index in range(512)),
                enq=Bundle(flag=signal('enqPtr_flag'), value=signal('enqPtr_value')),
                deq=Bundle(flag=signal('deqPtr_flag'), value=signal('deqPtr_value')),
                mask=signal('priorityMask'), force=signal('forceWrite'),
                hits=tuple(signal(f'a1_entryHit_{slot}') for slot in range(8)),
                chosen=signal('a1_chosenFirstMask'), train_index=signal('t1_trainIndex'),
                train_has_hit=signal('t1_hasHit'))
            inputs = Bundle(read_index=signal('io_req_readIndex'), train_index=signal('io_train_t0_trainIndex_bits'),
                tag=signal('io_train_t1_tag'), allocate=signal('io_train_t1_alloc_valid'),
                allocate_taken=signal('io_train_t1_alloc_bits_taken'),
                allocate_position=signal('io_train_t1_alloc_bits_cfiPosition'),
                update=signal('io_train_t1_update_valid'), update_taken=signal('io_train_t1_update_bits_updateTaken'),
                update_position=signal('io_train_t1_update_bits_updateCfiPosition'),
                update_counter=signal('io_train_t1_update_bits_updateTakenCtr_value'),
                useful_valid=signal('io_train_t1_update_bits_usefulValid'),
                useful_increase=signal('io_train_t1_update_bits_needUseful'), age=signal('io_usefulReset'))
            outputs = Bundle(response=Bundle(hit=signal('io_resp_hit'), **data('io_resp_readEntry')),
                train_read=Bundle(hit=signal('io_train_t0_read_canGetPosition'),
                    position=signal('io_train_t0_read_cfiPosition'), useful=signal('io_train_t0_read_useful')),
                write=Bundle(valid=signal('io_tryWrite_valid'), index=signal('io_tryWrite_bits_writeIndex'),
                    force=signal('io_tryWrite_bits_forceWrite'), **data('io_tryWrite_bits_writeData')),
                write_success=signal('io_writeSuccess'))
            tables.append(Bundle(inputs=inputs, state=state, outputs=outputs))
        self.binding = PortBinding(dut.clock, Bundle(reset=dut.reset, tables=tuple(tables)),
            'bpu.integrated_microtage_shadow')
        self.subscriptions = []

    def start(self, checker):
        execution = self.agent._execution
        # One fused pass over the fixed tree; identical structure to
        # ``_plain(compile_sampler(bits)())`` with a single value read per leaf.
        sample_bits = compile_plain(self.binding.bits)
        for phase, event_type in (('rising', RisingEdge), ('preedge', DriveStable)):
            def capture(event, phase=phase):
                checker.capture(phase, Transfer(event=event, value=sample_bits()))
            async def delivered(_):
                pass
            spec = on(event_type(self.binding.clock), delivery='lossless', capacity=64, capture=capture)(delivered)
            self.subscriptions.append(execution.subscribe(spec.bind()))

    async def aclose(self):
        execution = self.agent._execution
        for subscription in self.subscriptions:
            execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError):
                    await subscription.task
        self.subscriptions.clear()
