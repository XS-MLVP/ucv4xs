"""Static signal structure of ICacheMainPipe.

Only the ports a module-level test needs are bound. The DUT is the flattened
``io`` of the Scala module; the two fetch requests and the two data-read
responses are exposed as flat key spaces so the agent can drive a request as one
atomic value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toffee import Bundle

from icacheverify.common.bundle.bindings import PortBinding
from icacheverify.common.bundle.bindings import bind_bundle


DATA_BANKS = 8
FETCH_PORTS = 2

# FtqFetchRequest fields that are identical for both fetch requests, plus the
# ones only request 0 carries in the flattened DUT.
_FTQ_COMMON = (
    "vAddr_0_addr", "vAddr_1_addr", "endPosition", "taken",
    "bankSel_0", "bankSel_1", "vSetIdx_0", "vSetIdx_1",
    "ftqIdx_flag", "ftqIdx_value",
)


def _ftq_fields(dut: Any, index: int) -> dict[str, Any]:
    prefix = f"io_fromFtq_bits_req_{index}"
    fields = {name: getattr(dut, f"{prefix}_{name}") for name in _FTQ_COMMON}
    if index == 0:
        fields["hasBackendException"] = dut.io_fromFtq_bits_req_0_hasBackendException
        fields["hasSatpFlush"] = dut.io_fromFtq_bits_req_0_hasSatpFlush
    return fields


def _way_fields(dut: Any, index: int) -> dict[str, Any]:
    prefix = f"io_fromWayLookup_bits_wayLookupInfo_{index}_bits"
    fields = {
        "isMmio": getattr(dut, f"{prefix}_entry_isMmio", None),
        "itlbPbmt": getattr(dut, f"{prefix}_entry_itlbPbmt", None),
        "maybeRvcMap_0": getattr(dut, f"{prefix}_entry_maybeRvcMap_0", None),
        "maybeRvcMap_1": getattr(dut, f"{prefix}_entry_maybeRvcMap_1", None),
        "metaCodes_0": getattr(dut, f"{prefix}_entry_metaCodes_0", None),
        "metaCodes_1": getattr(dut, f"{prefix}_entry_metaCodes_1", None),
        "vSetIdx_0": getattr(dut, f"{prefix}_entry_vSetIdx_0", None),
        "vSetIdx_1": getattr(dut, f"{prefix}_entry_vSetIdx_1", None),
        "waymask_0": getattr(dut, f"{prefix}_entry_waymask_0", None),
        "waymask_1": getattr(dut, f"{prefix}_entry_waymask_1", None),
        "gpAddr_addr": getattr(dut, f"{prefix}_exceptionEntry_gpAddr_addr", None),
        "isForVSnonLeafPTE": getattr(dut, f"{prefix}_exceptionEntry_isForVSnonLeafPTE", None),
        "itlbException_value": getattr(dut, f"{prefix}_exceptionEntry_itlbException_value", None),
    }
    if index == 0:
        fields["pTag"] = dut.io_fromWayLookup_bits_wayLookupInfo_0_bits_entry_pTag
    # Firtool drops leaves the module never reads (request 1 has no pTag and no
    # pbmt of its own: the pipeline uses request 0's values for both).
    return {name: value for name, value in fields.items() if value is not None}


def _data_resp_fields(dut: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for port in range(FETCH_PORTS):
        for bank in range(DATA_BANKS):
            fields[f"d{port}_{bank}"] = getattr(dut, f"io_dataRead_resp_{port}_datas_{bank}")
            fields[f"c{port}_{bank}"] = getattr(dut, f"io_dataRead_resp_{port}_codes_{bank}")
    return fields


@dataclass(frozen=True, slots=True)
class MainPipePorts:
    ftq: PortBinding
    waylookup: PortBinding
    data_ready: PortBinding
    data_resp: PortBinding
    miss_ready: PortBinding
    miss_resp: PortBinding
    pmp_resp: PortBinding
    flush: PortBinding
    bpu_flush: PortBinding
    ecc_enable: PortBinding
    ifu_ready: PortBinding
    ftq_ready: Any
    wl_ready: Any
    data_req: PortBinding
    to_ifu: PortBinding
    miss_req: PortBinding
    replacer_touch: PortBinding
    to_ftq_two: Any
    to_wl_two: Any
    error_valid: Any
    error_paddr: Any
    error_report_to_beu: Any
    perf_pending_miss: Any
    perf_raw_hits: tuple[Any, Any]

    @classmethod
    def bind(cls, dut: Any) -> "MainPipePorts":
        io = bind_bundle(dut, ("io",), name="mainpipe.io").bits

        ftq = {f"r0_{key}": value for key, value in _ftq_fields(dut, 0).items()}
        ftq.update({f"r1_{key}": value for key, value in _ftq_fields(dut, 1).items()})
        # req0.valid is not a port: the FTQ protocol guarantees request 0 is
        # valid whenever io.fromFtq.valid is asserted.
        ftq["r1_valid"] = dut.io_fromFtq_bits_req_1_valid

        way = {f"r0_{key}": value for key, value in _way_fields(dut, 0).items()}
        way.update({f"r1_{key}": value for key, value in _way_fields(dut, 1).items()})
        way["r1_valid"] = dut.io_fromWayLookup_bits_wayLookupInfo_1_valid

        data_req = {
            "valid": dut.io_dataRead_req_valid,
            "valid_1": dut.io_dataRead_req_bits_1_valid,
        }
        for port in range(FETCH_PORTS):
            for field in ("bankSel", "vSetIdx", "waymask"):
                for line in range(2):
                    data_req[f"{field}{port}_{line}"] = getattr(
                        dut, f"io_dataRead_req_bits_{port}_bits_{field}_{line}")

        return cls(
            ftq=PortBinding(dut.clock,
                            Bundle(valid=dut.io_fromFtq_valid, **ftq),
                            "mainpipe.fromFtq"),
            waylookup=PortBinding(
                dut.clock,
                Bundle(valid=dut.io_fromWayLookup_valid, **way),
                "mainpipe.fromWayLookup"),
            data_ready=PortBinding(dut.clock,
                                   Bundle(ready=dut.io_dataRead_req_ready),
                                   "mainpipe.dataRead.ready"),
            data_resp=PortBinding(dut.clock, Bundle(**_data_resp_fields(dut)),
                                  "mainpipe.dataRead.resp"),
            miss_ready=PortBinding(dut.clock,
                                   Bundle(ready=dut.io_missReq_ready),
                                   "mainpipe.missReq.ready"),
            miss_resp=PortBinding(
                dut.clock,
                Bundle(valid=dut.io_missResp_valid,
                       blkPAddr=dut.io_missResp_bits_blkPAddr,
                       vSetIdx=dut.io_missResp_bits_vSetIdx,
                       data=dut.io_missResp_bits_data,
                       maybeRvcMap=dut.io_missResp_bits_maybeRvcMap,
                       corrupt=dut.io_missResp_bits_corrupt,
                       denied=dut.io_missResp_bits_denied),
                "mainpipe.missResp"),
            pmp_resp=PortBinding(dut.clock,
                                 Bundle(instr=dut.io_pmp_resp_instr,
                                        mmio=dut.io_pmp_resp_mmio),
                                 "mainpipe.pmp.resp"),
            flush=PortBinding(dut.clock, Bundle(flush=dut.io_flush), "mainpipe.flush"),
            bpu_flush=PortBinding(
                dut.clock,
                Bundle(s2_valid=dut.io_flushFromBpu_s2_valid,
                       s2_flag=dut.io_flushFromBpu_s2_bits_flag,
                       s2_value=dut.io_flushFromBpu_s2_bits_value,
                       s3_valid=dut.io_flushFromBpu_s3_valid,
                       s3_flag=dut.io_flushFromBpu_s3_bits_flag,
                       s3_value=dut.io_flushFromBpu_s3_bits_value),
                "mainpipe.flushFromBpu"),
            ecc_enable=PortBinding(dut.clock, Bundle(ecc=io.eccEnable),
                                   "mainpipe.eccEnable"),
            ifu_ready=PortBinding(dut.clock, Bundle(ready=dut.io_toIfu_req_ready),
                                  "mainpipe.toIfu.ready"),
            ftq_ready=dut.io_fromFtq_ready,
            wl_ready=dut.io_fromWayLookup_ready,
            data_req=PortBinding(dut.clock, Bundle(**data_req),
                                 "mainpipe.dataRead.req"),
            to_ifu=PortBinding(
                dut.clock,
                Bundle(
                    valid=dut.io_toIfu_req_valid,
                    firstRange=dut.io_toIfu_req_bits_firstRange,
                    totalRange=dut.io_toIfu_req_bits_totalRange,
                    maybeRvcMap=dut.io_toIfu_req_bits_maybeRvcMap,
                    info0_startVAddr=dut.io_toIfu_req_bits_info_0_startVAddr_addr,
                    info0_ftqIdx_flag=dut.io_toIfu_req_bits_info_0_ftqIdx_flag,
                    info0_ftqIdx_value=dut.io_toIfu_req_bits_info_0_ftqIdx_value,
                    info0_takenValid=dut.io_toIfu_req_bits_info_0_takenCfiOffset_valid,
                    info0_takenBits=dut.io_toIfu_req_bits_info_0_takenCfiOffset_bits,
                    info0_size=dut.io_toIfu_req_bits_info_0_size,
                    info0_data=dut.io_toIfu_req_bits_info_0_data,
                    info0_crossLine=dut.io_toIfu_req_bits_info_0_perf_isCrossLine,
                    info0_exception=dut.io_toIfu_req_bits_info_0_icacheMeta_exception_value,
                    info0_pmpMmio=dut.io_toIfu_req_bits_info_0_icacheMeta_pmpMmio,
                    info0_backendException=dut.io_toIfu_req_bits_info_0_icacheMeta_isBackendException,
                    info0_hasSatpFlush=dut.io_toIfu_req_bits_info_0_icacheMeta_hasSatpFlush,
                    info0_vsNonLeaf=dut.io_toIfu_req_bits_info_0_icacheMeta_isForVSnonLeafPTE,
                    info0_pbmt=dut.io_toIfu_req_bits_info_0_icacheMeta_itlbPbmt,
                    info0_paddr=dut.io_toIfu_req_bits_info_0_icacheMeta_pAddr_addr,
                    info0_gpaddr=dut.io_toIfu_req_bits_info_0_icacheMeta_gpAddr_addr,
                    info1_valid=dut.io_toIfu_req_bits_info_1_valid,
                    info1_startVAddr=dut.io_toIfu_req_bits_info_1_startVAddr_addr,
                    info1_ftqIdx_flag=dut.io_toIfu_req_bits_info_1_ftqIdx_flag,
                    info1_ftqIdx_value=dut.io_toIfu_req_bits_info_1_ftqIdx_value,
                    info1_takenValid=dut.io_toIfu_req_bits_info_1_takenCfiOffset_valid,
                    info1_takenBits=dut.io_toIfu_req_bits_info_1_takenCfiOffset_bits,
                    info1_size=dut.io_toIfu_req_bits_info_1_size,
                    info1_data=dut.io_toIfu_req_bits_info_1_data,
                    info1_exception=dut.io_toIfu_req_bits_info_1_icacheMeta_exception_value,
                    info1_vsNonLeaf=dut.io_toIfu_req_bits_info_1_icacheMeta_isForVSnonLeafPTE,
                    info1_gpaddr=dut.io_toIfu_req_bits_info_1_icacheMeta_gpAddr_addr,
                    corrupt00=dut.io_toIfu_corrupt_0_0,
                    corrupt01=dut.io_toIfu_corrupt_0_1,
                    corrupt10=dut.io_toIfu_corrupt_1_0,
                    corrupt11=dut.io_toIfu_corrupt_1_1,
                ),
                "mainpipe.toIfu",
            ),
            miss_req=PortBinding(
                dut.clock,
                Bundle(valid=dut.io_missReq_valid,
                       blkPAddr=dut.io_missReq_bits_blkPAddr,
                       vSetIdx=dut.io_missReq_bits_vSetIdx),
                "mainpipe.missReq"),
            replacer_touch=PortBinding(
                dut.clock,
                Bundle(
                    valid00=dut.io_replacerTouch_req_0_0_valid,
                    vset00=dut.io_replacerTouch_req_0_0_bits_vSetIdx,
                    way00=dut.io_replacerTouch_req_0_0_bits_way,
                    valid01=dut.io_replacerTouch_req_0_1_valid,
                    vset01=dut.io_replacerTouch_req_0_1_bits_vSetIdx,
                    way01=dut.io_replacerTouch_req_0_1_bits_way,
                    valid10=dut.io_replacerTouch_req_1_0_valid,
                    vset10=dut.io_replacerTouch_req_1_0_bits_vSetIdx,
                    way10=dut.io_replacerTouch_req_1_0_bits_way,
                    valid11=dut.io_replacerTouch_req_1_1_valid,
                    vset11=dut.io_replacerTouch_req_1_1_bits_vSetIdx,
                    way11=dut.io_replacerTouch_req_1_1_bits_way,
                ),
                "mainpipe.replacerTouch"),
            to_ftq_two=dut.io_toFtq_realTwoFetchValid,
            to_wl_two=dut.io_toWayLookup_realTwoFetchValid,
            error_valid=dut.io_error_valid,
            error_paddr=dut.io_error_bits_paddr,
            error_report_to_beu=dut.io_error_bits_report_to_beu,
            perf_pending_miss=dut.io_perf_pendingMiss,
            perf_raw_hits=(dut.io_perf_rawHits_0, dut.io_perf_rawHits_1),
        )
