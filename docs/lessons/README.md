# 验证经验与复盘

这里索引已有的错误假设、误报与漏检复盘、修正方法及证据来源。跨模块经验保留具体案例；模块细节继续在各工程维护。历史 PASS、FAIL、XFAIL 和覆盖数字仍属于原报告的版本与运行。

## 从哪里开始

- [编译、构建与工具链经验](build-and-toolchain.md)：完整构建入口、已遇到的工具问题、补丁、搬迁重建及日志位置。

- [防复发速查卡](../../skills/rtl-verification-soundness/CARD.md)：开始新模块或修改检查器前，定位相关的十二类历史坑。
- [踩坑复盘与防复发手册](../../skills/rtl-verification-soundness/SKILL.md)：按“实际问题 → 错误判断 → 原因 → 修正 → 成对回归”保留经验。
- [跨模块假阴性总结，2026-10-26](false-negatives-20261026.md)：保留原案例矩阵、状态快照、诊断树和待完成事项。

`skills/` 中的手册可按路径读取复用；文件存在不代表已向工具注册或自动加载。新仓库的维护规则见 [维护与验收](../maintenance.md)。

## 按工程查来源

| 工程 | 已保留的经验入口 | 主要内容 |
|---|---|---|
| BPU | [语义参考模型](../../suites/frontend/bpu/docs/semantic-reference-models.md)、[scoreboard 设计](../../suites/frontend/bpu/docs/scoreboard-design.md)、[缺陷与输入合同](../../suites/frontend/bpu/docs/bugs/README.md) | 预测事务身份、反馈归属、独立期望与缺陷边界 |
| ICache | [验证经验](../../suites/frontend/icache/docs/verification-lessons.md)、[错误复核](../../suites/frontend/icache/docs/error-review.md) | 跨路径组合、过宽放行、死字段与观察点缺失 |
| LSQ | [同源审计](../../suites/memblock/lsq/docs/reports/same-source-audit-20261022.md)、[假阳性复核](../../suites/memblock/lsq/docs/bug-reports-20261022/12-false-positive-review.md) | 独立模型、程序年龄与物理槽位、真实生产者约束 |
| DCache | [功能点审计](../../suites/memblock/dcache/docs/reports/functional-point-audit-20261025.md)、[防误报漏检复核](../../suites/memblock/dcache/docs/reports/soundness-recheck-20261026.md) | 功能点与实际断言对账、缺陷与检查器问题分离 |
| MMU | [验证可信度复核](../../suites/memblock/mmu/docs/reports/verification-soundness-20261025.md) | 并发采样、失活用例、独立 oracle、旧归因撤回 |
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

具体复盘写入所属工程的 `docs/`，对应的合法对照和错误对照放入该工程的 `tests/`；跨模块可复用的经验补入手册并从本页链接。每条说明原假设、反例、修正依据、实际检查入口及尚未验证的部分。没有执行过的检查保留“待执行”状态。

本次补迁保留了原工作区的手册、速查卡与跨模块总结，原文件和迁入文件的哈希见 [经验迁移记录](../history/experience-import.json)。整理文档不产生新的硬件验收结论。
