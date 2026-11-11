# Sbuffer 验证约束

本页保存**设计/验证范围、资源策略和合法输入域约束**，不是当前缺陷，也不表示设计或
接口已经退役。条目沿用历史 `manifest/known-issues.json` 的稳定 ID、原分类和依据；
它们不再放在 `docs/bugs/`，因为 `open`/`closed` 记录只表示需要处置的问题。当前缺陷和
误报分类见 [bugs/](../../bugs/README.md)。

最近完整验证绑定 `public-893e1580b`；当前默认基线为 `public-a0c2a26cb`，本工程尚未在
当前基线重新构建或回归。以下约束本身仍需在对应 DUT 范围内遵守。

| 稳定 ID | 原分类 | 当前处理 |
|---|---|---|
| `WLINE-ZERO-PAYLOAD-ONLY` | `scope_constraint` / `enforced_in_parent_tests` | 合法输入域约束 |
| `NO-VPI-NO-INTERNAL-CFG` | `scope_decision` / `enforced` | 公开端口范围约束 |
| `NO-PER-CYCLE-DUMP` | `resource_policy` / `enforced` | 证据资源策略 |

## WLINE-ZERO-PAYLOAD-ONLY

- **原分类**：`scope_constraint` / `enforced_in_parent_tests`；稳定 ID 保留为
  `WLINE-ZERO-PAYLOAD-ONLY`。
- **约束**：父块只在 `cbo.zero` 产生 `wline`，且 payload 恒为 0；顶层 UT 不再用非零
  payload 驱动 `wline`。`SbufferData` 模块级的非零整行广播只作为模块能力，不代表父块
  可达行为。
- **依据**：`NewStoreQueue.scala` 的 `wline := isCbo && isCboZero`、`cbo.zero` 数据置
  0 和 RTL 断言 “wline only supports whole zero write now”；
  [SBT-WRITE-01 功能点](../design/functional-points-sbuffer.md)、
  [SBD-WRITE-02 功能点](../design/functional-points-sbuffer-data.md)、
  [顶层 UT 报告](evidence/sbuffer-top-20261024.md)、
  [历史问题台账](../../../manifest/known-issues.json) 的同名条目。
- **当前状态**：约束；如果父块未来把 `wline` 用于非 `cbo.zero` 场景，需要重新定义合法域
  并补顶层用例。不是设计退役。

## NO-VPI-NO-INTERNAL-CFG

- **原分类**：`scope_decision` / `enforced`；稳定 ID 保留为
  `NO-VPI-NO-INTERNAL-CFG`。
- **约束**：Sbuffer/SbufferData DUT 构建不启用 `--vpi`，也不启用
  `--internal`/internal-cfg；测试只使用公开端口。内部信号不可访问，诊断由公开输出和
  覆盖率承担。
- **依据**：历史构建
  `results/builds/20261024T024302843131Z-modules/sbuffer/report.json` 记录 `vpi=false`、
  `internal_signal_config=false`；[工具链清单](../../../manifest/toolchain.json)、
  [历史问题台账](../../../manifest/known-issues.json) 的同名条目。
- **当前状态**：有意范围约束；不重新引入 VPI。不是设计退役。

## NO-PER-CYCLE-DUMP

- **原分类**：`resource_policy` / `enforced`；稳定 ID 保留为
  `NO-PER-CYCLE-DUMP`。
- **约束**：运行不保存逐周期信号或事务 dump；不使用 `--keep-coverage-inputs`，不写
  JSONL/逐拍 trace。证据只保留覆盖率数据库、功能覆盖 JSON、manifest 和审计报告。
- **依据**：[运行入口](../../../tools/run.py) 的 trace policy 生成与检查逻辑、
  [交付自检](../../../tools/verify_delivery.py)、
  [历史问题台账](../../../manifest/known-issues.json) 的同名条目（引用历史运行
  `results/sbuffer-top-contract-03/trace-policy.json`）、
  [顶层 UT 报告](evidence/sbuffer-top-20261024.md)。
- **当前状态**：有意资源策略；调试 trace 需显式开启并受大小上限约束。不是设计退役。

## 相关入口

- [Verification spec](README.md)
- [历史问题台账](../../../manifest/known-issues.json)
- [问题记录](../../bugs/README.md)
