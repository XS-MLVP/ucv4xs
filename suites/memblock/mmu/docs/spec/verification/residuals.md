# MMU 验证残余项

本页保留 `manifest/known-issues.json` 中**未被归为正式 bug** 的稳定 ID：覆盖缺口、结构/初始化边界、已接受性能观察和待合法激励复核项。目录 [bugs/](../../bugs) 只记录可处置的问题；本页记录当前验证范围/证据的残余，不能用 waiver 当作功能通过。

| ID | manifest 状态 | 当前观察 | 证据 |
|---|---|---|---|
| `TLBFA-INITIAL-RESET-ELSE` | accepted-nonfunctional | implicit else branch is not exercised | `manifest/known-issues.json` |
| `TLBFA-PUBLIC-PORTS-ONLY` | by-design | The Picker build has no VPI and no internal signal configuration. | `manifest/known-issues.json` |
| `WRAPPER-INITIAL-RESET-ELSE` | accepted-nonfunctional | implicit else branch is not exercised | `manifest/known-issues.json` |
| `L2MQ-CONSTANT-HPTW` | accepted | isHptwReq and hptwId are hardwired to zero in the queue payload. | `manifest/known-issues.json` |
| `L2TLB-TOP-PARTIAL` | open | Current soundness-final-l2tlb-02: 46 PASS, line 17079/22249, toggle 96980/255430, branch 4330/6304. Residual functional state/data-pattern enumeration remains open; sampled bins are not semantic closure. | `results/soundness-final-l2tlb-02/coverage-audit.json`; `docs/spec/verification/evidence/reports/evidence/soundness-20261025/final-residuals.json` |
| `L2TLB-MBIST-UNVERIFIED` | accepted-nonfunctional | MbistBitmapCache, MbistPipePtwL0 and MbistPipePtwL1 DFT ports are tied inactive; 8 lines per module remain uncovered. No functional DUT or functional point is claimed for MBIST/DFT in phase 2; this is an explicit exclusion, not a failed functional test. | `manifest/known-issues.json` |
| `L2TLB-PTWCACHE-LLPTW-GAPS` | open-residual-enumeration | Independent PtwCache/LLPTW suites pass but neither all coverage nor all functional data/state enumerations are closed. | `docs/spec/verification/evidence/reports/evidence/soundness-20261025/final-residuals.json` |
| `PTWFILTER-RESIDUAL-TOGGLE` | open | Current soundness-final-ptwfilter-01: 4412/4414 toggles; remaining polarity points unverified, not automatically unreachable. | `results/ptwfilter-final-16/coverage-audit.json`; `testbenches/ptwrepeater/tests/test_ptwfilter.py::test_high_tag_match_directions` |
| `PTW-LEAVES-INITIAL-ELSE` | accepted-nonfunctional | Each block has one uncovered branch: the implicit else of the time-zero initial reset block (line 371 / 1654). | `manifest/known-issues.json` |
| `HPTW-INITIAL-RESET-ELSE` | accepted-nonfunctional | The implicit else of the time-zero initial reset block is not exercised. | `manifest/known-issues.json` |
| `HPTW-RESIDUAL-TOGGLE` | open | HPTW final toggle is 5069/5270=96.19%; residual 201 points are high-bit/polarity combinations of cache_pte_ppn/req_ppn/gpaddr, io_mem_req_bits_addr[0..2] (structurally aligned zero), refill/bitmap vpn[36], bitmap way_info[3], cache_pte_n, fromSP/l2Hit and initial state. All event/page/hit functional bins are 100% and line coverage is 100%. | `results/hptw-final-02/coverage-audit.json`; `docs/spec/verification/functional-points/functional-points-hptw.md` |
| `HPTW-ACCESSFAULT-NOT-RESET` | accepted | Structural: HPTW.sv accessFault is assigned in a clocked always block without a reset branch and has a random initial value. With the fixed test seed 1 (and seeds 2..8), a first walk after reset without the usual post-reset sfence returns gaf=0 and performs three table reads; a PMP-denied walk sets gaf=1/no reads, and a subsequent reset+valid walk succeeds. No functional spurious first-walk fault was reproduced in this build/seed. | `rtl/hptw/HPTW.sv accessFault assignment (no reset)`; `testbenches/hptw/tests/test_hptw.py::test_hptw_reset_without_flush_observation` |
| `LLPTW-PARTIAL-COVERAGE` | open | Current soundness-final-llptw-01: 27 PASS, line 1660/1955, toggle 4330/20770, branch 359/407. Residual functional state/data-pattern enumeration remains open; sampled bins are not semantic closure. | `results/soundness-final-llptw-01/coverage-audit.json`; `docs/spec/verification/evidence/reports/evidence/soundness-20261025/final-residuals.json` |
| `PMP-PMA-DEFAULTS-FROM-RTL` | accepted | Previous PMA expected reset table was sampled from the live DUT, so the comparison could not detect wrong defaults. The environment now uses a checked-in build-specific table; its source hash and configuration provenance are explicit. | `manifest/pma-reset-reference.json`; `testbenches/pmp/env/pmp.py` |
| `BITMAPCACHE-RESIDUAL` | partially-reviewed | BitmapCache line 314/323; 9 uncovered lines are MBIST registers and time-zero initial. 24 branches are split-SRAM stageDelay/bypass or reset structure. | `results/soundness-final-bitmapcache-01/coverage-audit.json`; `docs/spec/verification/evidence/reports/evidence/soundness-20261025/final-residuals.json` |
| `PTWCACHE-RESIDUAL-STRUCTURAL` | partially-reviewed | Current soundness-final-ptwcache-01: 50 PASS, line 13744/13748, toggle 95616/110892, branch 3182/3226. Residual functional state/data-pattern enumeration remains open; sampled bins are not semantic closure. | `results/soundness-final-ptwcache-01/coverage-audit.json`; `docs/spec/verification/evidence/reports/evidence/soundness-20261025/final-residuals.json` |
| `L2TLBWRAPPER-PERF-NO-RESET` | accepted-nonfunctional | The 19 wrapper perf outputs are two extra RegNext stages over L2TLB perf outputs. Neither stage has a synchronous reset, so the first cycles after reset can expose Verilator random initial values; they flush after four cycles. Functional TLB state is reset normally. | `testbenches/l2tlbwrapper/tests/test_l2tlbwrapper.py::test_wrapper_reset_and_idle_pipeline`; `docs/spec/verification/evidence/reports/evidence/cycle-l2tlbwrapper-20261025/perf-trace-comparison.json` |

## 阅读说明

- `accepted-nonfunctional` / `by-design` / `accepted` 表示验证侧明确排除或仅作观察，不代表 RTL 功能正确。
- `open` / `open-residual-enumeration` / `partially-reviewed` 表示残余仍未闭合；本次文档整理没有重跑 native。
- 与正式 bug 的关系：已撤回的旧 RTL 根因进入 [bugs/closed](../../bugs/closed)；仍需设计确认或合法激励复核的候选进入 [bugs/open](../../bugs/open)；本页只保留非 bug 的覆盖/结构/范围边界。
- 所有 `manifest/known-issues.json` 条目仍保留原文和旧证据路径；历史证据快照中的旧路径不重写。
