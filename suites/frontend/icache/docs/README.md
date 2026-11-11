# ICache 文档

当前摘要、构建与运行入口见[工程 README](../README.md)。本目录按设计规格、验证规格
和问题记录组织；完整运行结果、波形和生成 RTL 不进入 Git。
工程根的 `verification_plan.json` 已删除；当前要求与实现入口见验证规格和事务合同，
实际缺陷见问题索引。历史报告中的旧计划路径和功能点统计保留原日期、基线与含义。

## 当前边界

- 基线：`public-a0c2a26cb` / DefaultConfig；11 个独立 DUT 均已完成 prepare/build 和冒烟。
- 收口后 seed 1 与 seed 2 均为 **572 PASS / 1 XFAIL，exit 0**；唯一非 PASS 是
  `WAYLOOKUP-020`（flush 同拍取消写仍锁存异常）的 strict XFAIL，见
  [未解决问题](bugs/open/waylookup-flush-cancelled-write-exception.md)。
- `ICACHE-012` 已由上游 `4b9f938b7` 修复并转为正向用例；`ICACHE-030` 的旧接口退役，
  改写为 FTQ `PrefetchQueue` 承接的握手合同。两者的历史失败记录和红/绿对照保留在
  [错误复核](spec/verification/error-review.md)与[新基线记录](spec/verification/reports/baseline-update-a0c2a26cb.md)。
- 2026-10-31 的交付报告和更早覆盖分析属于 `public-893e1580b`，保留原日期和基线，
  不与当前数字拼接。

## 文档入口

| 主题 | 入口 |
|---|---|
| DUT 层次、职责与配置边界 | [设计规格](spec/design/README.md) |
| 当前基线、逐 nodeid 对账、事务与覆盖 | [验证规格](spec/verification/README.md) |
| 新基线适配记录 | [baseline-update-a0c2a26cb](spec/verification/reports/baseline-update-a0c2a26cb.md) |
| 错误复核与模型修正 | [错误复核](spec/verification/error-review.md) |
| 覆盖闭环 | [整块 ICache](spec/verification/coverage/icache-coverage-closure.md)、[line/branch/toggle](spec/verification/coverage/coverage-line-toggle-branch.md) |
| 事务适配检查点 | [DataBank](spec/verification/transactions/databank-transaction-adaptation.md)、[MetaBank/SRAM](spec/verification/transactions/metabank-transaction-adaptation.md) |
| 历史交付报告和实验记录 | [交付报告](spec/verification/reports/verification-report.md)、[历史 README](spec/verification/evidence/legacy-readme-20261031.md) |
| 运行时 helper 归档 | [runtime-archive](spec/verification/evidence/runtime-archive.md) |
| 通用验证经验 | [验证经验](spec/verification/lessons/verification-lessons.md) |
| 问题状态 | [问题索引](bugs/README.md) |

## 维护约定

- 设计合同以 ISA/协议/接口意图为依据，不从生成 RTL 赋值反推期望；实现事实只在
  “端口可观测面”或“结构裁剪证据”中使用。
- 覆盖缺口必须按构造性不可达、合法域外、工具 don't-care、随机深度或真实功能缺失
  分类；不得为了数字改分母或扩大豁免。
- 新基线、新 seed 使用新结果目录；旧基线的 PASS 不自动成为当前已修，问题关闭需要
  新证据。
