"""Memory-direct component interface; no SRAM/counter state as model input."""
from toffee import Bundle

from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal, memory_signal_names


META_FIELDS = ('altDiffers', 'providerCnt_value', 'providerUsefulCnt_value',
               'providerTarget_addr', 'altProviderCnt_value', 'altProviderTarget_addr')
FOLD_PORTS = ((0, 0, 0), (4, 4, 3), (12, 11, 10))


def semantic_binding(agent):
    anchor, = [name for name in memory_signal_names(agent.dut) if name.endswith('.ittage.io_enable')]
    prefix = anchor.removeprefix('TOP.').removesuffix('io_enable')
    signal = lambda leaf: memory_signal(agent.dut, prefix + leaf)

    def context(port):
        return tuple(Bundle(index=signal(f'io_{port}_hist_{index}_foldedHist'),
                            tag=signal(f'io_{port}_hist_{tag}_foldedHist'),
                            secondary=signal(f'io_{port}_hist_{secondary}_foldedHist'))
                     for index, tag, secondary in FOLD_PORTS)

    def metadata(port, *, valid=False):
        mapping = {field: signal(port + field) for field in META_FIELDS}
        for name in ('provider', 'altProvider', 'allocate'):
            mapping[name] = Bundle(valid=signal(port + name + '_valid'), bits=signal(port + name + '_bits'))
        if valid:
            mapping['valid'] = signal(port + 'valid')
        return Bundle(**mapping)

    inputs = Bundle(reset=signal('reset'), enabled=signal('io_enable'), ready=signal('io_sramResetDone'),
        accept=signal('io_stageCtrl_s0_fire'), access=signal('io_stageCtrl_s1_fire'),
        select=signal('io_stageCtrl_s2_fire'), pc=signal('io_startPc_addr'),
        context=context('s1_foldedPhr'), train_valid=signal('io_stageCtrl_t0_fire'),
        train_pc=signal('io_train_startPcVec_dup_0_0_addr'), train_context=context('trainFoldedPhr'),
        train_meta=metadata('io_train_meta_ittage_'),
        branches=tuple(Bundle(valid=signal(f'io_train_branches_{index}_valid'),
            taken=signal(f'io_train_branches_{index}_bits_taken'),
            branch_type=signal(f'io_train_branches_{index}_bits_attribute_branchType'),
            ras_action=signal(f'io_train_branches_{index}_bits_attribute_rasAction'),
            target=signal(f'io_train_branches_{index}_bits_target_addr'),
            mispredict=signal(f'io_train_branches_{index}_bits_mispredict')) for index in range(8)))
    root = prefix.removesuffix('ittage.')
    parent = lambda leaf: memory_signal(agent.dut, root + leaf)
    outputs = Bundle(enabled=signal('io_enable'), consume=signal('io_stageCtrl_s3_fire'),
        prediction=Bundle(hit=signal('io_prediction_hit'), target=signal('io_prediction_target_addr'),
                          meta=metadata('io_meta_', valid=True)),
        baseline=Bundle(overridden=parent('s3_s2Override'),
                        early_target=parent('s3_s1Prediction_target_addr'),
                        corrected_target=parent('s3_s2Prediction_target_addr')))
    return PortBinding(agent.dut.clock, Bundle(inputs=inputs, outputs=outputs), 'bpu.ittage.semantic-interface')
