"""Central mapping from logical pin fields to generated RTL names.

Functional tests use this schema; only this module spells physical names.
"""


class Pins:
    """Logical field names; ``io`` adds the generated RTL prefix."""

    def io(self, suffix: str) -> str:
        return "io_" + suffix

    p_fromICache_req_bits_info_0_startVAddr_addr = "io_fromICache_req_bits_info_0_startVAddr_addr"
    p_fromICache_req_ready = "io_fromICache_req_ready"
    p_ill = "io_ill"
    p_out_bits = "io_out_bits"
    p_req_ready = "io_req_ready"
    p_resp_bits_exception_value = "io_resp_bits_exception_value"
    p_resp_bits_needResend = "io_resp_bits_needResend"
    p_resp_bits_uncacheData = "io_resp_bits_uncacheData"
    p_resp_firstEndIsHalfRvi = "io_resp_firstEndIsHalfRvi"
    p_resp_stage2Out_checkerRedirect_bits_attribute_branchType = "io_resp_stage2Out_checkerRedirect_bits_attribute_branchType"
    p_resp_stage2Out_checkerRedirect_bits_attribute_rasAction = "io_resp_stage2Out_checkerRedirect_bits_attribute_rasAction"
    p_resp_stage2Out_checkerRedirect_bits_blockSel = "io_resp_stage2Out_checkerRedirect_bits_blockSel"
    p_resp_stage2Out_checkerRedirect_bits_endOffset = "io_resp_stage2Out_checkerRedirect_bits_endOffset"
    p_resp_stage2Out_checkerRedirect_bits_invalidTaken = "io_resp_stage2Out_checkerRedirect_bits_invalidTaken"
    p_resp_stage2Out_checkerRedirect_bits_isCrossBlockInstr = "io_resp_stage2Out_checkerRedirect_bits_isCrossBlockInstr"
    p_resp_stage2Out_checkerRedirect_bits_isRVC = "io_resp_stage2Out_checkerRedirect_bits_isRVC"
    p_resp_stage2Out_checkerRedirect_bits_notCfiTaken = "io_resp_stage2Out_checkerRedirect_bits_notCfiTaken"
    p_resp_stage2Out_checkerRedirect_bits_taken = "io_resp_stage2Out_checkerRedirect_bits_taken"
    p_resp_stage2Out_checkerRedirect_bits_target_addr = "io_resp_stage2Out_checkerRedirect_bits_target_addr"
    p_resp_stage2Out_checkerRedirect_valid = "io_resp_stage2Out_checkerRedirect_valid"
    p_resp_totalEndIsHalfRvi = "io_resp_totalEndIsHalfRvi"
    p_resp_valid = "io_resp_valid"
    p_toBackend_gpAddrMem_waddr = "io_toBackend_gpAddrMem_waddr"
    p_toBackend_gpAddrMem_wdata_gpaddr = "io_toBackend_gpAddrMem_wdata_gpaddr"
    p_toBackend_gpAddrMem_wdata_isForVSnonLeafPTE = "io_toBackend_gpAddrMem_wdata_isForVSnonLeafPTE"
    p_toBackend_gpAddrMem_wen = "io_toBackend_gpAddrMem_wen"
    p_toFtq_wbRedirect_bits_attribute_branchType = "io_toFtq_wbRedirect_bits_attribute_branchType"
    p_toFtq_wbRedirect_bits_attribute_rasAction = "io_toFtq_wbRedirect_bits_attribute_rasAction"
    p_toFtq_wbRedirect_bits_canTrain = "io_toFtq_wbRedirect_bits_canTrain"
    p_toFtq_wbRedirect_bits_ftqIdx_flag = "io_toFtq_wbRedirect_bits_ftqIdx_flag"
    p_toFtq_wbRedirect_bits_ftqIdx_value = "io_toFtq_wbRedirect_bits_ftqIdx_value"
    p_toFtq_wbRedirect_bits_ftqOffset = "io_toFtq_wbRedirect_bits_ftqOffset"
    p_toFtq_wbRedirect_bits_isRVC = "io_toFtq_wbRedirect_bits_isRVC"
    p_toFtq_wbRedirect_bits_pc = "io_toFtq_wbRedirect_bits_pc"
    p_toFtq_wbRedirect_bits_taken = "io_toFtq_wbRedirect_bits_taken"
    p_toFtq_wbRedirect_bits_target = "io_toFtq_wbRedirect_bits_target"
    p_toFtq_wbRedirect_valid = "io_toFtq_wbRedirect_valid"
    p_toIBuffer_bits_enqEnable = "io_toIBuffer_bits_enqEnable"
    p_toIBuffer_bits_exceptionCrossPage = "io_toIBuffer_bits_exceptionCrossPage"
    p_toIBuffer_bits_exceptionMask = "io_toIBuffer_bits_exceptionMask"
    p_toIBuffer_bits_exceptionType_value = "io_toIBuffer_bits_exceptionType_value"
    p_toIBuffer_bits_foldpc_0 = "io_toIBuffer_bits_foldpc_0"
    p_toIBuffer_bits_hasSatpFlush = "io_toIBuffer_bits_hasSatpFlush"
    p_toIBuffer_bits_isBackendException = "io_toIBuffer_bits_isBackendException"
    p_toIBuffer_bits_prevInstrCount = "io_toIBuffer_bits_prevInstrCount"
    p_toIBuffer_bits_valid = "io_toIBuffer_bits_valid"
    p_toIBuffer_valid = "io_toIBuffer_valid"
    p_toUncache_req_bits_addr_addr = "io_toUncache_req_bits_addr_addr"
    p_toUncache_req_bits_memBackTypeMM = "io_toUncache_req_bits_memBackTypeMM"
    p_toUncache_req_bits_memPageTypeNC = "io_toUncache_req_bits_memPageTypeNC"
    p_toUncache_req_valid = "io_toUncache_req_valid"


P = Pins()
