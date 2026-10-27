"""Read-only TAGE component public IO; never an SRAM/selector-state oracle."""
from toffee import Bundle

from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal, memory_signal_names


META_FIELDS = ('hasProvider', 'hasAlt', 'useProvider', 'providerTableIdx', 'providerWayIdx',
               'providerTakenCtr_value', 'providerUsefulCtr_value', 'altOrBasePred', 'altConf')
HISTORY_PORTS = (2, 5, 6, 13, 14, 15, 16, 17, 18)


def semantic_binding(agent):
    anchor, = [name for name in memory_signal_names(agent.dut) if name.endswith('.tage.io_enable')]
    prefix = anchor.removeprefix('TOP.').removesuffix('io_enable')
    signal = lambda field: memory_signal(agent.dut, prefix + field)
    metadata = lambda base: Bundle(**{field: signal(base + field) for field in META_FIELDS})
    # The emitted module exposes exactly the folds consumed by these tables;
    # unused aggregate leaves are removed by RTL elaboration, not by tracing.
    history = lambda base: tuple(Bundle(foldedHist=signal(f'{base}_hist_{index}_foldedHist')) for index in HISTORY_PORTS)
    vector = lambda base: tuple(Bundle(valid=signal(f'{base}_{slot}_valid'), bits=signal(f'{base}_{slot}_bits'))
                                for slot in range(4))
    bases = Bundle(
        s1_positions=tuple(signal(f'io_fromMainBtb_s1_positions_{slot}') for slot in range(4)),
        baseConf=tuple(signal(f'io_fromMainBtb_baseConf_{slot}') for slot in range(4)),
        result=tuple(Bundle(valid=signal(f'io_fromMainBtb_result_{slot}_valid'), bits=Bundle(
            taken=signal(f'io_fromMainBtb_result_{slot}_bits_taken')))
            for slot in range(4)))
    lookup = Bundle(start_pc=signal('io_startPc_addr'), s0_fire=signal('io_stageCtrl_s0_fire'),
        s1_fire=signal('io_stageCtrl_s1_fire'), history=history('io_fromPhr_foldedPathHist'), main_btb=bases)
    train = Bundle(start_pc=signal('io_train_startPcVec_dup_0_0_addr'),
        history=history('io_fromPhr_foldedPathHistForTrain'),
        mbtb_meta=tuple(tuple(Bundle(rawHit=signal(f'io_train_meta_mbtb_entries_{bank}_{way}_rawHit'),
            position=signal(f'io_train_meta_mbtb_entries_{bank}_{way}_position'),
            counter_value=signal(f'io_train_meta_mbtb_entries_{bank}_{way}_counter_value'))
            for way in range(2)) for bank in range(2)),
        tage_meta=tuple(metadata(f'io_train_meta_tage_entries_{slot}_') for slot in range(4)),
        branches=tuple(Bundle(**{key: signal(f'io_train_branches_{slot}_' + suffix) for key, suffix in (
            ('valid','valid'),('taken','bits_taken'),('position','bits_cfiPosition'),
            ('branch_type','bits_attribute_branchType'),('mispredict','bits_mispredict'))}) for slot in range(8)))
    correction, fast = vector('io_prediction_takenVec'), vector('io_prediction_fastTakenVec')
    sc = tuple(Bundle(valid=signal(f'io_toSc_providerTakenCtrVec_{slot}_valid'),
        bits_value=signal(f'io_toSc_providerTakenCtrVec_{slot}_bits_value')) for slot in range(4))
    prediction = Bundle(taken_vec=correction, meta_vec=tuple(metadata(f'io_meta_entries_{slot}_') for slot in range(4)),
                        provider_counter_valid_vec=tuple(entry.valid for entry in sc))
    return PortBinding(agent.dut.clock, Bundle(
        inputs=Bundle(reset=signal('reset'), enabled=signal('io_enable'), ready=signal('io_sramResetDone'),
                      lookup=lookup, train_valid=signal('io_stageCtrl_t0_fire'), train=train),
        outputs=Bundle(enabled=signal('io_enable'), bases=lookup, fast=fast, sc=sc, prediction=prediction)),
        'bpu.tage.semantic-component')
