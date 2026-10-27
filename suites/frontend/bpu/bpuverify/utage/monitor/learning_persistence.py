"""Event-only native receipts; SRAM words are read through memory-direct only."""
import asyncio
from contextlib import suppress
from copy import deepcopy

from toffee import Bundle, DriveStable, RisingEdge, on
from toffee.signals import signal_width

from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.utage.bundle.values import _plain
from bpuverify.utage.monitor.observation import UtageUsefulMonitor
from bpuverify.utage.monitor.shadow import UtageShadowMonitor


class Monitor:
    def __init__(self, agent, program, ledger):
        self.agent, self.program, self.ledger = agent, program, ledger
        prefixes, self.protection, _ = UtageUsefulMonitor._bind(agent)
        self.shadow = tuple(UtageShadowMonitor(agent, table=table) for table in (0, 1))
        self.cells, self.layout, services, ownership = {}, {}, [], []
        for table, prefix in enumerate(prefixes):
            def signal(field, prefix=prefix):
                return memory_signal(agent.dut, prefix + field)
            services.append(Bundle(valid=signal('io_tryWrite_valid'), success=signal('io_writeSuccess'),
                index=signal('io_tryWrite_bits_writeIndex'), data=Bundle(valid=signal('io_tryWrite_bits_writeData_valid'),
                    tag=signal('io_tryWrite_bits_writeData_tag'), position=signal('io_tryWrite_bits_writeData_cfiPosition'),
                    counter=signal('io_tryWrite_bits_writeData_takenCtr_value'))))
            ownership.append(Bundle(enq=signal('enqPtr_value'),deq=signal('deqPtr_value'),
                dirty=tuple(signal(f'statusEntries_{slot}_dirty') for slot in range(8))))
            for history in program.histories:
                _, index, _, _ = program.identity(history, table)
                root = prefix.removesuffix('wbuffer.')
                cell = memory_signal(agent.dut,
                    root + f'utage_entry_sram_bank{index % 4}.array.array_ext.Memory', index // 4)
                self.cells[table, index] = Bundle(word=cell).compile_sampler()
                tag_width = signal_width(self.shadow[table].binding.bits.cells[0].tag)
                position_width = signal_width(self.shadow[table].binding.bits.cells[0].position)
                counter_width = signal_width(self.shadow[table].binding.bits.cells[0].counter)
                padding = signal_width(cell) - (1 + tag_width + position_width + counter_width)
                if padding != 1:
                    raise AssertionError('native SRAM packing must retain the documented reserved bit')
                self.layout[table] = (tag_width, position_width, counter_width, padding)
        self.services = Bundle(tables=tuple(services)).compile_sampler()
        self.ownership = Bundle(tables=tuple(ownership)).compile_sampler()
        self.public = Bundle(valid=agent.ports.training.valid, bits=agent.ports.training.bits).compile_sampler()
        self.previous_enq = None
        self.launched_service = None
        self.attempts = []
        self.storage_checks = []
        self.memory_changes = []
        self.last_memory = self.memory()
        self.failure = None
        self.latest_shadow = None
        self.subscriptions = []

    def decode(self, table, word):
        tag_width, position_width, counter_width, padding = self.layout[table]
        value = word >> padding
        counter = value & ((1 << counter_width) - 1); value >>= counter_width
        position = value & ((1 << position_width) - 1); value >>= position_width
        tag = value & ((1 << tag_width) - 1); value >>= tag_width
        return dict(valid=value, tag=tag, position=position, counter=counter)

    def memory(self):
        return {key: self.decode(key[0], sample().word.as_int()) for key, sample in self.cells.items()}

    def before(self, event):
        try:
            current = _plain(self.services())['tables']
            # Like the existing public input monitor, keep one launch receipt
            # separate from the phase that consumes it. Calibration is checked
            # against actual native SRAM, not inferred from model.commits.
            self.launched_service = (event.tick, current)
        except Exception as error:
            self.failure = error

    def after(self, event):
        if self.failure is not None:
            return
        try:
            public = _plain(self.public())
            if public['valid']:
                self.ledger.accept(public['bits'], event.tick)
            shadows = [self.shadow[table].sample_at(event).value for table in (0, 1)]
            self.latest_shadow = deepcopy(shadows)
            if self.previous_enq is not None:
                for table, row in enumerate(shadows):
                    old = self.previous_enq[table]
                    if row['enq'] != old:
                        if row['enq'] != (old + 1) % len(row['cells']):
                            raise AssertionError('one version write per table and boundary')
                        cell = row['cells'][old]
                        entry = {key: cell[key] for key in ('valid', 'tag', 'position', 'counter')}
                        entry['valid'] = cell['data_valid']
                        self.ledger.publish(table, cell['index'], entry, event.tick)
            self.previous_enq = tuple(row['enq'] for row in shadows)
            memory = self.memory()
            serviced = {}
            if self.launched_service is not None:
                tick, services = self.launched_service
                for table, row in enumerate(services):
                    if not row['valid'] or not row['success']:
                        continue
                    key = table, row['index']
                    if key not in memory:
                        raise AssertionError('service of an undeclared logical identity')
                    self.attempts.append(dict(tick=tick, table=table, index=row['index'], entry=row['data'],
                                              stored=memory[key]))
                    if memory[key] != row['data']:
                        raise AssertionError(f'actual service/storage differ: {self.attempts[-1]}')
                    self.ledger.service(table, row['index'], row['data'], event.tick)
                    self.storage_checks.append(dict(tick=event.tick, table=table, index=row['index']))
                    serviced[key] = row['data']
            for key, entry in memory.items():
                if entry != self.last_memory[key]:
                    if serviced.get(key) != entry:
                        raise AssertionError(f'persistent state changed without its actual service: {key}, {entry}')
                    self.memory_changes.append(dict(tick=event.tick, table=key[0], index=key[1],
                                                    previous=self.last_memory[key], entry=entry))
            self.last_memory = memory
        except Exception as error:
            self.failure = error

    def start(self):
        async def delivered(_):
            pass
        for trigger, capture in ((DriveStable(self.agent.dut.clock), self.before),
                                 (RisingEdge(self.agent.dut.clock), self.after)):
            self.subscriptions.append(self.agent._execution.subscribe(on(trigger,
                capture=capture, delivery='lossless', capacity=64)(delivered).bind()))
        return self

    def check(self):
        if self.failure is not None:
            raise self.failure

    async def aclose(self, *, raise_failure=True):
        for subscription in self.subscriptions:
            self.agent._execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError):
                    await subscription.task
        if raise_failure:
            self.check()
