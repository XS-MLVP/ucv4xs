"""FTQ monitor decoders: public outputs become typed observations."""

from __future__ import annotations

from types import SimpleNamespace

from suites.frontend.ftq.ftq.bundle.ports import FtqPorts
from suites.frontend.ftq.ftq.transaction.types import BackendWrite
from suites.frontend.ftq.ftq.transaction.types import CommitEvent
from suites.frontend.ftq.ftq.transaction.types import FetchRequest
from suites.frontend.ftq.ftq.transaction.types import FlushEvent
from suites.frontend.ftq.ftq.transaction.types import Owner
from suites.frontend.ftq.ftq.transaction.types import Pointers
from suites.frontend.ftq.ftq.transaction.types import PrefetchRequest
from suites.frontend.ftq.ftq.transaction.types import RedirectEvent
from suites.frontend.ftq.ftq.transaction.types import Topdown
from suites.frontend.ftq.ftq.transaction.types import TrainingEntry
from suites.frontend.ftq.harness import Dut
from suites.frontend.ftq.resolve_queue.transaction.types import Branch


def pointer(dut: Dut, name: str, index: int = 0) -> Owner:
    base = f"FtqDut_top.Ftq.{name}_ptrs_{index}"
    return Owner(flag=dut.internal(base + "_flag"),
                 value=dut.internal(base + "_value"))


def pointers(dut: Dut) -> Pointers:
    return Pointers(
        bpu=pointer(dut, "bpuPtr"),
        pf=(pointer(dut, "pfPtr", 0), pointer(dut, "pfPtr", 1)),
        fetch=(pointer(dut, "fetchPtr", 0), pointer(dut, "fetchPtr", 1)),
        commit=pointer(dut, "commitPtr"),
        pnr=pointer(dut, "pnrPtr"),
    )


def training(dut: Dut, ports: FtqPorts) -> TrainingEntry | None:
    if not ports.train.b("valid"):
        return None
    branches = []
    for slot in range(8):
        if not ports.train.b(f"slot{slot}.valid"):
            continue
        branches.append(Branch(
            position=ports.train.u(f"slot{slot}.bits_cfiPosition"),
            target=ports.train.u(f"slot{slot}.bits_target_addr"),
            taken=ports.train.u(f"slot{slot}.bits_taken"),
            mispredict=ports.train.u(f"slot{slot}.bits_mispredict"),
            branch_type=ports.train.u(f"slot{slot}.bits_attribute_branchType"),
            ras_action=ports.train.u(f"slot{slot}.bits_attribute_rasAction"),
        ))
    return TrainingEntry(
        start_pc=ports.train.u("start_pc"),
        start_pc_vec=(ports.train.u("start_pc"),
                      ports.train.u("start_pc1"),
                      ports.train.u("start_pc2"),
                      ports.train.u("start_pc2_1")),
        branches=tuple(branches),
        meta_phr=ports.train.u("meta_phr"),
        meta_ghr=ports.train.u("meta_ghr"),
        meta_common_valid=ports.train.u("meta_common_valid"),
    )


def commit_event(dut: Dut, ports: FtqPorts) -> CommitEvent | None:
    if not ports.commit_out.b("valid"):
        return None
    return CommitEvent(
        ras_action=ports.commit_out.u("ras"),
        meta_ssp=ports.commit_out.u("meta_ssp"),
        meta_tosw_flag=ports.commit_out.u("meta_tosw_flag"),
        meta_tosw_value=ports.commit_out.u("meta_tosw_value"),
    )


def redirect_event(dut: Dut, ports: FtqPorts) -> RedirectEvent | None:
    if not ports.redirect_out.b("valid"):
        return None
    return RedirectEvent(
        cfi_pc=ports.redirect_out.u("cfi_pc"),
        target=ports.redirect_out.u("target"),
        taken=ports.redirect_out.u("taken"),
        branch_type=ports.redirect_out.u("branch_type"),
        ras_action=ports.redirect_out.u("ras_action"),
        meta_phr=ports.redirect_out.u("meta_phr"),
        meta_ghr=ports.redirect_out.u("meta_ghr"),
    )


def prefetch(dut: Dut, ports: FtqPorts) -> PrefetchRequest:
    p = ports.prefetch
    return PrefetchRequest(
        valid=p.b("valid"),
        start=p.u("req0.startVAddr_addr"),
        next_line=p.u("req0.nextLineVAddr_addr"),
        set0=p.u("req0.vSetIdx_0"),
        set1=p.u("req0.vSetIdx_1"),
        cross_line=p.b("req0.isCrossLine"),
        index=p.u("req0.ftqIdx_value"),
        index_flag=p.u("req0.ftqIdx_flag"),
        backend_exception=p.u("req0.backendException_value"),
        case=p.u("case"),
        req1_start=p.u("req1.startVAddr_addr"),
        req1_index=p.u("req1.ftqIdx_value"),
    )


def fetch(dut: Dut, ports: FtqPorts) -> FetchRequest:
    p = ports.fetch
    return FetchRequest(
        valid=p.b("valid"),
        req1_valid=p.b("req1.valid"),
        start=p.u("req0.vAddr_0_addr"),
        addr0=p.u("req0.vAddr_0_addr"),
        addr1=p.u("req0.vAddr_1_addr"),
        index=p.u("req0.ftqIdx_value"),
        index_flag=p.u("req0.ftqIdx_flag"),
        taken=p.u("req0.taken"),
        end_position=p.u("req0.endPosition"),
        bank0=p.u("req0.bankSel_0"),
        bank1=p.u("req0.bankSel_1"),
        backend_exception=p.b("req0.hasBackendException"),
        satp_flush=p.b("req0.hasSatpFlush"),
        req1_index=p.u("req1.ftqIdx_value"),
    )


def flush(dut: Dut, ports: FtqPorts) -> FlushEvent:
    p = ports.flush
    return FlushEvent(
        s2_valid=p.b("s2_valid"),
        s2_flag=p.u("s2_flag"),
        s2_value=p.u("s2_value"),
        s3_valid=p.b("s3_valid"),
        s3_flag=p.u("s3_flag"),
        s3_value=p.u("s3_value"),
        redirect_flush=p.b("redirect_flush"),
        to_ifu_redirect=p.b("to_ifu_redirect"),
        ifu_s3_flush=p.b("ifu_s3_flush"),
    )


def topdown(dut: Dut, ports: FtqPorts) -> Topdown:
    p = ports.topdown
    return Topdown(
        reasons={index: p.b(f"reason{index}") for index in (2, 3, 5, 6, 7, 8, 9)},
        backend_redirect=p.b("backend_redirect"),
        control_flow=p.b("control_flow"),
        memory_violation=p.b("memory_violation"),
        tage_miss=p.b("tage_miss"),
        ittage_miss=p.b("ittage_miss"),
        ras_miss=p.b("ras_miss"),
    )


def backend_write(dut: Dut, ports: FtqPorts) -> BackendWrite:
    p = ports.backend
    return BackendWrite(wen=p.b("wen"), index=p.u("index"),
                        start_pc=p.u("start_pc"))


def prediction_offer(dut: Dut, ports: FtqPorts) -> SimpleNamespace:
    """Ready and the combinational backend PC write for the offered entry."""

    write = backend_write(dut, ports)
    return SimpleNamespace(ready=ports.prediction_ready.b("ready"),
                           wen=write.wen, index=write.index,
                           start_pc=write.start_pc)


def entry(dut: Dut, index: int):
    from suites.frontend.ftq.ftq.transaction.types import Entry

    return Entry(
        start_pc=dut.internal(f"FtqDut_top.Ftq.entryQueue_{index}_startPc_addr"),
        taken=dut.internal(f"FtqDut_top.Ftq.entryQueue_{index}_taken"),
        end_position=dut.internal(f"FtqDut_top.Ftq.entryQueue_{index}_endPosition"),
    )
