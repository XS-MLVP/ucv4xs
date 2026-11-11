# LSU 问题记录

本目录记录 LSU 三个模块族独立 UT 中确认的 RTL 问题。目录决定当前状态：`open/` 为仍需处理或未在当前基线复验的问题，`closed/` 为已给出处置结论的问题。旧错误包和运行证据在 [evidence/](evidence/)。

正式记录使用稳定 ID；每个文件开头的 ```ucv-bug``` JSON 块给出机器可读状态、基线和证据。正文保留现象、预期依据、复现/对照、根因和适用范围。历史 17 次 FAIL 缺少逐节点证据的边界仍按旧报告保留。

<!-- ucv:bugs:start -->

由 `ucv docs --write` 生成；目录表示当前处理状态，版本结论见各记录。

当前工程基线：`public-a0c2a26cb`。未复验项不继承历史通过结论。

## 未解决（7）

| ID | 问题 | 类型 | 本基线结论 | 关闭原因 |
|---|---|---|---|---|
| [LSU-CBO-NC-AF-001](open/LSU-CBO-NC-AF-001.md) | PBMT=NC 的 CBO 被误报 Store Access Fault | rtl | 未复验 | — |
| [LSU-HWPF-MISS-001](open/LSU-HWPF-MISS-001.md) | 硬件预取已 miss，性能事件 s2_hw_pf_miss 却恒为 0 | rtl | 未复验 | — |
| [LSU-MATCHINV-CAUSE-001](open/LSU-MATCHINV-CAUSE-001.md) | matchInvalid 回写仍携带 replay cause，LQ 建立伪重放项 | rtl | 未复验 | — |
| [LSU-PREFETCH-W-INTENT-001](open/LSU-PREFETCH-W-INTENT-001.md) | prefetch.w 丢失写意图，DCache 请求发成 M_PFR | rtl | 未复验 | — |
| [LSU-S3-KILL-WB-001](open/LSU-S3-KILL-WB-001.md) | redirect kill 的 S3 Load 仍驱动 ldout、intRF 和 lqWrite 写回 | rtl | 未复验 | — |
| [LSU-STD-PERF-001](open/LSU-STD-PERF-001.md) | StdExeUnit 的 STD_out_of_range_issue 性能计数器条件取反 | rtl | 未复验 | — |
| [LSU-STORE-TVAL-001](open/LSU-STORE-TVAL-001.md) | Store 故障 tval 未使用 TLB 指针掩码后的 fullva | rtl | 未复验 | — |

## 已关闭（0）

暂无登记条目。

<!-- ucv:bugs:end -->

## 旧证据

- [2026-10-26 错误包](evidence/bug-reports-20261026/)：7 个 RTL 根因、上游核查、误报/漏报和覆盖/交付复核。
- [`manifest/baseline.json`](../../manifest/baseline.json) 的 `failure_review` 仍保留机器可读的根因列表和最终 run 名称。
