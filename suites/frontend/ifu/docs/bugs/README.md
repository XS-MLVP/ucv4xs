# IFU 问题记录

本目录按 `open/`、`closed/` 表示当前处理状态。每条正式记录以单个 `ucv-bug` JSON
块声明稳定 ID、类型和各基线结论；正文保留现象、预期、基线、复现、对照、根因、影响
范围和证据。旧基线的 PASS 不等于当前已修复，关闭必须提供复验证据。

<!-- ucv:bugs:start -->

由 `ucv docs --write` 生成；目录表示当前处理状态，版本结论见各记录。

当前工程基线：`public-a0c2a26cb`。未复验项不继承历史通过结论。

## 未解决（2）

| ID | 问题 | 类型 | 本基线结论 | 关闭原因 |
|---|---|---|---|---|
| [R-13](open/frontend-trigger-tdata2-width.md) | FrontendTrigger 忽略 tdata2 高 14 位，导致 EQ/GE 误命中与 LT 漏命中 | rtl | 未解决 | — |
| [R-14](open/instr-boundary-carry-ftq-owner.md) | InstrBoundary carry 误标跨块，导致完成指令的 FTQ 归属错误 | rtl | 未解决 | — |

## 已关闭（0）

暂无登记条目。

<!-- ucv:bugs:end -->
