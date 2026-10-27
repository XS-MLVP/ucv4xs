"""Read-only core IO and diagnostic projections; observations never seed tokens."""
from toffee import Bundle

from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal, memory_signal_names
from bpuverify.bpu.model.pipeline import ENABLES
from bpuverify.bpu.bundle.tage_semantic import HISTORY_PORTS
from bpuverify.bpu.bundle.tage_semantic import META_FIELDS
from bpuverify.bpu.bundle.ahead import ahead_bundle
from bpuverify.bpu.bundle.early_direction import early_direction_bundle


def pipeline_binding(agent,*,with_tage=False,with_ahead=False,with_early_direction=False,with_ittage=False,with_sc=False,with_ras=False):
    anchor, = [name for name in memory_signal_names(agent.dut) if name.endswith('.tage.io_enable')]
    prefix = anchor.removeprefix('TOP.').removesuffix('tage.io_enable')
    signal = lambda field: memory_signal(agent.dut, prefix + field)
    from bpuverify.bpu.bundle.statistical import history_bundle, metadata_bundle, statistical_bundle
    def ras_metadata(base, *, redirect=False):
        return Bundle(ssp=signal(base+'ssp'),tosw=Bundle(flag=signal(base+'tosw_flag'),value=signal(base+'tosw_value')),
            **(dict(sctr=signal(base+'sctr')) if redirect else {}))
    def return_stack():
        return Bundle(public=Bundle(top=signal('ras.io_topRetAddr_addr'),
            redirect_meta=ras_metadata('ras.io_redirectMeta_',redirect=True),commit_meta=ras_metadata('ras.io_commitMeta_')),
            retained=Bundle(head=signal('ras.RasStack.nsp'),cells=tuple(Bundle(
                address=signal(f'ras.RasStack.commitStack_{slot}_retAddr_addr'),
                counter=signal(f'ras.RasStack.commitStack_{slot}_ctr')) for slot in range(8))),
            micro=Bundle(usable=signal('uras.io_specOut_isCanUse'),target=signal('uras.io_specOut_retTarget_addr')))
    def metadata(base):
        return Bundle(phrPtr=Bundle(flag=signal(base + 'phrPtr_flag'), value=signal(base + 'phrPtr_value')),
                      phrLowBits=signal(base + 'phrLowBits'))
    def main_metadata(base):
        return tuple(tuple(Bundle(**{key:signal(f'{base}entries_{align}_{way}_'+field)
            for key,field in (('hit','rawHit'),('position','position'),('kind','attribute_branchType'),
                ('action','attribute_rasAction'),('counter','counter_value'))}) for way in range(2)) for align in range(2))
    tage_metadata = lambda base:tuple(Bundle(**{field:signal(f'{base}entries_{slot}_{field}')
        for field in META_FIELDS}) for slot in range(4))
    def ittage_metadata(base):
        from bpuverify.bpu.bundle.ittage_semantic import META_FIELDS as INDIRECT_FIELDS
        return Bundle(valid=signal(base+'valid'),**{field:signal(base+field) for field in INDIRECT_FIELDS},
            **{name:Bundle(valid=signal(base+name+'_valid'),bits=signal(base+name+'_bits'))
                for name in ('provider','altProvider','allocate')})
    def indirect_read():
        from bpuverify.bpu.bundle.ittage_semantic import FOLD_PORTS
        return Bundle(pc=signal('ittage.s1_startPc_addr'),
            folds=tuple(tuple(signal(f'ittage.io_s1_foldedPhr_hist_{index}_foldedHist')
                for index in ports) for ports in FOLD_PORTS))
    training = Bundle(valid=signal('io_fromFtq_train_valid'), ready=signal('io_fromFtq_train_ready'),
        pc=signal('io_fromFtq_train_bits_startPcVec_dup_0_0_addr'),
        history=metadata('io_fromFtq_train_bits_meta_phr_'),
        main=main_metadata('io_fromFtq_train_bits_meta_mbtb_'),
        **(dict(tage=tage_metadata('io_fromFtq_train_bits_meta_tage_')) if with_tage else {}),
        **(dict(ittage=ittage_metadata('io_fromFtq_train_bits_meta_ittage_')) if with_ittage else {}),
        **(dict(sc=metadata_bundle(signal,'io_fromFtq_train_bits_meta_sc_'),
            common=history_bundle(signal,'io_fromFtq_train_bits_meta_commonHR_')) if with_sc else {}),
        branches=tuple(Bundle(**{key:signal(f'io_fromFtq_train_bits_branches_{slot}_' + field)
            for key, field in (('valid','valid'),('position','bits_cfiPosition'),('target','bits_target_addr'),
                ('taken','bits_taken'),('kind','bits_attribute_branchType'),('action','bits_attribute_rasAction'),
                ('mispredict','bits_mispredict'))}) for slot in range(8)))
    inputs = Bundle(reset=signal('reset'), reset_vector=signal('io_resetVector_addr'),
        commit_valid=signal('io_fromFtq_commit_valid'),
        **(dict(commit=Bundle(action=signal('io_fromFtq_commit_bits_attribute_rasAction'),
            branch_type=signal('io_fromFtq_commit_bits_attribute_branchType'),
            meta=ras_metadata('io_fromFtq_commit_bits_meta_ras_'))) if with_ras else {}),
        prediction_ready=signal('io_toFtq_prediction_ready'), metadata_ready=signal('io_toFtq_meta_ready'),
        enabled=tuple(signal(f'io_ctrl_{name}Enable') for name in ENABLES),
        initialization=tuple(signal(f'{name}.io_sramResetDone') for name in ('abtb','utage','mbtb','tage','sc','ittage')),
        redirect=Bundle(valid=signal('io_fromFtq_redirect_valid'),
            pc=signal('io_fromFtq_redirect_bits_cfiPc_addr'), target=signal('io_fromFtq_redirect_bits_target_addr'),
            taken=signal('io_fromFtq_redirect_bits_taken'),
            kind=signal('io_fromFtq_redirect_bits_attribute_branchType'),action=signal('io_fromFtq_redirect_bits_attribute_rasAction'),
            history=metadata('io_fromFtq_redirect_bits_meta_phr_'),
            **(dict(ras=ras_metadata('io_fromFtq_redirect_bits_meta_ras_',redirect=True)) if with_ras else {})),
        training=training)
    observed = Bundle(valids=tuple(signal(f's{stage}_valid') for stage in (1,2,3)),
        micro_confidence=tuple(signal(f'ubtb.entries_{entry}_usefulCnt_value') for entry in range(32)),
        # S2/S3 fire and S3 flush collapse to aliases in the generated top.
        # Observe the real consumer IO/redirect net, not a fabricated shadow.
        fires=(signal('s0_fire'), signal('s1_fire'), signal('commonHR.io_stageCtrl_s2_fire'),
               signal('commonHR.io_stageCtrl_s3_fire')),
        flushes=(signal('s1_flush'), signal('s2_flush'), signal('io_fromFtq_redirect_valid')),
        pcs=tuple(signal(f's{stage}_startPc_dup_{duplicate}_addr') for stage,duplicate in ((1,2),(2,2),(3,1))),
        initialized=signal('sramResetDone'),
        enabled=tuple(signal(f'csrCtrl_delay.REG_1_{name}Enable') for name in ENABLES),
        lookup_folds=tuple(signal(f'phr.io_s0_foldedPhr_hist_{index}_foldedHist') for index in HISTORY_PORTS),
        choices=tuple(Bundle(taken=signal('s1_prediction_taken' if stage == 1 else f's{stage}_taken'),
            target=signal(f's{stage}_prediction_target_addr'), position=signal(f's{stage}_prediction_cfiPosition'),
            kind=signal(f's{stage}_prediction_attribute_branchType'), action=signal(f's{stage}_prediction_attribute_rasAction'))
            for stage in (1,2,3)),
        repair2=signal('s2_override'), repair3=signal('s3_override'),
        prediction=Bundle(valid=signal('io_toFtq_prediction_valid'),
            pc=signal('io_toFtq_prediction_bits_startPc_addr'), target=signal('io_toFtq_prediction_bits_target_addr'),
            taken=signal('io_toFtq_prediction_bits_taken'), position=signal('io_toFtq_prediction_bits_endPosition'),
            repair2=signal('io_toFtq_prediction_bits_s2Override'), repair3=signal('io_toFtq_prediction_bits_s3Override')),
        metadata=Bundle(valid=signal('io_toFtq_meta_valid'), pc=signal('io_toFtq_perfMeta_startPc_addr'),
            history=metadata('io_toFtq_meta_bits_redirectMeta_phr_'),
            main=main_metadata('io_toFtq_meta_bits_resolveMeta_mbtb_'),
            **(dict(tage=tage_metadata('io_toFtq_meta_bits_resolveMeta_tage_')) if with_tage else {}),
            **(dict(ittage=ittage_metadata('io_toFtq_meta_bits_resolveMeta_ittage_')) if with_ittage else {}),
            **(dict(sc=metadata_bundle(signal,'io_toFtq_meta_bits_resolveMeta_sc_'),
                common=history_bundle(signal,'io_toFtq_meta_bits_resolveMeta_commonHR_')) if with_sc else {}),
            **(dict(source=signal('io_toFtq_perfMeta_bpSource_s1Source')) if with_ahead else {})),
        **(dict(return_stack=return_stack(),ras_metadata=Bundle(
            redirect=ras_metadata('io_toFtq_meta_bits_redirectMeta_ras_',redirect=True),
            commit=ras_metadata('io_toFtq_meta_bits_commitMeta_ras_'))) if with_ras else {}),
        **(dict(ahead=ahead_bundle(signal)) if with_ahead else {}),
        **(dict(early_direction=early_direction_bundle(signal)) if with_early_direction else {}),
        **(dict(statistical=statistical_bundle(signal)) if with_sc else {}),
        **(dict(indirect_read=indirect_read(),indirect_random=tuple(
            signal(f'ittage.s2_allocLFSR_prng.state_{bit}') for bit in range(15))) if with_ittage else {}))
    return PortBinding(agent.dut.clock, Bundle(inputs=inputs, observed=observed), 'bpu.semantic-pipeline')
