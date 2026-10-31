# 验证经验与复盘

这里保存真实案例、错误决策、反证、修正依据和证据导航。可执行方法按
[`skills/<阶段>/<问题>.md`](../../skills/README.md) 独立维护，不再分成两本方法与案例混写的大手册。历史案例中的旧检查表、建议和计划作为原文保留，不作为另一份现行流程。历史 PASS、FAIL、XFAIL 和覆盖数字仍属于原报告的版本与运行。

## 从哪里开始

- [编译、构建与工具链经验](build-and-toolchain.md)：完整构建入口、已遇到的工具问题、补丁、搬迁重建及日志位置。

- [按阶段/问题选方法](../../skills/README.md)：每篇说明输入、怎么做、产出和验收；不只检查“是否完整”。
- [十二类踩坑案例](rtl-verification-soundness-20261026.md)：原手册的历史案例、错误判断、修正建议与来源，正文保留。
- [MMU 上游差分漏检，2026-10-29](mmu-upstream-escapes-20261029.md)：8 个失败探针/7 类行为的漏检机制与证明边界，外部证据仍未迁入。
- [验证包布局审计与迁移，2026-10-30](suite-layout-audit-20261030.md)：BPU/ICache fixture 集中、agent 边界、可执行审计及未迁移工程 backlog。
- [十工程布局迁移与 Pin Schema，2026-10-31](suite-layout-audit-20261031.md)：IFU/LSQ/LSU/MMU/DCache/Sbuffer/VAGQ 的根 fixture、pin schema、原生访问收口与真实判定。
- [目录、清理与 Skill 复核，2026-10-31](structure-skill-review-20261031.md)：保留 Python 命名空间的取舍，撤回“端口别名等于事务迁移”的错误标准，清理清单和技能合法性检查。
- [工程根命名空间重构，2026-10-31](suite-namespace-refactor-20261031.md)：删除十工程 *verify/common 外壳，修复 runner、资源锚点、安装包、反向依赖，逐 nodeid 对账与真实回归结果。
- [跨模块假阴性总结，2026-10-26](false-negatives-20261026.md)：案例矩阵、状态快照、诊断树和历史证据；它不是 skill 方法正文。

旧 skill 名称仅保留短导航以兼容已有引用。方法文件可按路径读取，不代表已向工具注册或自动加载。新仓库的维护规则见 [维护与验收](../maintenance.md)。

## 按工程查来源

| 工程 | 已保留的经验入口 | 主要内容 |
|---|---|---|
| BPU | [语义参考模型](../../suites/frontend/bpu/docs/semantic-reference-models.md)、[scoreboard 设计](../../suites/frontend/bpu/docs/scoreboard-design.md)、[缺陷与输入合同](../../suites/frontend/bpu/docs/bugs/README.md) | 预测事务身份、反馈归属、独立期望与缺陷边界 |
| ICache | [验证经验](../../suites/frontend/icache/docs/verification-lessons.md)、[错误复核](../../suites/frontend/icache/docs/error-review.md) | 跨路径组合、过宽放行、死字段与观察点缺失 |
| FTQ | [功能点与语义](../../suites/frontend/ftq/docs/functional-points.md)、[覆盖率闭环](../../suites/frontend/ftq/docs/coverage-analysis-20261030.md)、[分支槽溢出案例](ftq-resolve-capacity-20261029.md) | 自底向上层次、物理槽/来源枚举、100% 行覆盖下的容量缺陷、合法激励与不变量 |
| IFU | [功能点语义](../../suites/frontend/ifu/docs/functional-points.md)、[覆盖率闭环](../../suites/frontend/ifu/docs/coverage-loop.md)、[环境完整性案例](ifu-harness-integrity-20261029.md) | 自底向上六子模块+顶层组合、规范级参考模型、未覆盖分支的结构性证明、复位随机化/删除端口/端口宽度截窄的静默通过 |
| LSQ | [同源审计](../../suites/memblock/lsq/docs/reports/same-source-audit-20261022.md)、[假阳性复核](../../suites/memblock/lsq/docs/bug-reports-20261022/12-false-positive-review.md) | 独立模型、程序年龄与物理槽位、真实生产者约束 |
| DCache | [功能点审计](../../suites/memblock/dcache/docs/reports/functional-point-audit-20261025.md)、[防误报漏检复核](../../suites/memblock/dcache/docs/reports/soundness-recheck-20261026.md) | 功能点与实际断言对账、缺陷与检查器问题分离 |
| MMU | [验证可信度复核](../../suites/memblock/mmu/docs/reports/verification-soundness-20261025.md)、[上游漏检案例](mmu-upstream-escapes-20261029.md) | 并发采样、旧归因撤回、错误 oracle、组合/检查点缺口；上游探针仍在外部历史工作区 |
| Sbuffer | [独立审计](../../suites/memblock/sbuffer/docs/reports/independent-audit-20261024.md)、[二次裁决](../../suites/memblock/sbuffer/docs/reports/bug-recheck-20261024.md) | 空跑、排空超时、同字节竞争与检查器扰动 |
| LSU | [为什么没检查到](../../suites/memblock/lsu/docs/bug-reports-20261026/06-why-missed.md)、[复核总入口](../../suites/memblock/lsu/docs/bug-reports-20261026/README.md) | 同源期望、取消副作用、组合遗漏与覆盖结论边界 |
| VAGQ | [外部复盘入口](#vagq-external-evidence)、[验证工程](../../suites/vector/vagq/README.md) | 架构与协议层级、参考修正、XFAIL 解遮罩 |

## 历史路径对照

历史快照中的代码行号、旧命令和路径用于定位当时的材料；当前运行从根目录使用 `ucv`。路径对应关系如下：

| 原工作区路径 | 当前位置 |
|---|---|
| `bpu-verify-kunminghu-v3/` 的验证代码和文档 | `suites/frontend/bpu/` |
| `icache-verify-kunminghu-v3/` 的验证代码和文档 | `suites/frontend/icache/` |
| `memblock-hash/<suite>/` 的验证代码和文档 | `suites/memblock/<suite>/` |
| `vqgq-d4566d5-20261016/` 的可公开验证代码 | `suites/vector/vagq/` |
| 原工程 `results/`、`review/` 等证据树 | 外部历史工作区，通过 `history://<suite>/<relative-path>` 定位 |
| 顶层 `KMH-V3-VERIFICATION-FALSE-NEGATIVE-LESSONS-20261026.md` | [跨模块假阴性总结](false-negatives-20261026.md) |

历史工作区的本机位置由 `historical_roots` 配置，见 [外部接入说明](../local-configuration.md)。使用证据前应核对索引、文件可用性及哈希；未收录或缺失的文件需单独说明。

<a id="vagq-external-evidence"></a>

## VAGQ 外部复盘

以下复盘文件保持外部接入，其 SHA-256、大小与导入时可用性已记录在 [VAGQ 证据分片](../history/evidence/vagq.jsonl)，分片本身的哈希见 [证据主索引](../history/evidence-index.json)：

- `history://vagq/results/vagq-xfail-contract-review-20261018-v1/README.md`：XFAIL 逐项复核。
- `history://vagq/results/vagq-exhaustive-review-20261020-v1/README.md`：失败分类与覆盖边界。
- `history://vagq/results/vagq-reference-repair-rtl-rereview-20261020-v2/README.md`：参考修正与 RTL 重新复核。

这些引用保留经验来源；internal 源码、生成产物及包含内部源码的证据继续按 [外部接入说明](../local-configuration.md) 管理。

## 后续怎样积累

具体复盘保留在所属工程的 `docs/`，跨模块案例可放入本目录；对应合法/错误对照放回工程适用的测试或明确标识的探针入口。可复用方法更新 `skills/<阶段>/<问题>.md`，双方互链，不复制另一套正文。每条案例说明原假设、反例、修正依据、实际检查入口及尚未验证的部分；未执行的检查保留“待执行”。

原导入手册、速查卡与跨模块总结的哈希见 [经验迁移记录](../history/experience-import.json)，仍描述当时的导入快照，不改写为本次文件哈希。十二类案例现移至本目录，旧 skill 路径保留导航。整理文档不产生新的硬件验收结论。
