# InstrUncache 问题记录

本目录按 `open/`、`closed/` 表示当前处理状态。每条正式记录以单个 `ucv-bug` JSON
块声明稳定 ID、类型和各基线结论；正文保留现象、预期、基线、复现、对照、根因、影响
范围和证据。

当前正式登记的 [FRONTEND-FLUSH-CONNECT](open/FRONTEND-FLUSH-CONNECT.md) 为
`kind=spec` 的待设计确认事项，在 `public-a0c2a26cb` 上保持 open，并阻塞完整验收。
原依据见[退出标准](../spec/verification/exit-criteria.md)、[缺陷判定](../spec/verification/defects.md)
和[结构证据](../spec/verification/evidence/flush-closure.json)；它不是已确认 RTL 缺陷。
工程根旧计划已删除，本记录承接既有稳定 ID 与未决状态，配置和观察边界仍由规格说明。

<!-- ucv:bugs:start -->

由 `ucv docs --write` 生成；目录表示当前处理状态，版本结论见各记录。

当前工程基线：`public-a0c2a26cb`。未复验项不继承历史通过结论。

## 未解决（1）

| ID | 问题 | 类型 | 本基线结论 | 关闭原因 |
|---|---|---|---|---|
| [FRONTEND-FLUSH-CONNECT](open/FRONTEND-FLUSH-CONNECT.md) | Frontend 将 InstrUncache flush 恒接 false 的设计意图与集成行为待确认 | spec | 未解决 | — |

## 已关闭（0）

暂无登记条目。

<!-- ucv:bugs:end -->
