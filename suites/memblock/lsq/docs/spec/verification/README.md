# LSQ Verification Spec

状态：验证侧当前索引。**完整硬件结论仍为非 PASS；历史运行与本轮限定事务适配验收分开。**

## 1. 范围与基线

- 工程：`suites/memblock/lsq`；38 个 DUT/运行键，覆盖叶子、Load/Store 业务块和 `LsqWrapper`。
- 最近完整运行记录：2026-11-06，`public-a0c2a26cb`，seed 1，2600 个节点，**2369 PASS / 231 FAIL**；运行前后 `source_sha256=8ede0b3b…`。该结果来自 [interaction-probes-20261106.md](evidence/reports/interaction-probes-20261106.md)，2026-11-09 文档整理时未重跑；2026-11-11 仅适配定向验收，见第6节。
- 历史旧基线：2026-10-18/19 报告绑定 `XiangShan 893e1580…`；与当前 `public-a0c2a26cb` 的数字不可合并。基线与 RTL 哈希见 [`manifest/baseline.json`](../../../manifest/baseline.json)。

## 2. 功能点与检查

- 可执行矩阵：[`testbenches/lsq_wrapper/coverage/function_points.py`](../../../testbenches/lsq_wrapper/coverage/function_points.py)。8 kind × 6 outcome 共 48 格；2026-11-06 记录为 **23 pass / 2 fail / 4 gap / 19 na / 0 out-of-domain**。
- 指令来源映射：[instruction-source-mapping.md](../design/contracts/instruction-source-mapping.md)；kind × outcome 语义：[kind-outcome-matrix.md](../design/contracts/kind-outcome-matrix.md)。
- 交互窗口：[interaction-semantics.md](../design/contracts/interaction-semantics.md) 的 B1–B8 与 `function_points.INTERACTION_WINDOWS`。2026-11-06 记录为 **2 fail / 2 gap / 1 pass**。
- 自检：`testbenches/lsq_wrapper/tests/meta/test_function_points.py`（14 项）和 `testbenches/lsq_wrapper/tests/meta/test_critical_fields.py`（5 项）检查矩阵完整性、证据存在性和缺失端口声明；修改矩阵/合同后必须重新运行。

## 3. 覆盖与证据

| 证据 | 位置 | 边界 |
|---|---|---|
| 2026-11-06 交互回归 | [interaction-probes-20261106.md](evidence/reports/interaction-probes-20261106.md) | v2 为修正 NC 假阳性后的权威记录；v1 作废。 |
| 2026-11-03 功能点/上游核查 | [function-points-and-skill-20261103.md](evidence/reports/function-points-and-skill-20261103.md)、[upstream-audit-20261103.md](evidence/reports/upstream-audit-20261103.md) | 发现 MMIO Store 总线故障上报缺口；两次运行中源码变化的记录已作废。 |
| 2026-10-22 错误包 | [bugs/evidence/bug-reports-20261022](../../bugs/evidence/bug-reports-20261022) | 11 个旧根因 + 4 个关系核验新增根因 + 1 个配置问题；旧计数不重算。 |
| 2026-10-18/19 阶段报告 | [evidence/reports](evidence/reports) | 保留原基线、覆盖分母、真实 FAIL 和结论边界。 |
| 当前问题 | [bugs/open](../../bugs/open)、[bugs/closed](../../bugs/closed) | 稳定 ID；目录决定当前状态。 |

## 4. 当前问题与缺口

- 当前目录为 **17 open / 2 closed**。17 个 open 中，13 个在当前基线 `public-a0c2a26cb` 有 2026-11-02/03/06 的完整回归、逐条源码核对或交互探针证据（状态 `open`）；4 个当前基线只有旧记录/缺口、没有逐节点复验（`LQU-MMIO-IF-001`、`VSQ-REDIR-IF-001`、`LSQ-UPSTREAM-6704`、`LSQ-UPSTREAM-6688`，状态 `unverified`）。
- 2 个 closed 为 `FWD-SQID-001`、`LRQ-STRICT-001`：`docs/history/lsq-regression-a0c2a26cb-20261102.json` 的 2026-11-02/03 新基线完整回归记录对应节点 FAIL→PASS，上游 `302c0fe19`/`73cc6ee42` 已进入当前基线；旧基线版本仍保留为 open，旧报告不删除。该关闭不是仅复制旧状态，也不代表本次文档整理重跑了 native。
- 旧 2026-10-22 错误包的 15 个 RTL bug 计数是旧基线/上游关系核验口径；当前目录按各基线证据分别记录，不能把两条新基线已修复项继续算作当前 open，也不能据此把其余根因写成已修复。
- 已知验证缺口：向量首次路由、segmented vector store + AMO、deq credit 类型、CBO TLB miss、跨页第二页可见性；详见 [kind-outcome-matrix.md](../design/contracts/kind-outcome-matrix.md#4-显式缺口条目与矩阵同格式) 与 [interaction-semantics.md](../design/contracts/interaction-semantics.md)。
- 当前 231 FAIL 中仍包含真实 RTL 反例和未关闭语义/模型残余；不能把历史报告中的局部 PASS、DA 满或“检查器通过”当作整体验收。

## 5. 完成条件

一个 DUT/组合只有在以下条件同时满足时才能声明验收：

1. 设计要求有合同或独立 ISA/协议依据，且未确认项已关闭或明确排除；
2. 对应 kind × outcome 格和交互窗口有必达激励、独立预期、真实观察点和合法对照；
3. 真实 FAIL 保留为 FAIL，不以 xfail/skip/waiver 消除；
4. 覆盖分母和缺口逐项分类，未把声明式 bin 采样当作语义 reached/checked；
5. 当前基线重新构建、运行并保留源码/种子/构建/RTL 哈希；本文档整理不提供这些新证据。

当前实施计划（范围、层次、顺序和完成条件）见 [plan.md](plan.md)；2026-10-18/19 的逐轮进度和旧里程碑见 [evidence/plan-progress-20261018-20261019.md](evidence/plan-progress-20261018-20261019.md)，保留旧基线 `893e1580…` 和原结论。

## 6. 事务适配的限定接受范围

2026-11-11，`public-a0c2a26cb` / DefaultConfig：已审查事务适配范围接受，不改变
第5节的硬件完成条件，也不修订旧报告、功能点 checked 数字或问题关闭状态。

- 七族及 LoadUncache 的刺激所有权独立于参考模型事件，Wrapper 场景与三个历史
  checker 消费 typed request/前后沿快照。原模型函数 AST 无修改或删除；错误valid、
  byte来源、generation与生命周期负对照仍拒绝，省略字段不等于显式0/False。
- 20 个受影响 DUT 当前 key/完整基线/active/native/RTL/真实冒烟匹配，最后统一入口
  68个原功能节点为 **65 PASS / 3 FAIL**，另22自检PASS。最后只改一个未选中的Deq
  用例调用，恢复原未指定valid的断言域；单独统一入口全4原参数仍4 FAIL，wline错误
  不消除。两次运行的源码身份分别稳定，不把后一个4项说成重跑了前68项。
- 原711叶子选择、96父级选择、136 Wrapper中间冻结以及返修定向证据分别保留；
  有重叠，不累计PASS。58个父级定向流的1567记录/28312字段与原期望、实际、mask、
  相位一致；这是最后96稿和Deq单点最后复验的明确组合，不是一次全量运行。
- 最后68项当前选择中可对比的43个非空输入/输出流一致；14个没有原projection、
  2个不符合projection窗口schema，不声称这些缺失流相等。叶子完整Journal及两个
  Replay随机种子的独立保全证据另列，不能将语法审计推及所有随机种子。
- 当前 collection=2608，原2600无删除、参数/标记不变，7个fixture来源搬迁单列；
  8个新增适配自检不计硬件功能提升。严格事务命令仍exit1，三个原业务kind标签已人工
  分类，但人工分类不是该命令PASS。未执行最终全2608、其它18 DUT或覆盖闭环。

本机完整收据、起点源码与保护核对保存在 `results/transaction-adapters-20261110/lsq/`，
入口为 `independent-final-review.md`、`takeover-final-evidence-audit.json`；这些忽略产物
不随Git发布。硬件summary的FAIL、原非PASS及未确认责任边界继续保留。
