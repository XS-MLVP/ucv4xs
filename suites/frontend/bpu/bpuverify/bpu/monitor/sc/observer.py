"""Static, read-only views of SC T0/read responses and all sixteen shadow buffers."""
from bpuverify.common.model.configuration import *

from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import memory_signal_names
from toffee import Bundle
from toffee import DriveStable
from toffee import Transfer
from toffee import on
from toffee.data import sample_data
import asyncio
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.monitor.cycle import CycleMonitor
from bpuverify.bpu.bundle.values import _plain
from bpuverify.bpu.model.sc.model import TABLES
from bpuverify.bpu.model.sc.model import width
from bpuverify.bpu.model.sc.training_path import SC_FIELDS
from bpuverify.bpu.model.sc.training_path import DEBUG_VECTORS


class ScMonitor(CycleMonitor):
    def __init__(self, agent):
        dut = agent.dut
        names = tuple(memory_signal_names(dut))
        anchor, = [name for name in names if name.endswith('.sc.pathTable_0.writeBuffer_0.shadowValid_0_0')]
        sc_prefix = anchor.split('.', 1)[1].split('pathTable_0.', 1)[0]
        self.paths = {'sc': sc_prefix}

        def signal(leaf):
            path = sc_prefix + leaf
            value = memory_signal(dut, path)
            if value is None:
                raise RuntimeError(f'Missing SC observation signal: {path}')
            return value

        buffers, reads = {}, {}
        for table in TABLES:
            ways = width(table)
            prefix = table + '.'
            reads[table] = Bundle(valid=signal(prefix + 'io_trainReadReq_valid'),
                set_index=signal(prefix + 'io_trainReadReq_bits_setIdx'),
                bank_mask=signal(prefix + 'io_trainReadReq_bits_bankMask'),
                response=tuple(signal(prefix + f'io_trainReadResp_{way}_ctr_value')
                               for way in range(ways)))
            for bank in range(2):
                key = f'{table}_bank{bank}'
                base = prefix + f'writeBuffer_{bank}.'
                self.paths[key] = sc_prefix + base

                def payload(leaf):
                    return Bundle(set_index=signal(base + leaf + 'setIdx'),
                        masks=tuple(signal(base + leaf + f'wayMask_{way}') for way in range(ways)),
                        data=tuple(signal(base + leaf + f'wayData_{way}') for way in range(ways)))

                slots = tuple(Bundle(valid=signal(base + f'shadowValid_0_{slot}'),
                    dirty=signal(base + f'dirty_0_{slot}'), payload=payload(f'entries_0_{slot}_'))
                    for slot in range(4))
                buffers[key] = Bundle(reset=signal(base + 'reset'), slots=slots,
                    write=Bundle(valid=signal(base + 'io_write_0_valid'), bits=payload('io_write_0_bits_')),
                    drain=Bundle(valid=signal(base + 'io_read_0_valid'), ready=signal(base + 'io_read_0_ready'),
                                 bits=payload('io_read_0_bits_')))
        inputs = Bundle(pc=signal('io_train_startPcVec_dup_0_0_addr'),
            branches=tuple(Bundle(valid=signal(f'io_train_branches_{index}_valid'),
                bits=Bundle(taken=signal(f'io_train_branches_{index}_bits_taken'),
                    cfiPosition=signal(f'io_train_branches_{index}_bits_cfiPosition'),
                    branchType=signal(f'io_train_branches_{index}_bits_attribute_branchType')))
                for index in range(8)),
            mbtb_entries=tuple(tuple(Bundle(rawHit=signal(f'io_train_meta_mbtb_entries_{bank}_{way}_rawHit'),
                position=signal(f'io_train_meta_mbtb_entries_{bank}_{way}_position'))
                for way in range(MAIN_WAYS + 1)) for bank in range(2)),
            commonHR=Bundle(**{name: signal('io_train_meta_commonHR_' + name)
                               for name in ('valid', 'ghr', 'bw', 'imli')}),
            sc=Bundle(**{name: tuple(signal(f'io_train_meta_sc_{name}_{index}') for index in range(RESULT_SLOTS))
                         for name in SC_FIELDS}),
            debug=Bundle(**{name: tuple(signal(f'io_train_meta_sc_debug_{name}_{index}')
                          for index in range(RESULT_SLOTS)) for name in DEBUG_VECTORS},
                predPathIdx=tuple(signal(f'io_train_meta_sc_debug_predPathIdx_{i}') for i in range(2)),
                predGlobalIdx=tuple(signal(f'io_train_meta_sc_debug_predGlobalIdx_{i}') for i in range(2)),
                predBWIdx=tuple(signal(f'io_train_meta_sc_debug_predBWIdx_{i}') for i in range(2)),
                predImliIdx=signal('io_train_meta_sc_debug_predImliIdx'),
                predBiasIdx=signal('io_train_meta_sc_debug_predBiasIdx')))
        t0 = Bundle(enable=signal('io_enable'), stage_fire=signal('io_stageCtrl_t0_fire'),
            fire=signal('t0_fire'), ready=signal('io_trainReady'), inputs=inputs,
            folded_path=tuple(signal(f'io_trainFoldedPathHist_hist_{PHR_FOLDS.index((n,7))}_foldedHist') for n in SC_PATH_HISTORIES),
            predict_stage_fire=signal('io_stageCtrl_s0_fire'), predict_pc=signal('io_startPc_addr'),
            predict_fire=signal('s0_fire'), predict_bank_mask=signal('s0_bankMask'),
            bank_mask=signal('t0_bankMask'), need_write=signal('t0_needWrite'), reads=Bundle(**reads))
        training, prediction = agent.ports.training, agent.ports.prediction
        super().__init__(PortBinding(dut.clock, Bundle(buffers=Bundle(**buffers), t0=t0,
            training=Bundle(valid=training.valid, ready=training.ready, bits=training.bits),
            prediction=Bundle(valid=prediction.valid, ready=prediction.ready)), 'bpu.sc.masked_feedback'),
            decoder=_plain)

    def start(self, execution, *, observer=None, controls=None):
        if controls is None:
            raise ValueError('SC state reference requires explicit preedge controls capture')
        super().start(execution, observer=observer)

        def capture(event):
            return Transfer(event=event, value=_plain(sample_data(self.binding.bits)))

        async def deliver(observation):
            controls(observation)

        spec = on(DriveStable(self.binding.clock), delivery='lossless', capacity=64, capture=capture)(deliver)
        self._controls_subscription = execution.subscribe(spec.bind())
        return self

    async def aclose(self):
        subscription = getattr(self, '_controls_subscription', None)
        self._controls_subscription = None
        if subscription is not None:
            self._execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                await asyncio.gather(subscription.task, return_exceptions=True)
        await super().aclose()
