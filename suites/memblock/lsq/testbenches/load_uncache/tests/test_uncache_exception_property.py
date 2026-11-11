"""Property-only check for LoadQueueUncache exception ownership (#6634).

The existing LoadUncacheModel copies the RTL's own choice: every writeback
creates a candidate and the first physical entry wins.  This probe uses only
public parent transactions and the documented filter (``ExceptionInfoGen``
selects ``exceptionVec.orR`` and then the oldest by ROB/uopIdx).

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
                      domain="public LoadQueueUncache transactions; no model prediction")
    # Two independent NC loads; A (ROB 10) is older than B (ROB 11).
    # Slot order follows allocation: A->0, B->1, so a physical-order selector
    # would prefer A even when A is only a normal completion.
    a = dict(uid=1, rob=10, lq=11, va=0x10000, pa=0x80000000, sid=3,
             fault=mode in ("one_fault", "two_faults"))
    b = dict(uid=2, rob=11, lq=12, va=0x11000, pa=0x80001000, sid=4,
             fault=mode in ("normal_and_fault", "two_faults"))

    async def serve(owner):
        mid = await e.bus_fire(owner["sid"], owner)
        await e.respond(owner, owner["sid"], 0xA0 + owner["uid"], nderr=owner["fault"])
        e.event("served", uid=owner["uid"], mid=mid, fault=owner["fault"])
        e.check("original LQ wakeup", ("nc", False, owner["lq"]) in e.wakes, True)

    await e.enqueue(a, 0, pending=e.pending)
    await e.enqueue(b, 1, pending=e.pending)
    await serve(a)
    await serve(b)

    # Consume both owners on two bypass lanes in the SAME cycle.
    await e.bypass_many({0: a, 1: b})
    reports, consumed = [], {0: [], 1: []}
    for _ in range(12):
        snapshot = e.post_response
        if snapshot.exception.valid:
            reports.append((snapshot.exception.rob.value, snapshot.exception.vaddr,
                            snapshot.exception.exceptions >> 5 & 1,
                            snapshot.exception.exceptions >> 19 & 1))
        for lane in (0, 1):
            item = snapshot.bypass[lane]
            if item.s1_valid:
                consumed[lane].append(("s1", item.s1_paddr))
            if item.s2_valid:
                consumed[lane].append(("s2", item.s2_data))
        await e.idle(1)

    faults = [owner for owner in (a, b) if owner["fault"]]
    real = [report for report in reports if report[2] or report[3]]
    e.check("a real fault candidate was reported", bool(real), True)
    for lane, owner in enumerate((a, b)):
        e.check("owner reached s2 response", any(stage == "s2" for stage, _ in consumed[lane]), True)

    reported = {(entry[0], entry[1]) for entry in real}
    for owner in faults:
        e.check("each consumed fault reported with its address",
                (owner["rob"], owner["va"]) in reported, True)
    if len(faults) > 1:
        e.check("oldest fault reported first", real[0][0], a["rob"])
    e.finish()
