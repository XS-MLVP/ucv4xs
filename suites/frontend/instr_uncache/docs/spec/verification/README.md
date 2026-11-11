# InstrUncache 验证规格

状态：三个 DUT 的单元可达行为在 `public-a0c2a26cb` / DefaultConfig 上通过双 seed
回归；整体仍为 **INCOMPLETE**，因为 `FRONTEND-FLUSH-CONNECT` 的 flush 设计决定没有
owner 签字，也没有 Frontend 级集成验证。本页是当前验证入口。

## 范围与假设

- DUT：`instr_uncache_entry`、`instr_uncache_resp_arbiter`、`instr_uncache`；层次和
  配置见[设计规格](../design/README.md)。
- 顶层保留真实 Entry/Arbiter RTL；模型只提供期望值。
- `flush` 在 DefaultConfig 下恒为 0，取消路径不可达；`R-FLUSH` 是 out-of-domain /
  accepted-limited，不能读成“flush 已验证”。
- 功能要求与实现关联见[功能点](../design/functional-points.md)和[设计合同](../design/contracts.md)。
  工程根的 `verification_plan.json` 已删除，历史报告中的功能点统计保持原运行含义。

## 当前结果

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
