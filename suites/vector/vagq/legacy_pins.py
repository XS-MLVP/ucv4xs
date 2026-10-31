"""Central mapping from logical pin fields to generated RTL names.

Functional tests use this schema; only this module spells physical names.
"""


class Pins:
    """Logical field names; ``io`` adds the generated RTL prefix."""

    def io(self, suffix: str) -> str:
        return "io_" + suffix

    p_addrUop_0_ready = "io_addrUop_0_ready"
    p_addrUop_0_valid = "io_addrUop_0_valid"
    p_addrUop_1_ready = "io_addrUop_1_ready"
    p_in_bits_issueMask = "io_in_bits_issueMask"
    p_in_bits_pc = "io_in_bits_pc"
    p_in_bits_pdest = "io_in_bits_pdest"
    p_in_bits_vaddr = "io_in_bits_vaddr"
    p_in_valid = "io_in_valid"
    p_issueLda_0_ready = "io_issueLda_0_ready"
    p_lduReq_0_bits_meta_byteOffset = "io_lduReq_0_bits_meta_byteOffset"
    p_lduReq_0_bits_meta_elemIdx = "io_lduReq_0_bits_meta_elemIdx"
    p_lduReq_0_bits_meta_entryIdx = "io_lduReq_0_bits_meta_entryIdx"
    p_lduReq_0_bits_meta_valid = "io_lduReq_0_bits_meta_valid"
    p_lduReq_0_bits_req_ctrl_fuType = "io_lduReq_0_bits_req_ctrl_fuType"
    p_lduReq_0_bits_req_ctrl_vecWen = "io_lduReq_0_bits_req_ctrl_vecWen"
    p_lduReq_0_bits_req_data_pc = "io_lduReq_0_bits_req_data_pc"
    p_lduReq_0_bits_req_data_src_0 = "io_lduReq_0_bits_req_data_src_0"
    p_lduReq_0_valid = "io_lduReq_0_valid"
    p_lduReq_1_bits_meta_entryIdx = "io_lduReq_1_bits_meta_entryIdx"
    p_lduReq_1_valid = "io_lduReq_1_valid"
    p_lduReq_2_valid = "io_lduReq_2_valid"
    p_lsqEmptyReq_0_ = "io_lsqEmptyReq_0_"
    p_robWriteback_bits_entryIdx = "io_robWriteback_bits_entryIdx"
    p_robWriteback_bits_exception = "io_robWriteback_bits_exception"
    p_robWriteback_bits_faultVstart = "io_robWriteback_bits_faultVstart"
    p_robWriteback_bits_robIdx_value = "io_robWriteback_bits_robIdx_value"
    p_robWriteback_valid = "io_robWriteback_valid"
    p_staReq_0_bits_meta_byteOffset = "io_staReq_0_bits_meta_byteOffset"
    p_staReq_0_bits_meta_dataMask = "io_staReq_0_bits_meta_dataMask"
    p_staReq_0_bits_meta_elemIdx = "io_staReq_0_bits_meta_elemIdx"
    p_staReq_0_bits_meta_entryIdx = "io_staReq_0_bits_meta_entryIdx"
    p_staReq_0_bits_meta_valid = "io_staReq_0_bits_meta_valid"
    p_staReq_0_bits_req_data_src_0 = "io_staReq_0_bits_req_data_src_0"
    p_staReq_0_bits_req_robIdx_value = "io_staReq_0_bits_req_robIdx_value"
    p_staReq_0_valid = "io_staReq_0_valid"
    p_staReq_1_valid = "io_staReq_1_valid"
    p_vagqLsuReq_0_ready = "io_vagqLsuReq_0_ready"
    p_vagqStdData_0_valid = "io_vagqStdData_0_valid"
    p_vagqStdData_1_bits_data = "io_vagqStdData_1_bits_data"
    p_vagqStdData_1_valid = "io_vagqStdData_1_valid"
    p_vagqStoreDataReq_0_ready = "io_vagqStoreDataReq_0_ready"
    p_vagqStoreDataReq_1_ready = "io_vagqStoreDataReq_1_ready"
    p_vpWakeUp_valid = "io_vpWakeUp_valid"
    p_vrfReadReq_bits_entryIdx = "io_vrfReadReq_bits_entryIdx"
    p_vrfReadReq_bits_robIdx_value = "io_vrfReadReq_bits_robIdx_value"
    p_vrfReadReq_valid = "io_vrfReadReq_valid"
    p_vrfWriteReq_bits_mask = "io_vrfWriteReq_bits_mask"
    p_vrfWriteReq_bits_pdest = "io_vrfWriteReq_bits_pdest"
    p_vrfWriteReq_valid = "io_vrfWriteReq_valid"


P = Pins()
