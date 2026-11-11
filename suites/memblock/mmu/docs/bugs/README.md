# MMU 问题记录

本目录记录 MMU/TLB 验证中的开放缺陷、候选调查项和已关闭的旧误报/覆盖缺口。目录决定当前状态：`open/`、`closed/`；旧可信度复核和证据在 [evidence/](evidence/)。

正式记录使用稳定 ID；每个文件开头的 ```ucv-bug``` JSON 块给出机器可读状态、基线和证据。
`closed/` 中的 `fixed`/`invalid` 判定来自 2026-10-25/26 历史复核；当前 `public-a0c2a26cb` 未重跑。`invalid` 只关闭旧基线误报/归因错误，当前基线标为 `unverified`；唯一保留的 `fixed` 结构项（独立 DUT）以当前仓库结构证据关闭，也不代表当前基线回归通过。
正文保留现象、预期依据、复现/对照、根因、处置结论和适用范围。未归为正式 bug 的覆盖/结构/范围残余见 [../spec/verification/residuals.md](../spec/verification/residuals.md)。

<!-- ucv:bugs:start -->

由 `ucv docs --write` 生成；目录表示当前处理状态，版本结论见各记录。

当前工程基线：`public-a0c2a26cb`。未复验项不继承历史通过结论。

## 未解决（8）

| ID | 问题 | 类型 | 本基线结论 | 关闭原因 |
|---|---|---|---|---|
| [L2TLB-PMA-UNVERIFIED](open/L2TLB-PMA-UNVERIFIED.md) | PMA/PMP 交互覆盖缺口 | verification | 未复验 | — |
| [L2TLB-SATP-NO-SFENCE-STALE](open/L2TLB-SATP-NO-SFENCE-STALE.md) | satp 写入不隐含排序/失效；旧超时使用非法 responder，未定性 | investigation | 未复验 | — |
| [L2TLBWRAPPER-MULTI-OUTSTANDING-UNVERIFIED](open/L2TLBWRAPPER-MULTI-OUTSTANDING-UNVERIFIED.md) | wrapper 多 outstanding 覆盖缺口 | verification | 未复验 | — |
| [LLPTW-STAGE2-CACHE-UNVERIFIED](open/LLPTW-STAGE2-CACHE-UNVERIFIED.md) | LLPTW 独立 harness 无法捕获 stage2/cache-retry | verification | 未复验 | — |
| [PTW-FULL-GVPN-GAP](open/PTW-FULL-GVPN-GAP.md) | PTW full_gvpn / normal allStage 覆盖缺口 | verification | 未复验 | — |
| [TLB-GPA-REPLAY-UNVERIFIED](open/TLB-GPA-REPLAY-UNVERIFIED.md) | TLB GPA/getGpa 重放覆盖缺口 | verification | 未复验 | — |
| [TLBFA-LEVEL3-FAKE-PTE-UNREACHABLE](open/TLBFA-LEVEL3-FAKE-PTE-UNREACHABLE.md) | s1 fake PTE + s2 exception 永远选择 s1_level，文档所述 level 3 分支不可达 | rtl | 未复验 | — |
| [WRAPPER-PLRU-NO-INVALID-PRIORITY](open/WRAPPER-PLRU-NO-INVALID-PRIORITY.md) | TlbStorageWrapper 的 PLRU 不优先无效 way，冷启动可能淘汰有效项 | rtl | 未复验 | — |

## 已关闭（9）

| ID | 问题 | 类型 | 本基线结论 | 关闭原因 |
|---|---|---|---|---|
| [BITMAP-MULTI-MISS-UNVERIFIED](closed/BITMAP-MULTI-MISS-UNVERIFIED.md) | Bitmap 多 miss 被误报为只完成一次 | verification | 未复验 | invalid |
| [BITMAP-PMP-BACKTOBACK-LOST](closed/BITMAP-PMP-BACKTOBACK-LOST.md) | Bitmap back-to-back 第二个请求看似丢失 | verification | 未复验 | invalid |
| [L2TLB-BITMAP-DENY-UNVERIFIED](closed/L2TLB-BITMAP-DENY-UNVERIFIED.md) | Bitmap deny 极性曾被误判 | verification | 未复验 | invalid |
| [L2TLB-INDEPENDENT-SUBBLOCKS-MISSING](closed/L2TLB-INDEPENDENT-SUBBLOCKS-MISSING.md) | L2 子块与 wrapper 缺少独立 DUT | verification | 已处置 | fixed |
| [L2TLB-MULTI-OUTSTANDING-STALL](closed/L2TLB-MULTI-OUTSTANDING-STALL.md) | L2TLB 多 outstanding 停顿被归因为 RTL | verification | 未复验 | invalid |
| [L2TLB-PREFETCH-SHARED-LEAF-STALL](closed/L2TLB-PREFETCH-SHARED-LEAF-STALL.md) | 共享叶表零间隔 prefecth 抢占 demand 的根因结论 | verification | 未复验 | invalid |
| [L2TLB-SFENCE-RS1RS2-ZERO-NO-REWALK](closed/L2TLB-SFENCE-RS1RS2-ZERO-NO-REWALK.md) | sfence rs1=0/rs2=0 被误当作全局失效 | verification | 未复验 | invalid |
| [LLPTW-MULTI-STAGE2-UNVERIFIED](closed/LLPTW-MULTI-STAGE2-UNVERIFIED.md) | 两个 allStage 并发时只完成一个 | verification | 未复验 | invalid |
| [LLPTW-PMP-BACKTOBACK-GAP](closed/LLPTW-PMP-BACKTOBACK-GAP.md) | LLPTW 连续请求被要求插入 >=3 idle cycle | verification | 未复验 | invalid |

<!-- ucv:bugs:end -->

## 旧证据

- [2026-10-25 可信度复核](../spec/verification/evidence/reports/verification-soundness-20261025.md)：5 个旧 XFAIL 被反证，旧 RTL 根因撤回。
- [`manifest/known-issues.json`](../../manifest/known-issues.json) 保留原始状态和证据路径；本目录将其中的可处置问题分流为 open/closed，其余进入 residuals。
