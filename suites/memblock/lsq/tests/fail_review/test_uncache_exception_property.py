"""Property-only check for uncache exception ownership (#6634).

The existing LoadUncacheModel copies the RTL's own choice: every writeback
creates a candidate and the first physical entry wins.  This probe uses only
public pins and the parent's documented filter (``ExceptionInfoGen`` selects
``exceptionVec.orR`` and then the oldest by ROB/uopIdx).

Properties:
1. every consumed real bus error must be reported with its own ROB and VA;
2. a normal completion (all-zero exceptionVec) must never replace a real fault
   consumed in the same cycle;
3. when two real faults are consumed in the same cycle, both must be reported
   (one may be delayed, but none may be dropped).
"""
import pytest


@pytest.mark.parametrize("review_dut", ["load_queue_uncache"], indirect=True)
@pytest.mark.parametrize("mode", ("one_fault", "normal_and_fault", "two_faults"))
async def test_uncache_exception_owner_is_oldest_real_bus_error(review_dut, mode):
    e = review_dut
    e.metadata = dict(issue="#6634", mode=mode,
                      domain="public LoadQueueUncache pins; no model prediction")
    base = {"io_rob_pendingPtr_value": 10, "io_rob_pendingPtr_isFormer": 1}

    async def cycle(fields=None):
        await e.step({**base, **(fields or {})})

    # Two independent NC loads; A (ROB 10) is older than B (ROB 11).
    # Slot order follows allocation: A->0, B->1, so a physical-order selector
    # would prefer A even when A is only a normal completion.
    a = dict(uid=1, rob=10, lq=11, va=0x10000, pa=0x80000000, sid=3,
             fault=mode in ("one_fault", "two_faults"))
    b = dict(uid=2, rob=11, lq=12, va=0x11000, pa=0x80001000, sid=4,
             fault=mode in ("normal_and_fault", "two_faults"))

    async def enqueue(owner, lane):
        p = f"io_req_{lane}_"
        await cycle({p + name: value for name, value in {
            "valid": 1, "bits_uop_robIdx_value": owner["rob"], "bits_uop_robIdx_isFormer": 1,
            "bits_uop_lqIdx_value": owner["lq"], "bits_uop_ftqOffset": 2 * owner["uid"] - 1,
            "bits_uop_perfDebugInfo_runahead_checkpoint_id": owner["uid"],
            "bits_vaddr": owner["va"], "bits_fullva": owner["va"], "bits_paddr": owner["pa"],
            "bits_mask": 255, "bits_nc": 1, "bits_rep_info_need_rep": 1, "bits_rep_info_cause_0": 1}.items()})

    async def serve(owner):
        for _ in range(60):
            if e.post["io_uncache_req_valid"]:
                break
            await cycle()
        e.check("bus request offered", e.post["io_uncache_req_valid"], 1)
        await cycle({"io_uncache_req_ready": 1})
        mid = e.pre["io_uncache_req_bits_id"]
        await cycle({"io_uncache_idResp_valid": 1, "io_uncache_idResp_bits_mid": mid,
                     "io_uncache_idResp_bits_sid": owner["sid"]})
        await cycle({"io_uncache_resp_valid": 1, "io_uncache_resp_bits_id": owner["sid"],
                     "io_uncache_resp_bits_data": 0xA0 + owner["uid"],
                     "io_uncache_resp_bits_nderr": int(owner["fault"])})
        for _ in range(40):
            if ("nc", 0, owner["lq"]) in e.wakes:
                break
            await cycle()
        e.event("served", uid=owner["uid"], mid=mid, fault=owner["fault"])
        e.check("original LQ wakeup", ("nc", 0, owner["lq"]) in e.wakes, True)

    await enqueue(a, 0)
    await enqueue(b, 1)
    await serve(a)
    await serve(b)

    # Consume both owners on two bypass lanes in the SAME cycle.
    packet = {}
    for lane, owner in ((0, a), (1, b)):
        p = f"io_bypass_{lane}_"
        packet.update({p + "s0Req_valid": 1, p + "s0Req_bits_lqIdx_value": owner["lq"],
                       p + "s0Req_bits_isNCReplay": 1})
    await cycle(packet)

    reports, consumed = [], {0: [], 1: []}
    for _ in range(12):
        if e.post["io_exceptionInfo_valid"]:
            reports.append(dict(rob=e.post["io_exceptionInfo_bits_robIdx_value"],
                                vaddr=e.post["io_exceptionInfo_bits_vaddr"],
                                laf=e.post["io_exceptionInfo_bits_exceptionVec_5"],
                                hwe=e.post["io_exceptionInfo_bits_exceptionVec_19"]))
        for lane in (0, 1):
            p = f"io_bypass_{lane}_"
            if e.post[p + "s1Resp_valid"]:
                consumed[lane].append(("s1", e.post[p + "s1Resp_bits_paddr"]))
            if e.post[p + "s2Resp_valid"]:
                consumed[lane].append(("s2", e.post[p + "s2Resp_bits_data"]))
        await cycle()
    e.event("all_exception_candidates", reports=reports, consumed=consumed,
            owners={x["uid"]: x for x in (a, b)})

    # Both owners must actually have reached the LDU response pipeline.
    for lane, owner in enumerate((a, b)):
        e.check("owner reached s2 response", any(stage == "s2" for stage, _ in consumed[lane]), True)

    faults = [owner for owner in (a, b) if owner["fault"]]
    real = [report for report in reports if report["laf"] or report["hwe"]]
    e.check("a real fault candidate was reported", bool(real), True)

    # Parent-visible property: every consumed real error must appear with its
    # own ROB/VA.  A zero-vector candidate may exist internally but must not
    # replace a real one.
    reported = {(report["rob"], report["vaddr"]) for report in real}
    for owner in faults:
        e.check("each consumed fault reported with its address",
                (owner["rob"], owner["va"]) in reported, True)
    if len(faults) > 1:
        e.check("oldest fault reported first", real[0]["rob"], a["rob"])
    e.finish()
