# InstrUncache 文档

当前摘要、构建与运行入口见[工程 README](../README.md)。本工程只验证 `InstrUncache`
及其真实内部层次；不是 ICache/IFU/Frontend 或芯片验收。
工程根的 `verification_plan.json` 已删除；当前功能要求和未证明范围沿用既有功能点、
合同与退出标准。下方报告字段保留 2026-11-08 的运行含义；新报告依据实际用例及正式
问题快照判定。[FRONTEND-FLUSH-CONNECT](bugs/open/FRONTEND-FLUSH-CONNECT.md) 已作为
`spec` 问题承接既有 open 状态，仍阻塞当前基线的完整验收，不是已确认 RTL 缺陷。

## 当前边界

- 基线：`public-a0c2a26cb` / DefaultConfig；三个 DUT 均 `BUILT + SMOKE PASS`。
- seed 1 与 seed 2 各 **68 PASS / 0 UNCERTAIN / 0 FAIL / 0 ERROR**（68 nodeid，
  两轮 nodeid 一致）；功能点账本硬件 **13/13 PASS**、环境 **4/4 PASS**。
- `ucv report` 为 `run_status=PASS`、`hardware_verdict=INCOMPLETE`：
  `FRONTEND-FLUSH-CONNECT` 仍 blocking/open；`migration_acceptance=NOT_CERTIFIED`。
  单元可达行为通过，但 `Frontend` 把 `instrUncache.io.flush` 恒接 `false.B` 的设计
  决定没有 owner 签字，也没有 Frontend 级集成验证，不能写成硬件 PASS 或
  “flush 已验证”。
- `R-FLUSH` 为 out-of-domain / accepted-limited；`INC-FLUSH-012` 是验证环境分区的
  结构检查点，不驱动 flush、不计硬件通过率。

## 文档入口

| 主题 | 入口 |
|---|---|
| 层次、配置与接口合同 | [设计规格](spec/design/README.md) |
| Scala/ISA/TileLink 合同正文 | [合同](spec/design/contracts.md) |
| 功能点与验证责任 | [功能点](spec/design/functional-points.md) |
| 当前验证结果与判定 | [验证规格](spec/verification/README.md) |
| 覆盖率闭环与摘要 | [coverage-loop](spec/verification/coverage/coverage-loop.md)、[摘要](spec/verification/coverage/coverage-summary.md) |
| 验证报告 | [verification-report](spec/verification/reports/verification-report.md) |
| flush 结构证据 | [flush-closure.json](spec/verification/evidence/flush-closure.json) |
| 缺陷与设计边界 | [defects](spec/verification/defects.md) |
| 残余与结论边界 | [exit-criteria](spec/verification/exit-criteria.md) |
| 问题状态 | [问题索引](bugs/README.md) |

## 维护约定

- 设计裁剪是结构事实，不是行为验证；端口重新出现必须让绑定失败并显式迁移。
- 合法物理地址上限、对齐常量、TL 字段裁剪和 don't-care 数据不能用非法激励去覆盖。
- 新基线/配置使用新结果目录；flush 连接或 `nMmioEntry`/`MmioBusWidth`/PMA 上限/
  生成哈希变化时，必须重跑并单独标注结论。
