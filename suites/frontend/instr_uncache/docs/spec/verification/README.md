# InstrUncache 验证规格

<!-- ucv:work-index:start -->

## DUT 工作索引

由 `ucv docs --write` 从配方与 workspace 生成；每行是一个 DUT 的合同入口。
当前工程基线：`public-e716c7658`。接入观察不代表验证进度或验收结果。

负责人、当前工作、下一步、阻塞与验收证据维护在对应合同正文或关联任务中；
未认领不推断负责人；各 DUT 独立实现、选跑与验收。

| DUT / RTL top | 接入观察 | 验证合同 | 工作入口 |
|---|---|---|---|
| `instr_uncache_entry` / `InstrUncacheEntry` | 已有资产；本基线待复验 | [范围、工作与完成条件](README.md) | [实现、用例与命令](../../../testbenches/instr_uncache_entry/README.md) |
| `instr_uncache_resp_arbiter` / `Arbiter1_InstrUncacheResp` | 已有资产；本基线待复验 | [范围、工作与完成条件](README.md) | [实现、用例与命令](../../../testbenches/instr_uncache_resp_arbiter/README.md) |
| `instr_uncache` / `InstrUncache` | 已有资产；本基线待复验 | [范围、工作与完成条件](README.md) | [实现、用例与命令](../../../testbenches/instr_uncache/README.md) |

<!-- ucv:work-index:end -->

## 当前工作（public-e716c7658）

负责人：三个 DUT **待认领**；按 Entry、响应仲裁器、顶层合同分别记录责任人与证据。
当前工作：重新核对单 outstanding、请求/响应与 WFI 合同及当前裁剪端口，随后按 DUT
适配环境、建立新基线原生资源并复验。工具身份和缺失闭包见[全仓状态](../../../../../../docs/status.md)。

阻塞：当前基线硬件验收证据尚无；[FRONTEND-FLUSH-CONNECT](../../bugs/open/FRONTEND-FLUSH-CONNECT.md)
继续承接设计确认缺口。其 Frontend 集成验证任务链接
[frontend_top/frontend 合同](../../../../frontend_top/docs/spec/verification/frontend.md)，
保留单一问题记录，完成本包单元用例不自动关闭该问题。

## 历史验证范围（public-a0c2a26cb）

三个 DUT 的单元可达行为曾在 `public-a0c2a26cb` / DefaultConfig 上通过双 seed 回归；
当时整体仍为 **INCOMPLETE**，因为 flush 设计决定没有 owner 签字，也没有 Frontend 集成验证。

## 范围与假设

- DUT：`instr_uncache_entry`、`instr_uncache_resp_arbiter`、`instr_uncache`；层次和
  配置见[设计规格](../design/README.md)。
- 顶层保留真实 Entry/Arbiter RTL；模型只提供期望值。
- `flush` 在 DefaultConfig 下恒为 0，取消路径不可达；`R-FLUSH` 是 out-of-domain /
  accepted-limited，不能读成“flush 已验证”。
- 功能要求与实现关联见[功能点](../design/functional-points.md)和[设计合同](../design/contracts.md)。
  工程根的 `verification_plan.json` 已删除，历史报告中的功能点统计保持原运行含义。

## 历史结果（2026-11-08）

| 项 | 结果 |
|---|---|
| prepare/build | 三个 DUT 均 `BUILT + SMOKE PASS` |
| seed 1 / seed 2 | 各 **68 PASS / 0 UNCERTAIN / 0 FAIL / 0 ERROR**（68 nodeid，一致） |
| 功能点 | 硬件 **13/13 PASS**、环境 **4/4 PASS**（含 `INC-FLUSH-012` 结构证据） |
| `ucv report` | `run_status=PASS`、`hardware_verdict=INCOMPLETE`、`migration_acceptance=NOT_CERTIFIED` |
| blocking/open | `FRONTEND-FLUSH-CONNECT` |

上表报告字段来自 2026-11-08 的冻结运行。新运行冻结 `docs/bugs/` 中的问题记录，
不再读取旧计划残余；[FRONTEND-FLUSH-CONNECT](../../bugs/open/FRONTEND-FLUSH-CONNECT.md)
已按 `kind=spec` 登记，在当前基线仍为 open，承接既有设计确认/集成缺口。
带 `acceptance_source='issue-records'` 的新运行会据此将纯 PASS 汇总为 `INCOMPLETE`，
保留实际 case 计数，真实 FAIL/ERROR 优先。本记录不是已确认 RTL 缺陷，也不新增执行证据。

`INC-FLUSH-012` 是验证环境分区的结构检查点：验证 `Frontend.scala:266` 的恒 0 裁剪与
记录哈希一致，不驱动 flush、不是行为验证、不计硬件通过率。机器证据在
[flush-closure.json](evidence/flush-closure.json)，由
`tools/audit_flush_closure.py` 复核；证据变化时用例会失败并要求重新分类。

## 验证内容

| 主题 | 入口 |
|---|---|
| 合同、端口裁剪与时序 | [设计合同](../design/contracts.md) |
| 功能点 → oracle/driver/monitor/checker/用例 | [功能点](../design/functional-points.md) |
| 请求/对齐/resend/WFI/单 outstanding 等定向覆盖 | [覆盖闭环](coverage/coverage-loop.md)、[摘要](coverage/coverage-summary.md) |
| 实际命令、RTL/产物哈希、seed、逐 DUT 判定 | [验证报告](reports/verification-report.md) |
| 缺陷判定标准与设计边界 | [defects](defects.md) |
| 残余登记与结论边界 | [exit-criteria](exit-criteria.md) |
| flush 结构证据 | [flush-closure.json](evidence/flush-closure.json) |
| 问题状态 | [问题索引](../../bugs/README.md) |

## 完成条件与缺口

- `FRONTEND-FLUSH-CONNECT` 确认前，整体保持 **INCOMPLETE**；不得写成硬件 PASS，
  也不得把 `INC-FLUSH-012` 写成 flush 行为通过。
- flush 期间/迟响应的取消语义、Frontend 级 flush/redirect 交互、TL 反压、真实 L2
  行为、其他 `nMmioEntry` 配置和 Frontend/芯片验收均未证明。
- 覆盖残余（地址高位、对齐位、don't-care 数据等）按[覆盖闭环](coverage/coverage-loop.md)
  归因，不用非法激励追数字。
- 新配置或生成哈希变化时，重新执行 `tools/audit_flush_closure.py` 并单独标注结论。
