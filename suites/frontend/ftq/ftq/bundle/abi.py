"""Fixed DefaultConfig Ftq leaf ABI, not discovery-driven expected widths.

The type/geometry sources are frontend/Bundles.scala, ftq/Bundles.scala,
bpu/*/Bundles.scala and DefaultConfig: 10 prediction results, 2 MainBTB banks,
4 main ways plus output-only victim metadata, 8 resolve/commit lanes,
50-bit Pc byte domain, 51-bit guarded target and the explicit Pc projections.
This is transport shape, not a golden model of predictor algorithms.
"""


def resolve_meta():
    fields = dict(commonHR_bw=8, commonHR_ghr=16, commonHR_imli=8, commonHR_valid=1,
                  phr_phrLowBits=13, phr_phrPtr_value=10)
    fields.update({f'ittage_{name}': bits for name, bits in dict(
        allocate_bits=3, allocate_valid=1, altDiffers=1, altProvider_bits=3,
        altProvider_valid=1, altProviderCnt_value=2, altProviderTarget_addr=49,
        provider_bits=3, provider_valid=1, providerCnt_value=2,
        providerTarget_addr=49, providerUsefulCnt_value=1).items()})
    for bank in range(2):
        for way in range(5):
            attrs = dict(counter_value=2, position=5, rawHit=1)
            if way < 4:
                attrs.update(attribute_branchType=2, attribute_rasAction=2)
            fields.update((f'mbtb_entries_{bank}_{way}_{name}', bits) for name, bits in attrs.items())
    for index in range(10):
        for name, bits in dict(altConf=1, altOrBasePred=1, hasAlt=1, hasProvider=1,
                              providerTableIdx=3, providerTakenCtr_value=3,
                              providerUsefulCtr_value=2, providerWayIdx=2, useProvider=1).items():
            fields[f'tage_entries_{index}_{name}'] = bits
        for name in ('scBWTakenVec', 'scBiasTakenVec', 'scGlobalTakenVec', 'scImliTakenVec', 'scPathTakenVec'):
            fields[f'sc_debug_{name}_{index}'] = 1
        for name, bits in dict(scBiasLowerBits=2, scPred=1, sumAboveThres=1,
                              tageCtr=3, tagePred=1, tagePredValid=1, useScPred=1).items():
            fields[f'sc_{name}_{index}'] = bits
    for name in ('predBiasIdx', 'predImliIdx'):
        fields['sc_debug_' + name] = 7
    for name in ('predBWIdx', 'predGlobalIdx', 'predPathIdx'):
        for index in range(2):
            fields[f'sc_debug_{name}_{index}'] = 7
    return fields


def redirect_meta(*, with_target):
    fields = dict(commonHRMeta_bw=8, commonHRMeta_ghr=16, commonHRMeta_imli=8,
                  phr_phrLowBits=13, phr_phrPtr_value=10,
                  ras_nos_flag=1, ras_nos_value=5, ras_sctr=3, ras_ssp=4,
                  ras_tosr_flag=1, ras_tosr_value=5, ras_tosw_flag=1, ras_tosw_value=5)
    if with_target:
        fields['ras_topRetAddr_addr'] = 50
    for index in range(10):
        fields[f'commonHRMeta_attribute_{index}_branchType'] = 2
        fields[f'commonHRMeta_hitMask_{index}'] = 1
        fields[f'commonHRMeta_position_{index}'] = 5
    return fields


def metadata_inputs():
    fields = dict(commitMeta_ras_ssp=4, commitMeta_ras_tosw_flag=1, commitMeta_ras_tosw_value=5)
    fields.update(('resolveMeta_' + name, bits) for name, bits in resolve_meta().items())
    fields.update(('redirectMeta_' + name, bits) for name, bits in redirect_meta(with_target=True).items())
    return fields


def validate_metadata(fields):
    widths = metadata_inputs()
    for key, value in fields.items():
        if key not in widths:
            raise ValueError(f'Ftq metadata has unknown field {key!r}')
        if type(value) is not int or not 0 <= value < (1 << widths[key]):
            raise ValueError(f'Ftq metadata {key} must fit {widths[key]} bits')


def layout():
    inputs, outputs = {}, {}

    def group(destination, prefix, fields):
        for name, bits in fields.items():
            physical = prefix + name
            if physical in destination:
                raise ValueError(f'duplicate FTQ ABI leaf {physical}')
            destination[physical] = bits

    group(inputs, '', dict(reset=1))
    group(inputs, 'io_fromBpu_prediction_', dict(valid=1, bits_startPc_addr=50, bits_taken=1,
        bits_endPosition=5, bits_s2Override=1, bits_s3Override=1))
    for stage in ('s2', 's3'):
        group(inputs, f'io_fromBpu_{stage}FtqPtr_', dict(flag=1, value=6))
    group(inputs, 'io_fromBpu_meta_', dict(valid=1))
    group(inputs, 'io_fromBpu_meta_bits_', metadata_inputs())
    redirect = dict(valid=1, bits_ftqIdx_flag=1, bits_ftqIdx_value=6, bits_pc=50, bits_taken=1,
        bits_ftqOffset=5, bits_isRVC=1, bits_attribute_branchType=2, bits_attribute_rasAction=2, bits_target=51)
    group(inputs, 'io_fromBackend_redirect_', redirect | dict(bits_level=1, bits_backendIPF=1,
        bits_backendIGPF=1, bits_backendIAF=1, bits_satpFlush=1, bits_debugIsCtrl=1, bits_debugIsMemVio=1))
    group(inputs, 'io_fromIfu_wbRedirect_', redirect | dict(bits_canTrain=1))
    for lane in range(3):
        group(inputs, f'io_fromBackend_resolve_{lane}_', dict(valid=1, bits_ftqIdx_flag=1,
            bits_ftqIdx_value=6, bits_ftqOffset=5, bits_pc_addr=49, bits_target_addr=49,
            bits_taken=1, bits_mispredict=1, bits_attribute_branchType=2, bits_attribute_rasAction=2))
    for lane in range(8):
        group(inputs, f'io_fromBackend_callRetCommit_{lane}_', dict(valid=1, bits_ftqPtr_value=6, bits_rasAction=2))
    group(inputs, 'io_fromBackend_commit_', dict(valid=1, bits_flag=1, bits_value=6))
    group(inputs, 'io_fromBackend_ftqIdxAhead_', dict(valid=1, bits_flag=1, bits_value=6))
    group(inputs, '', dict(io_toICache_toPrefetch_ready=1, io_toICache_toMainPipe_ready=1,
                          io_toBpu_train_ready=1, io_fromICache_fromMainPipe_realTwoFetchValid=1))
    group(outputs, '', dict(io_fromBpu_prediction_ready=1))
    group(outputs, 'io_toBpu_bpuPtr_', dict(flag=1, value=6))
    group(outputs, 'io_toBackend_', dict(wen=1, ftqIdx=6, startPc_addr=50))
    group(outputs, 'io_toBpu_train_', dict(valid=1))
    for copy, count in enumerate((1, 1, 2)):
        for lane in range(count):
            group(outputs, f'io_toBpu_train_bits_startPcVec_dup_{copy}_{lane}_', dict(addr=49))
    group(outputs, 'io_toBpu_train_bits_meta_', resolve_meta())
    for lane in range(8):
        group(outputs, f'io_toBpu_train_bits_branches_{lane}_', dict(valid=1, bits_target_addr=49,
            bits_taken=1, bits_cfiPosition=5, bits_attribute_branchType=2, bits_attribute_rasAction=2, bits_mispredict=1))
    group(outputs, 'io_toBpu_commit_', dict(valid=1, bits_attribute_rasAction=2,
        bits_meta_ras_ssp=4, bits_meta_ras_tosw_flag=1, bits_meta_ras_tosw_value=5))
    group(outputs, 'io_toBpu_redirect_', dict(valid=1, bits_cfiPc_addr=49, bits_target_addr=50,
        bits_taken=1, bits_attribute_branchType=2, bits_attribute_rasAction=2))
    group(outputs, 'io_toBpu_redirect_bits_meta_', redirect_meta(with_target=False))
    # TwoPrefetchCase is one-hot with zero permitted (Conflict), not binary.
    group(outputs, 'io_toICache_toPrefetch_', dict(valid=1, bits_twoPrefetchCase_value=4))
    group(outputs, 'io_toICache_toMainPipe_', dict(valid=1))
    for lane in range(2):
        group(outputs, f'io_toICache_toPrefetch_bits_req_{lane}_', dict(startVAddr_addr=50,
            nextLineVAddr_addr=50, vSetIdx_0=8, vSetIdx_1=8, isCrossLine=1, ftqIdx_flag=1, ftqIdx_value=6))
        group(outputs, f'io_toICache_toMainPipe_bits_req_{lane}_', dict(vAddr_0_addr=50,
            vAddr_1_addr=50, vSetIdx_0=8, vSetIdx_1=8, taken=1, endPosition=5,
            bankSel_0=8, bankSel_1=8, ftqIdx_flag=1, ftqIdx_value=6))
    group(outputs, 'io_toICache_toPrefetch_bits_req_0_', dict(backendException_value=3))
    group(outputs, 'io_toICache_toMainPipe_bits_req_0_', dict(hasBackendException=1, hasSatpFlush=1))
    group(outputs, 'io_toICache_toMainPipe_bits_req_1_', dict(valid=1))
    for stage in ('s2', 's3'):
        group(outputs, f'io_toICache_flushFromBpu_{stage}_', dict(valid=1, bits_flag=1, bits_value=6))
    group(outputs, 'io_toIfu_flushFromBpu_s3_', dict(valid=1, bits_flag=1, bits_value=6))
    group(outputs, '', dict(io_toICache_redirectFlush=1, io_toIfu_redirect_valid=1))
    group(outputs, 'io_toIfu_topdownInfo_reasons_', {str(index): 1 for index in (2, 3, 5, 6, 7, 8, 9)})
    group(outputs, 'io_backendRedirectTopdown_', {name: 1 for name in
        ('backendRedirect', 'controlFlowRedirect', 'memoryViolationRedirect', 'tageMissBubble', 'ittageMissBubble', 'rasMissBubble')})
    return inputs, outputs


def validate(dut):
    inputs, outputs = layout()
    if set(dut.input_names()) != set(inputs) or dut.output_names() != set(outputs):
        raise ValueError('Ftq full physical schema mismatch: ' + repr(dict(
            inputs=sorted(set(dut.input_names()) ^ set(inputs)), outputs=sorted(dut.output_names() ^ set(outputs)))))
    for output, expected in ((False, inputs | {'clock': 1}), (True, outputs)):
        for name, bits in expected.items():
            signal = getattr(dut.dut, name)
            if (max(1, int(signal.W())) != bits or bool(signal.IsOutIO()) != output
                    or (not output and not signal.IsInIO())):
                raise ValueError(f'Ftq {name}: expected {bits}-bit ' + ('output' if output else 'input'))
    return inputs, outputs
