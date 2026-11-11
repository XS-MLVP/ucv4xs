# VAGQ 资料入口

## 开始工作

- [工程入口](../README.md)与运行命令。
- 从仓库根运行 `./scripts/ucv info vagq --dut VAGQ`：生成规格、源码、RTL、环境和测试资源地图；
  `info` 只展开有效 baseline 的 `.cache/sources` 路径，internal checkout 由
  `ucv prepare vagq --source-only` 按本机 `source_mirrors` 接入。
- `./scripts/ucv check vagq`：检查登记文件、问题记录和当前页面链接。

## 工程规格

- [Design spec](spec/design/README.md)：VAGQ 顶层与 11 个组件的职责、公共接口、行为边界和未确认项。
- [Verification spec](spec/verification/README.md)：验证分层、场景矩阵、覆盖计划、当前记录和未关闭项。
- [问题记录](bugs/README.md)：当前 open/closed 状态；不复制 internal 源码或证据。
- [外部证据说明](spec/verification/evidence/README.md)：外部复盘入口、使用限制和本仓库保留的公开记录。

VAGQ 没有逐 DUT 独立 spec 文件：`workspace.json` 的 `design_spec` / `verification_spec`
对 12 个 DUT 统一指向上述共享详细页，页内按 DUT 链接已有公开参考模型、契约模型和测试，
并登记 internal 源码相对路径。它们是**共享逐 DUT 资料入口**，代码实现和测试入口
**不能代替独立设计依据**（RVV/ISA、协议合同和待确认的设计要求）。

## 维护约定

- 设计要求维护在 `spec/design/`，验证场景和判定维护在 `spec/verification/`。
- 普通回归、显式 campaign 和外部复盘分开登记；SKIP 不冒充 PASS。
- 重要历史运行材料保持外部接入；本目录不建立泛化 history 或 internal 证据副本。
- 文档路径变化时同步更新 Python docstring、工具生成文本和导航；历史判定、日期与基线不改写。
- 具体约定见根 [文档维护](../../../../docs/how-to/maintain-docs.md)。
