"""suites.frontend.bpu.bpu.monitor.abtb.observation components."""

from suites.frontend.bpu.runtime.memory_direct import memory_signal
import asyncio
from contextlib import suppress
from toffee import Bundle
from toffee import DriveStable
from toffee import on
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.bpu.monitor.phr.observation import BpuPhrMonitor
from suites.frontend.bpu.runtime.plain_sampler import compile_plain

class IntegratedMonitor(BpuPhrMonitor):
    def __init__(self, agent):
        super().__init__(agent)
        dut = agent.dut
        parent_prefix = self.prefix.removesuffix('phr.')
        prefix = parent_prefix + 'abtb.'
        def signal(name, *, parent=False):
            path = (parent_prefix if parent else prefix) + name
            result = memory_signal(dut, path)
            if result is None:
                raise RuntimeError(f'integrated ABTB memory-direct leaf unavailable: {path}')
            return result
        def attribute(base, *, parent=False):
            return Bundle(branchType=signal(base + '_branchType', parent=parent),
                rasAction=signal(base + '_rasAction', parent=parent))
        def metadata(base, *, parent=False):
            return Bundle(valid=signal(base + '_valid', parent=parent),
                setIdx=signal(base + '_setIdx', parent=parent), bankMask=signal(base + '_bankMask', parent=parent),
                entries=tuple(Bundle(hit=signal(base + f'_entries_{way}_hit', parent=parent),
                    attribute=attribute(base + f'_entries_{way}_attribute', parent=parent),
                    position=signal(base + f'_entries_{way}_position', parent=parent),
                    targetLowerBits=signal(base + f'_entries_{way}_targetLowerBits', parent=parent)) for way in range(4)))
        def write(bank):
            base = f'banks_{bank}.io_writeResp'
            return Bundle(valid=signal(base + '_valid'), set_index=signal(base + '_bits_setIdx'),
                way=signal(base + '_bits_wayIdx'), reset_counter=signal(base + '_bits_needResetCtr'))
        def replacer(bank):
            base = f'replacers_{bank}.'
            return Bundle(read_valid=signal(base + 'io_readValid'), read_set=signal(base + 'io_readSetIdx'),
                read_mask=tuple(signal(base + f'io_readWayMask_{way}') for way in range(4)),
                write_valid=signal(base + 'io_writeValid'), write_set=signal(base + 'io_writeSetIdx'),
                write_way=signal(base + 'io_writeWayIdx'), replace_set=signal(base + 'io_replaceSetIdx'),
                victim=signal(base + 'io_victimWayIdx'),
                states=tuple(signal(base + f'states.states_{index}') for index in range(64)),
                shadow=tuple(signal(base + f'state_vec_{index}') for index in range(64)))
        abtb = Bundle(enable=signal('io_enable'), t1_fire=signal('t1_fire'),
            feedback=Bundle(valid=agent.ports.training.valid, ready=agent.ports.training.ready,
                bits=agent.ports.training.bits),
            meta1=metadata('io_meta'), meta2=metadata('s2_abtbMeta', parent=True),
            meta3=metadata('s3_abtbMeta', parent=True),
            fast=Bundle(valid=signal('io_fastTrain_valid'), pc=signal('io_fastTrain_bits_startPc_addr'),
                target=signal('io_fastTrain_bits_branch_target_addr'), taken=signal('io_fastTrain_bits_branch_taken'),
                position=signal('io_fastTrain_bits_branch_cfiPosition'),
                branch_type=signal('io_fastTrain_bits_branch_attribute_branchType'),
                ras_action=signal('io_fastTrain_bits_branch_attribute_rasAction'),
                meta=metadata('io_fastTrain_bits_abtbMeta')),
            final=Bundle(valid=signal('s3_valid', parent=True), pc=signal('s3_startPc_dup_1_addr', parent=True),
                taken=signal('s3_taken', parent=True), position=signal('s3_prediction_cfiPosition', parent=True),
                target=signal('s3_prediction_target_addr', parent=True),
                branch_type=signal('s3_prediction_attribute_branchType', parent=True),
                ras_action=signal('s3_prediction_attribute_rasAction', parent=True)),
            capture=Bundle(fire1=signal('s1_fire', parent=True),
                fire2=signal('s2_valid', parent=True),
                pc1=signal('s1_startPc_dup_2_addr', parent=True)),
            writes=tuple(write(bank) for bank in range(4)),
            cells=tuple(signal(f'takenCounter_{bank}_{index}_{way}_value')
                for bank in range(4) for index in range(64) for way in range(4)),
            replacers=tuple(replacer(bank) for bank in range(4)))
        self.binding = PortBinding(dut.clock, Bundle(**dict(self.binding.bits), abtb=abtb), 'bpu.integrated_abtb_observation')
        self.controls = PortBinding(dut.clock, Bundle(reset=dut.reset, abtb=abtb), 'bpu.integrated_abtb_preedge')
        self.control_subscription = None

    def start(self, execution, *, observer=None):
        super().start(execution, observer=observer)
        checker = observer.__self__
        sample_controls = compile_plain(self.controls.bits)
        def capture(event):
            from toffee import Transfer
            checker.capture_controls(Transfer(event=event, value=sample_controls()))
        async def delivered(_):
            pass
        spec = on(DriveStable(self.binding.clock), delivery='lossless', capacity=64, capture=capture)(delivered)
        self.control_subscription = execution.subscribe(spec.bind())
        return self

    async def aclose(self):
        subscription, self.control_subscription = self.control_subscription, None
        if subscription is not None:
            self._execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError):
                    await subscription.task
        await super().aclose()
