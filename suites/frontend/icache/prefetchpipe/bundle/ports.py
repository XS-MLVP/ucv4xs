"""Static signal structure of ICachePrefetchPipe."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toffee import Bundle

from suites.frontend.icache.ports.bindings import PortBinding
from suites.frontend.icache.ports.bindings import bind_bundle


PORTS = 2
WAYS = 4


def _ftq_fields(dut: Any, index: int) -> dict[str, Any]:
    prefix = f"io_fromFtq_bits_req_{index}"
    fields = {
        "startVAddr": getattr(dut, f"{prefix}_startVAddr_addr"),
        "nextLineVAddr": getattr(dut, f"{prefix}_nextLineVAddr_addr"),
        "isCrossLine": getattr(dut, f"{prefix}_isCrossLine"),
        "vSetIdx_0": getattr(dut, f"{prefix}_vSetIdx_0"),
        "vSetIdx_1": getattr(dut, f"{prefix}_vSetIdx_1"),
        "ftqIdx_flag": getattr(dut, f"{prefix}_ftqIdx_flag"),
        "ftqIdx_value": getattr(dut, f"{prefix}_ftqIdx_value"),
    }
    if index == 0:
        fields["isSoftPrefetch"] = dut.io_fromFtq_bits_req_0_isSoftPrefetch
        fields["backendException"] = dut.io_fromFtq_bits_req_0_backendException_value
    return fields


def _meta_fields(dut: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for port in range(PORTS):
        for way in range(WAYS):
            prefix = f"io_metaRead_resp_entries_{port}_{way}"
            fields[f"p{port}_w{way}_valid"] = getattr(dut, f"{prefix}_valid")
            fields[f"p{port}_w{way}_tag"] = getattr(dut, f"{prefix}_bits_meta_phyTag")
            fields[f"p{port}_w{way}_rvc"] = getattr(dut, f"{prefix}_bits_meta_maybeRvcMap")
            fields[f"p{port}_w{way}_code"] = getattr(dut, f"{prefix}_bits_code")
    return fields


def _way_out_fields(dut: Any, port: int) -> dict[str, Any]:
    prefix = f"io_wayLookupWrite_{port}_bits"
    fields = {
        "valid": getattr(dut, f"io_wayLookupWrite_{port}_valid"),
        "ftqIdx_flag": getattr(dut, f"{prefix}_ftqIdx_flag"),
        "ftqIdx_value": getattr(dut, f"{prefix}_ftqIdx_value"),
        "isMmio": getattr(dut, f"{prefix}_entry_isMmio"),
        "itlbPbmt": getattr(dut, f"{prefix}_entry_itlbPbmt"),
        "vSetIdx_0": getattr(dut, f"{prefix}_entry_vSetIdx_0"),
        "vSetIdx_1": getattr(dut, f"{prefix}_entry_vSetIdx_1"),
        "waymask_0": getattr(dut, f"{prefix}_entry_waymask_0"),
        "waymask_1": getattr(dut, f"{prefix}_entry_waymask_1"),
        "pTag": getattr(dut, f"{prefix}_entry_pTag"),
        "rvc_0": getattr(dut, f"{prefix}_entry_maybeRvcMap_0"),
        "rvc_1": getattr(dut, f"{prefix}_entry_maybeRvcMap_1"),
        "code_0": getattr(dut, f"{prefix}_entry_metaCodes_0"),
        "code_1": getattr(dut, f"{prefix}_entry_metaCodes_1"),
    }
    if port == 0:
        fields.update({
            "exception": getattr(dut, f"{prefix}_exceptionEntry_itlbException_value"),
            "gpAddr": getattr(dut, f"{prefix}_exceptionEntry_gpAddr_addr"),
            "vsNonLeaf": getattr(dut, f"{prefix}_exceptionEntry_isForVSnonLeafPTE"),
        })
    return {name: value for name, value in fields.items() if value is not None}


@dataclass(frozen=True, slots=True)
class PrefetchPipePorts:
    ftq: PortBinding
    itlb_resp: PortBinding
    meta_resp: PortBinding
    miss_resp: PortBinding
    pmp_resp: PortBinding
    csr_pf: PortBinding
    flush: PortBinding
    bpu_flush: PortBinding
    meta_ready: PortBinding
    itlb_flush_pipe: Any
    ftq_ready: Any
    itlb_req: PortBinding
    meta_req: PortBinding
    miss_ready: PortBinding
    miss_req: PortBinding
    way: tuple[PortBinding, PortBinding]
    way_ready: tuple[PortBinding, ...]
    pending_itlb_miss: Any
    pmp_req: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "PrefetchPipePorts":
        io = bind_bundle(dut, ("io",), name="prefetchpipe.io").bits
        ftq = {f"r0_{k}": v for k, v in _ftq_fields(dut, 0).items()}
        ftq.update({f"r1_{k}": v for k, v in _ftq_fields(dut, 1).items()})
        ftq["twoPrefetchCase"] = dut.io_fromFtq_bits_twoPrefetchCase_value
        return cls(
            ftq=PortBinding(dut.clock, Bundle(valid=dut.io_fromFtq_valid, **ftq),
                            "prefetchpipe.fromFtq"),
            itlb_resp=PortBinding(
                dut.clock,
                Bundle(
                    miss=dut.io_itlb_resp_bits_miss,
                    paddr=dut.io_itlb_resp_bits_paddr_0,
                    pbmt=dut.io_itlb_resp_bits_pbmt_0,
                    gpaddr=dut.io_itlb_resp_bits_gpaddr_0,
                    pf=dut.io_itlb_resp_bits_excp_0_pf_instr,
                    af=dut.io_itlb_resp_bits_excp_0_af_instr,
                    gpf=dut.io_itlb_resp_bits_excp_0_gpf_instr,
                    vsNonLeaf=dut.io_itlb_resp_bits_isForVSnonLeafPTE,
                ),
                "prefetchpipe.itlb.resp"),
            meta_resp=PortBinding(dut.clock, Bundle(**_meta_fields(dut)),
                                  "prefetchpipe.metaRead.resp"),
            miss_resp=PortBinding(
                dut.clock,
                Bundle(valid=dut.io_missResp_valid,
                       blkPAddr=dut.io_missResp_bits_blkPAddr,
                       vSetIdx=dut.io_missResp_bits_vSetIdx,
                       waymask=dut.io_missResp_bits_waymask,
                       maybeRvcMap=dut.io_missResp_bits_maybeRvcMap,
                       corrupt=dut.io_missResp_bits_corrupt),
                "prefetchpipe.missResp"),
            pmp_resp=PortBinding(dut.clock,
                                 Bundle(instr=dut.io_pmp_resp_instr,
                                        mmio=dut.io_pmp_resp_mmio),
                                 "prefetchpipe.pmp.resp"),
            csr_pf=PortBinding(dut.clock, Bundle(enable=dut.io_csrPfEnable),
                               "prefetchpipe.csrPfEnable"),
            flush=PortBinding(dut.clock, Bundle(flush=dut.io_flush),
                              "prefetchpipe.flush"),
            bpu_flush=PortBinding(
                dut.clock,
                Bundle(s2_valid=dut.io_flushFromBpu_s2_valid,
                       s2_flag=dut.io_flushFromBpu_s2_bits_flag,
                       s2_value=dut.io_flushFromBpu_s2_bits_value,
                       s3_valid=dut.io_flushFromBpu_s3_valid,
                       s3_flag=dut.io_flushFromBpu_s3_bits_flag,
                       s3_value=dut.io_flushFromBpu_s3_bits_value),
                "prefetchpipe.flushFromBpu"),
            meta_ready=PortBinding(dut.clock,
                                   Bundle(ready=dut.io_metaRead_req_ready),
                                   "prefetchpipe.metaRead.req.ready"),
            itlb_flush_pipe=dut.io_itlbFlushPipe,
            ftq_ready=dut.io_fromFtq_ready,
            itlb_req=PortBinding(
                dut.clock,
                Bundle(valid=dut.io_itlb_req_valid,
                       vaddr=dut.io_itlb_req_bits_vaddr,
                       fullva=dut.io_itlb_req_bits_fullva),
                "prefetchpipe.itlb.req"),
            meta_req=PortBinding(
                dut.clock,
                Bundle(valid=dut.io_metaRead_req_valid,
                       isDoubleLine=dut.io_metaRead_req_bits_isDoubleLine,
                       vSetIdx_0=dut.io_metaRead_req_bits_vSetIdx_0,
                       vSetIdx_1=dut.io_metaRead_req_bits_vSetIdx_1),
                "prefetchpipe.metaRead.req"),
            miss_ready=PortBinding(dut.clock, Bundle(ready=dut.io_missReq_ready),
                                   "prefetchpipe.missReq.ready"),
            miss_req=PortBinding(
                dut.clock,
                Bundle(valid=dut.io_missReq_valid,
                       blkPAddr=dut.io_missReq_bits_blkPAddr,
                       vSetIdx=dut.io_missReq_bits_vSetIdx),
                "prefetchpipe.missReq"),
            way=(PortBinding(dut.clock, Bundle(**_way_out_fields(dut, 0)),
                             "prefetchpipe.wayLookupWrite.0"),
                 PortBinding(dut.clock, Bundle(**_way_out_fields(dut, 1)),
                             "prefetchpipe.wayLookupWrite.1")),
            way_ready=tuple(
                PortBinding(dut.clock,
                            Bundle(ready=getattr(dut, name)),
                            f"prefetchpipe.wayLookupWrite.{port}.ready")
                for port, name in ((0, "io_wayLookupWrite_0_ready"),
                                   (1, "io_wayLookupWrite_1_ready"))
                if hasattr(dut, name)),
            pending_itlb_miss=dut.io_perf_pendingItlbMiss,
            pmp_req=PortBinding(dut.clock, Bundle(addr=dut.io_pmp_req_bits_addr),
                                "prefetchpipe.pmp.req"),
        )
