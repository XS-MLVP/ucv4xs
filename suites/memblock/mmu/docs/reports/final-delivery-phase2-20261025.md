# 第二阶段交付报告：TLB/MMU 缺口补齐（2026-10-25）

> **可信度复核更正（2026-10-25）**：本报告保留旧 run 的历史指标；当前归因以
> `verification-soundness-20261025.md` 为准。原 5 个 strict XFAIL 的 DUT 缺陷归因
> 已被验证侧反证推翻；“100% sampled bins”不等于功能验收或不可达证明。


## 1. 结论

第二阶段以第一阶段 16 个最终 run 和 `manifest/known-issues.json` 为输入，逐项
补齐或确证缺口。所有新增/更新 run 均为 `state=committed`、
`coverage_complete=true`、`pytest_exitstatus=0`；没有 skip、failed 或伪造通过。
strict XFAIL 只用于已给出精确边界和证据的候选行为，不计入 PASS，也不冒充通过。

| 项 | 结果 |
|---|---|
| 最终 run 数 | 17（第一阶段的 16 个中 8 个被更新；新增 TLBNonBlock） |
| 用例 | **376 PASS + 5 strict XFAIL**，0 failed / 0 skip |
| 新闭合缺口 | TLBNonBlock、TLB GPA、Bitmap deny、L2TLB PMA/PMP、PTW full_gvpn、HPTW reset observation、共享叶子根因隔离 |
| 仍未闭合/不主张 | LLPTW 多 allStage、all-address sfence、Bitmap 多 miss/back-to-back、MBIST/DFT、物理 way 放置、整个 MMU |
| 工具 | Picker `2.0.0-HEAD-4dd442c-2026-10-12`、Verilator `5.052`、toffee `2.0.0.dev12+g3017293a7` |
| seed | `MMU_VERILATOR_SEED=1`（HPTW reset observation 另扫 1..8，仅作辅助证据） |
| RTL | `soc-split/rtl` 字节级副本，未修改；SHA-256 见 `manifest/*-rtl.sha256` |
| 波形 | 无波形/逐周期 dump；compact 证据与完整 run 分离 |

## 2. 更新后的最终 run

| 模块 | 用例 | 行覆盖 | branch | toggle | 最终 run |
|---|---:|---:|---:|---:|---|
| TLBFA | 31 | 3419/3419 | 1016/1018 | 17766/17766 | `tlbfa-full-06` |
| TlbStorageWrapper | 8 | 3431/3431 | 1019/1022 | 18798/18798 | `wrapper-full-06` |
| TLB（ITLB） | 25 | 3655/3657 | 1094/1104 | 18785/23074 | `tlb-gpa-tests-06` |
| **TLBNonBlock（DTLB）** | **30** | **4839/4956** | **1424/1568** | **20486/37422** | **`tlbn-tests-13`** |
| L2TlbMissQueue | 5 | 24/24 | 17/18 | 829/854 | `l2mq-03` |
| L2TlbPrefetch | 6 | 39/39 | 22/23 | 657/784 | `l2pf-05` |
| PTWRepeaterNB | 7 | 72/72 | 7/8 | 3114/3114 | `ptwrepeater-06` |
| PTWFilter | 14 | 206/206 | 91/92 | 4411/4414 | `ptwfilter-final-16` |
| HPTW | 21 | 133/133 | 97/98 | 5069/5270 | `hptw-final-02` |
| PTW | 30 | 530/530 | 418/420 | 12213/15344 | `ptw-final-06` |
| PMP | 12 | 2117/2117 | 437/470 | 47680/51404 | `pmp-final-04` |
| BitmapCache | 12 | 314/323 | 124/148 | 6953/14174 | `bitmapcache-final-06` |
| Bitmap | 16 + 2 XFAIL | 974/1415 | 279/398 | 2190/6636 | `bitmap-final-07` |
| PtwCache | 50 | 13741/13748 | 3179/3226 | 87398/110892 | `ptwcache-final-02` |
| LLPTW | 23 + 1 XFAIL | 1656/1955 | 359/407 | 4329/20770 | `llptw-final-04` |
| L2TLB 顶层 | 40 + 1 XFAIL | 17081/22249 | 4329/6304 | 96615/255430 | `l2tlb-final-12` |
| L2TLBWrapper | 46 + 1 XFAIL | 17697/22289 | 4444/6304 | 102301/260640 | `l2tlbwrapper-final-05` |

变化最大的项目：

- TLB GPA 重放：行 3644→3655，branch 1089→1094，toggle 18716→18785。
- TLBNonBlock：从无独立 DUT 到 30 PASS、功能 100%、行 97.639%；残余 117 行分类为
  TLBFA per-way sfence ternary 与 need_gpa 端口 1/3 情况枚举。
- PTW：519→530 行（100%），branch 413→418，toggle 12118→12213。
- L2TLB：16976→17081 行，branch 4297→4329，toggle 95703→96615；新增 bitmap
  deny、PMA/PMP、scoped sfence 等功能点。
- L2TLBWrapper：toggle 101986→102220；共享叶子停顿根因隔离并新增 1 个空闲周期正例。
- Bitmap：955→974 行，branch 266→279，toggle 2104→2190；deny 极性闭合，
  multi-miss/back-to-back 保留 XFAIL。

## 3. 已闭合项

| 缺口 | 处置与证据 |
|---|---|
| TLBNonBlock 无独立验收 | 5 文件真实闭包 `rtl/tlbn`，构建 `20261025T022103052014Z-tlbn`；30 用例覆盖 Bare/no_translate、miss/PTW/refill、超级页、ASID/VMID、load/store/AMO、A/D、af、PBMT、onlyS1/onlyS2/allStage、GPA 回放、fake/nonleaf、四端口、PMP、kill、lane、失效、容量、perf、redirect。`tlbn-tests-13`。 |
| TLB GPA/getGpa 重放 | `test_gpa_replay_for_all_stage_gpf` 实际断言 `ptw.getGpa=1`、GPA 响应、`gpf` 与 `gpaddr=0x1a2b3f678`；行 3655/3657。 |
| Bitmap deny 极性 | `test_bitmap_deny_and_allow`：all-ones cf=1 → `s1_af=1`；all-zero cf=0 → 正确 PPN。旧观察是 checker 未查 `s1_af`。 |
| PMA 0x7C0..0x7C8 | PMP leaf 的 32 entry PMA cfg/addr/mask 与逐字节 cfg 语义；L2TLB 顶层用 TOR 覆盖页表：C=1/R=1 允许，C=0 或 R=0 在表读前 `s1_af=1`。 |
| PTW full_gvpn / 512GB / normal allStage | `test_stage1_hit_full_gvpn_levels`（S1/G level 0..3、NAPOT、gpf）与 `test_normal_all_stage_identity_hptw`（root/mid/final HPTW identity）；行 530/530。 |
| HPTW accessFault 复位行为 | 结构上 `accessFault` 不在同步复位块内；seed 1..8 下首次合法走表仍 gaf=0 并完成三次读，PMP 拒绝走表 gaf=1，复位后再次成功。无功能性 spurious fault 复现，保留为 RTL hygiene observation。 |
| 共享叶子 back-to-back 停顿 | 零间隔时第三个 demand 行 0x800A2080 被预取行 0x800A20C0 替代；插入 1 个 service 周期后 demand 正常发出，三个页面全部完成。根因隔离为 0 空闲周期 prefetch/LLPTW 交接；strict XFAIL + 正例。 |
| satp.changed + sfence | 支持的“satp.changed + sfence”路径返回新翻译；无 sfence 序列不在软件契约内，记录为 accepted observation。 |

## 4. 仍未闭合/边界

| 项 | 证据 | 分类 |
|---|---|---|
| LLPTW 多 allStage | 零间隔/单请求 stagger/不同 slot 顺序均只有一个 entry 完成，另一个在 first-stage HPTW 响应后不再发 PTE 读；单 allStage slot 1..5 全过。`test_two_concurrent_all_stage` strict XFAIL。 | 公共端口精确边界，原因未完全隔离 |

| all-address sfence | PTE 改写后 `rs1=0/rs2=0` 返回旧 PPN 且无新表读；scoped sfence 正常。strict XFAIL。 | 候选 RTL 缺陷，需设计者复核 |
| Bitmap 多 miss/back-to-back | 第二个并发 miss 在首次读后停顿；back-to-back 请求丢失第二个 PMP 检查。两个 strict XFAIL。 | 候选 RTL 缺陷/边界 |
| PTWFilter residual toggle | 3 点：`issue_filtered_vmid_hit:1->0`、`ptwResp_newMatchVec_onlyS2_hit_tag_match_1/2:1->0`。行 206/206、branch 91/92、功能 100%。 | 情况枚举 |
| HPTW residual toggle | 201 点：高位/极性组合、bitmap 握手、fromSP/l2Hit、initial。行/功能 100%。 | 数据极性/结构 |
| Bitmap residual lines | 441 行：8-entry dup/wait 向量、multi-miss 路径。deny/allow 与单 miss 已闭合。 | 情况枚举 + XFAIL 边界 |
| LLPTW residual lines | 299 行：per-entry duplicate wait/last HPTW 状态。功能 100%。 | 情况枚举 |
| PtwCache residual | 7 行：SRAM 宏复位、MBIST/DFT、L3 one-hot 假分支；物理 way 放置/DFT 不通过功能端口可达。 | accepted-nonfunctional |
| MBIST/DFT | `MbistBitmapCache`、`MbistPipePtwL0/L1` 保持 inactive；未建功能 DUT，明确排除。 | scope exclusion |
| 整个 MMU | 本工程只做 TLB/MMU 分层 UT，不声称完整 MMU/SoC 验收。 | 范围声明 |

## 5. 证据与复现

- RTL SHA-256：`manifest/*-rtl.sha256`（TLBNonBlock 另见
  `manifest/tlbn-rtl.sha256`）。
- 构建：`results/builds/<stamp>/report.json`；新增 TLBNonBlock 构建
  `20261025T022103052014Z-tlbn`（`ok=true`）。
- 最终 run：`results/<run>/`（manifest、coverage-audit、functional-coverage、
  lcov/html、coverage.dat、native）。
- Compact 证据：
  - `docs/reports/evidence/cycle-tlbn-20261025/`
  - `docs/reports/evidence/cycle-tlb-gpa-20261025/`
  - `docs/reports/evidence/cycle-phase2-20261025/`（closures/residuals 汇总）
  - 其余更新：`cycle-l2-midblocks-20261024`、`cycle-hptw-20261024`、
    `cycle-l2tlb-20261024`、`cycle-l2tlbwrapper-20261025`、
    `cycle-llptw-20261025`。
- `tools/verify_delivery.py` 保留第一阶段既有检查并新增第二阶段 run/证据/XFAIL
  计数；资源受控：不保存波形，中间 probe/dbg run 已裁剪。

## 6. 明确不主张

本报告不主张：

- LLPTW 多 allStage 并发、all-address sfence、Bitmap 多 miss/back-to-back 已通过；
- all-address sfence 失效、Bitmap 多 miss/back-to-back 已修复；
- MBIST/DFT 或 PtwCache 物理 way 放置已验收；
- 整个 MMU、SoC 或与设计者签核等价。
