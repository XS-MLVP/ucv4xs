# Sbuffer 资料入口

## 开始工作

- [工程入口](../README.md)与运行命令。
- 从仓库根运行 `./scripts/ucv info sbuffer --dut sbuffer`：生成规格、源码、RTL、环境和测试资源地图；
  每个 DUT 已登记模块功能点、验证报告和固定 `public-a0c2a26cb` 的 Chisel 定义/实例化来源。
- `./scripts/ucv check sbuffer`：检查登记文件、问题记录和当前页面链接。

## 工程规格

- [Design spec](spec/design/README.md)：Sbuffer 层次、写合并/排空/转发合同和两个 DUT 的功能点。
- [Verification spec](spec/verification/README.md)：验证范围、场景/用例映射、覆盖率口径、当前记录和未关闭项。
- [验证约束](spec/verification/constraints.md)：范围、资源和合法输入域约束（稳定 ID），不是当前缺陷。
- [问题记录](bugs/README.md)：以稳定 ID 保存当前 open/closed 状态；修复复验前不把历史处置推到当前基线。
- [历史验证证据](spec/verification/evidence/README.md)：逐 DUT 报告、flush 合同复核、独立审计和旧版说明。
- [历史问题台账](../manifest/known-issues.json)：迁移来源与历史证据，当前状态以 `bugs/` 目录为准。

## 维护约定

- 设计要求维护在 `spec/design/`，验证场景和判定维护在 `spec/verification/`。
- 一般运行计数、覆盖表和汇总放在新的运行结果目录，由 `ucv report` 生成。
- 重要历史运行材料留在 `spec/verification/evidence/`，不另建工程级 history 目录。
- 文档路径变化时同步更新测试 docstring、manifest、`tools/verify_delivery.py` 和导航；历史判定、日期与基线不改写。
- 具体约定见根 [文档维护](../../../../docs/how-to/maintain-docs.md)。
