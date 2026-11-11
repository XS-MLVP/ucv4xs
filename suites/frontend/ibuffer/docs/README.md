# IBuffer / VTypeGen 文档

当前摘要、构建与运行入口见[工程 README](../README.md)。本工程只验证 `IBuffer` 及其
真实子模块 `VTypeGen`；不是 Frontend、FTQ、ICache 或芯片验收。
工程根的 `verification_plan.json` 已删除；功能点与实现关联沿用既有功能点文档和合同，
配置/观察边界见退出标准，真实缺陷及复验状态见问题索引。历史报告中的计划统计保持原义。

## 当前边界

- 基线：`public-a0c2a26cb` / DefaultConfig；两个 DUT 均 `BUILT + SMOKE PASS`。
- seed 1 与 seed 2 完整集合均 **83 PASS / 0 FAIL / 0 ERROR / 0 XFAIL / 0 XPASS /
  0 SKIP / 0 UNCERTAIN**，nodeid 与 collection SHA 一致；功能点账本 **23/23 PASS**
  （硬件 19 + 环境 4）。
- 覆盖：`vtype_gen` line 163/163、branch 104/106、toggle 1226/1596；`ibuffer` 闭包
  line 4177/4209、branch 666/726、toggle 18524/20252。未覆盖项全部归因，见
  [覆盖率闭环](spec/verification/coverage/coverage-loop.md)。
- 无 blocking 残余；本层闭环不等于 Frontend/芯片验收。当前没有正式缺陷记录。

## 文档入口

| 主题 | 入口 |
|---|---|
| 设计层次、配置与接口合同 | [设计规格](spec/design/README.md) |
| vtype/IBuffer 合同正文 | [合同](spec/design/contracts.md) |
| 功能点、oracle 与验证责任 | [功能点](spec/design/functional-points.md) |
| 验证结果、覆盖和退出标准 | [验证规格](spec/verification/README.md) |
| 覆盖率闭环 | [coverage-loop](spec/verification/coverage/coverage-loop.md)、[摘要](spec/verification/coverage/coverage-summary.md) |
| 验证报告 | [verification-report](spec/verification/reports/verification-report.md) |
| 缺陷与设计边界观察 | [defects](spec/verification/defects.md) |
| 残余与结论边界 | [exit-criteria](spec/verification/exit-criteria.md) |
| 问题状态 | [问题索引](bugs/README.md) |

## 维护约定

- 期望来自 RISC-V V 规范、接口合同和独立模型，不从 RTL 赋值反推。
- 覆盖缺口按结构不可达、合法域外、工具 don't-care 或随机深度归因；不为数字驱动
  非法 padding 或无效 payload。
- 新基线、新 seed 使用新结果目录；关闭残余或缺陷必须有新的复验证据。
