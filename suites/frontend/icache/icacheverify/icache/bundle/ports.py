"""Signal structure of the whole ICache DUT.

The DUT is the flattened ``ICacheImp``: the inner pipes are not visible, so the
binding exposes exactly the chip-level interface - FTQ, IFU, ITLB, PMP, the
TileLink memory client, the TileLink ECC-control register slave - plus WFI,
``fencei`` and the redirect/flush inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from toffee import Bundle

from icacheverify.common.bundle.bindings import PortBinding


def _ftq_main_fields(dut: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for index in range(2):
        prefix = f"io_fromFtq_toMainPipe_bits_req_{index}"
        common = {
            "vAddr_0_addr": f"{prefix}_vAddr_0_addr",
            "vAddr_1_addr": f"{prefix}_vAddr_1_addr",
            "endPosition": f"{prefix}_endPosition",
            "taken": f"{prefix}_taken",
            "bankSel_0": f"{prefix}_bankSel_0",
            "bankSel_1": f"{prefix}_bankSel_1",
            "vSetIdx_0": f"{prefix}_vSetIdx_0",
            "vSetIdx_1": f"{prefix}_vSetIdx_1",
            "ftqIdx_flag": f"{prefix}_ftqIdx_flag",
            "ftqIdx_value": f"{prefix}_ftqIdx_value",
        }
        for name, attribute in common.items():
            fields[f"r{index}_{name}"] = getattr(dut, attribute)
    fields["r0_hasBackendException"] = dut.io_fromFtq_toMainPipe_bits_req_0_hasBackendException
    fields["r0_hasSatpFlush"] = dut.io_fromFtq_toMainPipe_bits_req_0_hasSatpFlush
    fields["r1_valid"] = dut.io_fromFtq_toMainPipe_bits_req_1_valid
    return fields


def _ftq_pref_fields(dut: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for index in range(2):
        prefix = f"io_fromFtq_toPrefetch_bits_req_{index}"
        for name in ("startVAddr_addr", "nextLineVAddr_addr", "vSetIdx_0",
                     "vSetIdx_1", "isCrossLine", "ftqIdx_flag", "ftqIdx_value"):
            fields[f"r{index}_{name}"] = getattr(dut, f"{prefix}_{name}")
    fields["r0_backendException"] = dut.io_fromFtq_toPrefetch_bits_req_0_backendException_value
    fields["twoPrefetchCase"] = dut.io_fromFtq_toPrefetch_bits_twoPrefetchCase_value
    return fields


def _ifu_fields(dut: Any) -> dict[str, Any]:
    prefix = "io_toIfu_req_bits"
    fields = {
        "valid": dut.io_toIfu_req_valid,
        "firstRange": dut.io_toIfu_req_bits_firstRange,
        "totalRange": dut.io_toIfu_req_bits_totalRange,
        "maybeRvcMap": dut.io_toIfu_req_bits_maybeRvcMap,
        "corrupt00": dut.io_toIfu_corrupt_0_0,
        "corrupt01": dut.io_toIfu_corrupt_0_1,
        "corrupt10": dut.io_toIfu_corrupt_1_0,
        "corrupt11": dut.io_toIfu_corrupt_1_1,
        "missBubble": dut.io_toIfu_topdown_iCacheMissBubble,
        "itlbBubble": dut.io_toIfu_topdown_itlbMissBubble,
        "perfHit0": dut.io_toIfu_perf_hits_0,
        "perfHit1": dut.io_toIfu_perf_hits_1,
        "perfDoubleLine": dut.io_toIfu_perf_isDoubleLine,
    }
    for index in range(2):
        p = f"{prefix}_info_{index}"
        fields[f"info{index}_valid"] = (
            dut.io_toIfu_req_bits_info_1_valid if index == 1 else None)
        fields[f"info{index}_startVAddr"] = getattr(dut, f"{p}_startVAddr_addr")
        fields[f"info{index}_ftqIdx_flag"] = getattr(dut, f"{p}_ftqIdx_flag")
        fields[f"info{index}_ftqIdx_value"] = getattr(dut, f"{p}_ftqIdx_value")
        fields[f"info{index}_takenValid"] = getattr(dut, f"{p}_takenCfiOffset_valid")
        fields[f"info{index}_takenBits"] = getattr(dut, f"{p}_takenCfiOffset_bits")
        fields[f"info{index}_size"] = getattr(dut, f"{p}_size")
        fields[f"info{index}_data"] = getattr(dut, f"{p}_data")
        fields[f"info{index}_exception"] = getattr(dut, f"{p}_icacheMeta_exception_value")
        fields[f"info{index}_pmpMmio"] = getattr(dut, f"{p}_icacheMeta_pmpMmio", None)
        fields[f"info{index}_backendException"] = getattr(
            dut, f"{p}_icacheMeta_isBackendException", None)
        fields[f"info{index}_hasSatpFlush"] = getattr(
            dut, f"{p}_icacheMeta_hasSatpFlush", None)
        fields[f"info{index}_vsNonLeaf"] = getattr(
            dut, f"{p}_icacheMeta_isForVSnonLeafPTE")
        fields[f"info{index}_pbmt"] = getattr(dut, f"{p}_icacheMeta_itlbPbmt", None)
        fields[f"info{index}_paddr"] = getattr(dut, f"{p}_icacheMeta_pAddr_addr", None)
        fields[f"info{index}_gpaddr"] = getattr(
            dut, f"{p}_icacheMeta_gpAddr_addr", None)
    return {name: value for name, value in fields.items() if value is not None}


_BIST_INPUTS = ("array", "all", "req", "writeen", "be", "addr",
                "indata", "readen", "addr_rd")
_BIST_OUTPUTS = ("ack", "outdata")


def _bist_children() -> list[int]:
    return list(range(10))


def _bist_attribute(child: int, leaf: str) -> str:
    prefix = "boreChildrenBd_bore" if child == 0 else f"boreChildrenBd_bore_{child}"
    return f"{prefix}_{leaf}"


def _bist_fields(dut: Any, outputs: bool) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for child in _bist_children():
        for leaf in (_BIST_OUTPUTS if outputs else _BIST_INPUTS):
            attribute = _bist_attribute(child, leaf)
            fields[f"c{child}_{leaf}"] = getattr(dut, attribute)
    return fields


def _itlb_fields(dut: Any) -> dict[str, Any]:
    return {
        "miss": dut.io_itlb_resp_bits_miss,
        "paddr": dut.io_itlb_resp_bits_paddr_0,
        "pbmt": dut.io_itlb_resp_bits_pbmt_0,
        "gpaddr": dut.io_itlb_resp_bits_gpaddr_0,
        "pf": dut.io_itlb_resp_bits_excp_0_pf_instr,
        "af": dut.io_itlb_resp_bits_excp_0_af_instr,
        "gpf": dut.io_itlb_resp_bits_excp_0_gpf_instr,
        "vsNonLeaf": dut.io_itlb_resp_bits_isForVSnonLeafPTE,
    }


@dataclass(frozen=True, slots=True)
class ICachePorts:
    # FTQ
    ftq_main: PortBinding
    ftq_main_ready: Any
    ftq_pref: PortBinding
    ftq_pref_ready: Any
    flush_from_bpu: PortBinding
    redirect_flush: PortBinding
    csr_pf: PortBinding
    fencei: PortBinding
    wfi_req: PortBinding
    wfi_safe: Any
    # IFU
    ifu: PortBinding
    ifu_ready: PortBinding
    # ITLB
    itlb_req: PortBinding
    itlb_resp: PortBinding
    itlb_flush_pipe: Any
    # PMP
    pmp0_req: PortBinding
    pmp0_resp: PortBinding
    pmp1_req: PortBinding
    pmp1_resp: PortBinding
    # software prefetch
    soft_prefetch: PortBinding
    # backend error
    error: PortBinding
    to_ftq_two: Any
    # TileLink memory client
    mem_a: PortBinding
    mem_a_ready: PortBinding
    mem_d: PortBinding
    # TileLink ECC control register slave
    ctrl_a: PortBinding
    ctrl_a_ready: Any
    ctrl_d: PortBinding
    ctrl_d_ready: PortBinding
    # SRAM BIST child interface (memory built-in self test)
    bist_in: PortBinding
    bist_out: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "ICachePorts":
        return cls(
            ftq_main=PortBinding(
                dut.clock,
                Bundle(valid=dut.io_fromFtq_toMainPipe_valid,
                       **_ftq_main_fields(dut)),
                "icache.fromFtq.toMainPipe"),
            ftq_main_ready=dut.io_fromFtq_toMainPipe_ready,
            ftq_pref=PortBinding(
                dut.clock,
                Bundle(valid=dut.io_fromFtq_toPrefetch_valid,
                       **_ftq_pref_fields(dut)),
                "icache.fromFtq.toPrefetch"),
            ftq_pref_ready=dut.io_fromFtq_toPrefetch_ready,
            flush_from_bpu=PortBinding(
                dut.clock,
                Bundle(
                    s2_valid=dut.io_fromFtq_flushFromBpu_s2_valid,
                    s2_flag=dut.io_fromFtq_flushFromBpu_s2_bits_flag,
                    s2_value=dut.io_fromFtq_flushFromBpu_s2_bits_value,
                    s3_valid=dut.io_fromFtq_flushFromBpu_s3_valid,
                    s3_flag=dut.io_fromFtq_flushFromBpu_s3_bits_flag,
                    s3_value=dut.io_fromFtq_flushFromBpu_s3_bits_value,
                ),
                "icache.fromFtq.flushFromBpu"),
            redirect_flush=PortBinding(
                dut.clock, Bundle(flush=dut.io_fromFtq_redirectFlush),
                "icache.fromFtq.redirectFlush"),
            csr_pf=PortBinding(dut.clock, Bundle(enable=dut.io_csrPfEnable),
                               "icache.csrPfEnable"),
            fencei=PortBinding(dut.clock, Bundle(fencei=dut.io_fencei),
                               "icache.fencei"),
            wfi_req=PortBinding(dut.clock, Bundle(wfiReq=dut.io_wfi_wfiReq),
                                "icache.wfi"),
            wfi_safe=dut.io_wfi_wfiSafe,
            ifu=PortBinding(dut.clock, Bundle(**_ifu_fields(dut)),
                            "icache.toIfu"),
            ifu_ready=PortBinding(dut.clock, Bundle(ready=dut.io_toIfu_req_ready),
                                  "icache.toIfu.ready"),
            itlb_req=PortBinding(
                dut.clock,
                Bundle(valid=dut.io_itlb_req_valid,
                       vaddr=dut.io_itlb_req_bits_vaddr,
                       fullva=dut.io_itlb_req_bits_fullva),
                "icache.itlb.req"),
            itlb_resp=PortBinding(dut.clock, Bundle(**_itlb_fields(dut)),
                                  "icache.itlb.resp"),
            itlb_flush_pipe=dut.io_itlbFlushPipe,
            pmp0_req=PortBinding(dut.clock,
                                 Bundle(addr=dut.io_pmp_0_req_bits_addr),
                                 "icache.pmp.0.req"),
            pmp0_resp=PortBinding(
                dut.clock,
                Bundle(instr=dut.io_pmp_0_resp_instr,
                       mmio=dut.io_pmp_0_resp_mmio),
                "icache.pmp.0.resp"),
            pmp1_req=PortBinding(dut.clock,
                                 Bundle(addr=dut.io_pmp_1_req_bits_addr),
                                 "icache.pmp.1.req"),
            pmp1_resp=PortBinding(
                dut.clock,
                Bundle(instr=dut.io_pmp_1_resp_instr,
                       mmio=dut.io_pmp_1_resp_mmio),
                "icache.pmp.1.resp"),
            soft_prefetch=PortBinding(
                dut.clock,
                Bundle(
                    valid0=dut.io_softPrefetchReq_0_valid,
                    vaddr0=dut.io_softPrefetchReq_0_bits_vaddr,
                    valid1=dut.io_softPrefetchReq_1_valid,
                    vaddr1=dut.io_softPrefetchReq_1_bits_vaddr,
                    valid2=dut.io_softPrefetchReq_2_valid,
                    vaddr2=dut.io_softPrefetchReq_2_bits_vaddr,
                ),
                "icache.softPrefetchReq"),
            error=PortBinding(
                dut.clock,
                Bundle(valid=dut.io_error_valid,
                       paddr=dut.io_error_bits_paddr,
                       report_to_beu=dut.io_error_bits_report_to_beu),
                "icache.error"),
            to_ftq_two=dut.io_toFtq_fromMainPipe_realTwoFetchValid,
            mem_a=PortBinding(
                dut.clock,
                Bundle(valid=dut.auto_client_out_a_valid,
                       address=dut.auto_client_out_a_bits_address,
                       source=dut.auto_client_out_a_bits_source,
                       user_alias=dut.auto_client_out_a_bits_user_alias),
                "icache.mem.a"),
            mem_a_ready=PortBinding(dut.clock,
                                    Bundle(ready=dut.auto_client_out_a_ready),
                                    "icache.mem.a.ready"),
            mem_d=PortBinding(
                dut.clock,
                Bundle(valid=dut.auto_client_out_d_valid,
                       opcode=dut.auto_client_out_d_bits_opcode,
                       source=dut.auto_client_out_d_bits_source,
                       data=dut.auto_client_out_d_bits_data,
                       corrupt=dut.auto_client_out_d_bits_corrupt,
                       denied=dut.auto_client_out_d_bits_denied),
                "icache.mem.d"),
            ctrl_a=PortBinding(
                dut.clock,
                Bundle(valid=dut.auto_ctrlUnitOpt_in_a_valid,
                       opcode=dut.auto_ctrlUnitOpt_in_a_bits_opcode,
                       size=dut.auto_ctrlUnitOpt_in_a_bits_size,
                       source=dut.auto_ctrlUnitOpt_in_a_bits_source,
                       address=dut.auto_ctrlUnitOpt_in_a_bits_address,
                       mask=dut.auto_ctrlUnitOpt_in_a_bits_mask,
                       data=dut.auto_ctrlUnitOpt_in_a_bits_data),
                "icache.ctrl.a"),
            ctrl_a_ready=dut.auto_ctrlUnitOpt_in_a_ready,
            ctrl_d=PortBinding(
                dut.clock,
                Bundle(valid=dut.auto_ctrlUnitOpt_in_d_valid,
                       opcode=dut.auto_ctrlUnitOpt_in_d_bits_opcode,
                       size=dut.auto_ctrlUnitOpt_in_d_bits_size,
                       source=dut.auto_ctrlUnitOpt_in_d_bits_source,
                       data=dut.auto_ctrlUnitOpt_in_d_bits_data),
                "icache.ctrl.d"),
            ctrl_d_ready=PortBinding(dut.clock,
                                     Bundle(ready=dut.auto_ctrlUnitOpt_in_d_ready),
                                     "icache.ctrl.d.ready"),
            bist_in=PortBinding(dut.clock, Bundle(**_bist_fields(dut, False)),
                                "icache.bist.in"),
            bist_out=PortBinding(dut.clock, Bundle(**_bist_fields(dut, True)),
                                 "icache.bist.out"),
        )
