"""bpuverify.bpu.monitor.phr.observation components."""
from bpuverify.common.model.configuration import *


from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import memory_signal_names
from toffee import Bundle
from toffee import RisingEdge
from toffee import on
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.monitor.cycle import CycleMonitor
from bpuverify.bpu.bundle.values import _plain


class BpuPhrMonitor(CycleMonitor):
    def __init__(self, agent):
        dut = agent.dut
        names = tuple(memory_signal_names(dut))
        matches = [name for name in names if name.endswith('.phr.phrPtr_value')]
        if len(matches) != 1:
            raise RuntimeError(f'unique PHR state binding required: {matches!r}')
        prefix = matches[0].split('.', 1)[1].removesuffix('phrPtr_value')

        def signal(field):
            value = memory_signal(dut, prefix + field)
            if value is None:
                raise RuntimeError(f'PHR memory-direct signal unavailable: {prefix + field}')
            return value

        def pointer(base):
            return Bundle(flag=signal(base + '_flag'), value=signal(base + '_value'))

        def metadata(base):
            return Bundle(pointer=pointer(base + '_phrPtr'), low=signal(base + '_phrLowBits'))

        def prediction(base):
            return Bundle(taken=signal(base + '_taken'), position=signal(base + '_cfiPosition'),
                target=signal(base + '_target_addr'))

        def folds(base):
            return tuple(signal(f'{base}_hist_{index}_foldedHist') for index in range(len(PHR_FOLDS)))

        boundary = Bundle(stall=signal('io_train_s0_stall'),
            fire0=signal('io_train_stageCtrl_s0_fire'), fire1=signal('io_train_stageCtrl_s1_fire'),
            fire2=signal('io_train_stageCtrl_s2_fire'),
            redirect=Bundle(valid=signal('io_train_redirect_valid'), taken=signal('io_train_redirect_bits_taken'),
                cfi_pc=signal('io_train_redirect_bits_cfiPc_addr'), target=signal('io_train_redirect_bits_target_addr'),
                meta=metadata('io_train_redirect_bits_meta_phr')),
            s1=Bundle(valid=signal('io_s1Train_valid'), start_pc=signal('io_s1Train_startPc_addr'),
                prediction=prediction('io_s1Train_prediction')),
            s2=Bundle(valid=signal('io_train_s2_overrideValid'), start_pc=signal('io_train_s2_startPc_addr'),
                prediction=prediction('io_train_s2_prediction'), meta=metadata('io_train_s2_phrMeta')),
            s3=Bundle(valid=signal('io_train_s3_overrideValid'), start_pc=signal('io_train_s3_startPc_addr'),
                prediction=prediction('io_train_s3_prediction'), meta=metadata('io_train_s3_phrMeta')))
        state = Bundle(cells=tuple(signal(f'phr_{index}') for index in range(PHR_STORAGE_BITS)), pointer=pointer('phrPtr'),
            s1_pointer=pointer('s1_phrPtr'), pending=Bundle(valid=signal('pendingValid'),
                taken=signal('pendingTaken'), low=signal('pendingLowBits'), shift=signal('pendingShiftBits')),
            fold0_reg=folds('s0_foldedPhrReg'), fold1=folds('s1_foldedPhrReg'),
            fold2=folds('s2_foldedPhrReg'), fold3=folds('s3_foldedPhrReg'))
        self.prefix = prefix
        self.top_payload = agent.ports.redirect.bits
        self.top_metadata = agent.ports.meta.bits
        self.top_prediction = agent.ports.prediction.bits
        parent_prefix = prefix.removesuffix('phr.')
        def parent_signal(field):
            value = memory_signal(dut, parent_prefix + field)
            if value is None:
                raise RuntimeError(f'BPU parent memory-direct signal unavailable: {parent_prefix + field}')
            return value
        parent = Bundle(s1_valid=parent_signal('s1_fire'), s1_pc=parent_signal('s1_startPc_dup_2_addr'),
            s1_taken=parent_signal('s1_prediction_taken'), s1_position=parent_signal('s1_prediction_cfiPosition'),
            s1_target=parent_signal('s1_prediction_target_addr'), s2_valid=parent_signal('s2_override'),
            s2_pc=parent_signal('s2_startPc_dup_2_addr'), s2_taken=parent_signal('s2_taken'),
            s2_target=parent_signal('s2_prediction_target_addr'), s3_valid=parent_signal('s3_override'),
            s3_pc=parent_signal('s3_startPc_dup_1_addr'), s3_taken=parent_signal('s3_taken'),
            s3_target=parent_signal('s3_prediction_target_addr'))
        pipeline = Bundle(s1_valid=parent_signal('s1_valid'), s2_valid=parent_signal('s2_valid'),
            s3_valid=parent_signal('s3_valid'), s1_flush=parent_signal('s1_flush'),
            s2_flush=parent_signal('s2_flush'))
        super().__init__(PortBinding(dut.clock, Bundle(reset=dut.reset, boundary=boundary, state=state,
            parent=parent, pipeline=pipeline, phr_meta=metadata('io_phrMeta'), top_meta_valid=agent.ports.meta.valid,
            top_prediction_valid=agent.ports.prediction.valid, top_prediction_ready=agent.ports.prediction.ready,
            top_redirect_valid=agent.ports.redirect.valid), 'bpu.phr_observation'), decoder=self._decode)

    def start(self, execution, *, observer=None):
        if observer is None:
            return super().start(execution)
        if self._subscription is not None:
            raise RuntimeError('monitor is already started')
        if execution.reactor is None:
            raise RuntimeError('monitor requires an active Execution')

        def capture(event):
            # Process this immutable snapshot before any resolved cycle waiter
            # resumes. Delayed subscription delivery would make a driver react
            # to yesterday's S1 acceptance when the legacy streams are absent.
            # The observer only compares/records; it never writes hardware.
            observer(self.sample_at(event))

        async def delivered(_):
            pass

        spec = on(RisingEdge(self.binding.clock), delivery='lossless',
                  capacity=self.capacity, capture=capture)(delivered)
        self._subscription = execution.subscribe(spec.bind())
        self._execution = execution
        return self

    def _decode(self, snapshot):
        row = _plain(snapshot)
        valid = row.pop('top_redirect_valid')
        row['public_redirect'] = dict(valid=valid, bits=_plain(self.top_payload.sample()) if valid else None)
        valid = row.pop('top_meta_valid')
        bits = _plain(self.top_metadata.sample()) if valid else None
        row['public_meta'] = dict(valid=valid, phr=None if bits is None else bits['redirect']['phr'], bits=bits)
        valid = row.pop('top_prediction_valid')
        row['public_prediction'] = dict(valid=valid, ready=row.pop('top_prediction_ready'),
            bits=_plain(self.top_prediction.sample()) if valid else None)
        return row
