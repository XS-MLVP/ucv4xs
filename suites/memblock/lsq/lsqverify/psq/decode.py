"""Independent decoding of all actually sampled PSQ public inputs."""
from lsqverify.forward.types import Query, Translation
from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import RobPtr
from .types import Address, Attributes, Data, Inputs, SecondPage


def decode(pins):
    def sq(prefix):
        return SqPtr(bool(pins[prefix + "first_flag"]), bool(pins[prefix + "second_flag"]), pins[prefix + "value"])
    addresses, attributes, data, pages, queries, translations = [], [], [], [], [], []
    for lane in range(2):
        p = f"io_fromStoreUnit_storeAddrIn_{lane}_"
        addresses.append(Address(bool(pins[p + "valid"]), pins[p + "bits_uop_sqIdx_value"], pins[p + "bits_uop_fuOpType"],
                                 pins[p + "bits_vaddr"], pins[p + "bits_paddr"], pins[p + "bits_size"], bool(pins[p + "bits_tlbMiss"]),
                                 bool(pins[p + "bits_isHyper"]), bool(pins[p + "bits_isUnalign"]), bool(pins[p + "bits_cross16Byte"]), bool(pins[p + "bits_isLastRequest"])))
        p = f"io_fromStoreUnit_storeAddrInRe_{lane}_"
        attributes.append(Attributes(*(bool(pins[p + key]) for key in ("nc", "mmio", "memBackTypeMM", "hasException", "isLastRequest"))))
        p = f"io_storeDataIn_{lane}_"
        data.append(Data(bool(pins[p + "valid"]), pins[p + "bits_sqIdx_value"], pins[p + "bits_fuOpType"], pins[p + "bits_data"]))
        p = f"io_fromStoreUnit_unalignQueueReq_{lane}_"
        pages.append(SecondPage(bool(pins[p + "valid"]), sq(p + "bits_sqIdx_"), pins[p + "bits_paddr"]))
    for lane in range(3):
        p = f"io_forward_{lane}_"
        queries.append(Query(bool(pins[p + "s0Req_valid"]), pins[p + "s0Req_bits_vaddr"], sq(p + "s0Req_bits_sqIdx_"), pins[p + "s0Req_bits_size"],
                             bool(pins[p + "s0Req_bits_loadWaitBit"]), bool(pins[p + "s0Req_bits_loadWaitStrict"]), sq(p + "s0Req_bits_waitSqIdx_")))
        translations.append(Translation(pins[p + "s1Req_paddr"], bool(pins[p + "s1Kill"])))
    prefix = "io_fromVirtualStoreQueue_"
    return Inputs(tuple(addresses), tuple(attributes), tuple(data), tuple(pages), tuple(queries), tuple(translations),
                  sq(prefix + "physicalQueueEnqPtr_"), sq(prefix + "retiredPtr_"), bool(pins[prefix + "preCommitPtr_valid"]), sq(prefix + "preCommitPtr_bits_"),
                  bool(pins[prefix + "redirectPtr_valid"]), sq(prefix + "redirectPtr_bits_"),
                  RobPtr(bool(pins[prefix + "headRobIdx_flag"]), pins[prefix + "headRobIdx_value"], bool(pins[prefix + "headRobIdx_isFormer"])),
                  tuple(bool(pins[f"io_writeToSbuffer_req_{lane}_ready"]) for lane in range(2)), bool(pins["io_sbufferCtrl_resp_empty"]),
                  bool(pins["io_toDCache_req_ready"]), bool(pins["io_toDCache_resp_valid"]), bool(pins["io_toDCache_resp_bits_denied"]), bool(pins["io_toDCache_resp_bits_corrupt"]),
                  bool(pins["io_toUncacheBuffer_req_ready"]), bool(pins["io_toUncacheBuffer_idResp_valid"]), bool(pins["io_toUncacheBuffer_idResp_bits_is2lq"]),
                  bool(pins["io_toUncacheBuffer_resp_valid"]), bool(pins["io_writeBack_ready"]), bool(pins["reset"]))
