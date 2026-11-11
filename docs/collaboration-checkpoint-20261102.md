# 协作发布检查点（2026-11-02）

> 后续变更说明：该检查点收尾后，用户要求将公开默认基线升级到上游`kunminghu-v3`
> 分支头`a0c2a26cb...`。本页的功能/收集/源码匹配结果仍属于收尾时的旧
> `public-893e1580b`及各自记录的验证源码，不重标为新基线结果。新基线尚未生成/构建/
> 冒烟/功能回归，详见[升级记录](history/baseline-kunminghu-v3-20261102.json)。

## 这次交付什么

按用户要求结束本轮连续适配，整理为**供其他贡献者接续的协作检查点**。
交付重点是统一目录、命名、运行和交接规则；不是“十工程/132 DUT全部事务适配完成”，
也不是全仓硬件全绿版本。整体目标保留未完成范围，收尾后暂停，不标 complete/unmet。

目录与分工唯一入口为 [CONTRIBUTING.md](../CONTRIBUTING.md)，仓库约束见
[AGENTS.md](../AGENTS.md)。人工与AI贡献者遵守同一规则；不再创建 `*verify/common`
外壳，不为发布批量重排已有工程。每项工作沿用当前工程/DUT的布局和根fixture。

**收尾时发布状态**：捕获本检查点时没有创建新 commit、tag、GitHub release 或推送。
本检查点整理时 HEAD 为 `001735033979f52712808b25280efc262a48654f`，它是上一已提交
检查点，不包含本轮后续修改。发布者应先审查并提交当前改动，再把实际新 commit/tag
交给协作者；不要让他人只按上述旧 HEAD 接手。不要将整个本机工作目录压包发布。

用户随后已授权把本阶段检查点、协作约定和新基线更新一并提交并推送到
`XS-MLVP/ucv4xs`的`main`。实际发布提交以Git历史及远端分支为准；上面的旧HEAD和
“未提交”描述仅保留捕获时状态，不表示后续没有提交。

## 已核验的收尾结果

| 检查 | 实际结果 | 范围/限制 |
|---|---|---|
| 根 `tests/` | **266 PASS** | 编排、工具、运行时与真实pytest报告桥接自检 |
| ICache 完整、seed2 | **567 PASS / 3 XFAIL** | 原412项均保留且判定不变；新增158项PASS，无新增XFAIL |
| DataBank＋MetaBank、seed2 | **305 PASS** | 当前两DUT全部选择，不是完整ICache第二次运行 |
| 同源码 DataBank＋MetaBank、seed1 | **305 PASS** | 与seed2源码身份相同，原生构造实际转发seed |
| MainBTB 完整、seed2 | **2854 PASS / 9 FAIL** | native159/9、pure2695，真实反例保留 |
| 同源码 MainBTB定向、seed1 | **136 PASS / 9 FAIL** | native66/9、pure70，不冒称完整BPU双seed |
| 十工程目录/fixture结构 | **PASS** | `audit-suite-layout.py --strict`；不是事务/硬件验收 |
| 十工程最新collection | **49078项** | 十个收集任务exit0；初始45883及上一48809无删除/逐工程相对顺序变化，仅收集不是硬件PASS |
| Skill与锁定框架能力 | **PASS** | 20篇方法文档；API存在不代表行为认证 |
| 全仓严格事务边界 | **exit1，真实债务保留** | 不以豁免或搬目录取得绿色，详见下表 |

ICache当前源码身份为
`b48dc54b08a3febfc7d0ba54f867e6a95efe15e1689d04419fcaa8f8a473d4b2`。
完整回归387个native实例、66个构建文件；两DUT各次131个native实例、12个构建文件，
全部源码/产物/processor/build hash已核验，native构建未变。覆盖产物完整不等于覆盖闭环；
runner已清理的原始覆盖输入不声称仍逐份可用。

最新collection source为`602ea9a6...`，4159个记录文件当前逐hash匹配、source_after稳定。
`full`含外部internal VAGQ，本次未冒称统一公开基线硬件验收；CLI exit1仍保留IFU已登记
残余，不是收集任务失败。不得再把此前48809项称为当前新增控制后的总数。

MainBTB当前源码身份为
`606640f86555fe7a05f83c5399f10a85cb3ccb08107c75657189ab592fd9f399`。
九条FAIL现在实际报告七条原始semantic-reference比较及两条shared-service写回比较，
不再由缺sample/交付见证的次生错误遮盖；不是仅根据FAIL数量相同作出的结论。

收尾运行与机器记录见
[本检查点证据](history/collaboration-checkpoint-20261102.json)、
[MainBTB终态/归因记录](history/transaction-goal-mbtb-disposition-index-20261102.json)和
[MetaBank/SRAM记录](history/transaction-goal-icache-metabank-dft-20261102.json)。
本机完整结果在忽略的 `results/ucv-collaboration-checkpoint-*`，Git只保存简短索引与哈希。

## 可分工的接续范围

| 工程/路径 | 当前边界与接手项 |
|---|---|
| `suites/frontend/ifu/` | 七DUT当前适配已核验；保留R-13两FAIL、R-14三FAIL及R-09 UNCERTAIN。后续仍可补新合同/组合反证，不能改历史为PASS |
| `suites/frontend/ftq/` | 三DUT当前事务链、采样、输入来源、收尾已核验；完整905PASS/2XFAIL，两个严格容量XFAIL保留 |
| `suites/frontend/bpu/` | PHR/共享pipeline及MainBTB已取得多轮来源与生命周期修复；其他DUT、剩余API/调度组合与24处功能owner访问继续审计。九条MainBTB反例不豁免 |
| `suites/frontend/icache/` | DataBank/MetaBank本轮迁移与非零模拟SRAM控制已有生产实现/正反控制；完整API/调度组合与更多直接采样/身份反证尚未全部签核，其余九DUT继续迁移。见[合同](../suites/frontend/icache/docs/spec/verification/transactions/metabank-transaction-adaptation.md) |
| `suites/memblock/sbuffer/` | 原排空来源修复、双DUTDriver/Monitor与静态边界已有证据；managed context正文捕获比较错误后的收尾风险仅源码审计，尚无本轮native red/修复，接手先补正反控制 |
| `suites/memblock/{dcache,lsq,lsu,mmu}/` | 已修种子/部分事务子链；剩余pin/signal/owner耦合与完整逐DUT事务审计继续，不由旧完整功能结果替代 |
| `suites/vector/vagq/` | external internal源码/产物边界保持；需独立来源配置，继续32处owner及pin/signal耦合审计，不把internal证据加入公共Git |
| 公共层/最终验收 | 当前目录不重排；后续全仓语义门禁、必要native回归、逐项差分、最终证据和覆盖边界仍必需 |

当前静态债务如下；这是语法审计，不是待修bug精确数量，也不能用零命中签核语义：

| 工程 | pin表达式 | signal操作 | owner/私有helper访问 |
|---|---:|---:|---:|
| BPU | 0 | 0 | 24 |
| FTQ | 0 | 0 | 0 |
| ICache | 0 | 0 | 327 |
| IFU | 0 | 0 | 0 |
| DCache | 2 | 87 | 0 |
| LSQ | 1057 | 1 | 121 |
| LSU | 140 | 0 | 0 |
| MMU | 29 | 382 | 53 |
| Sbuffer | 0 | 0 | 0 |
| VAGQ | 179 | 9 | 32 |

## 交接时必须保持的事实

- 原功能用例、随机激励、FAIL/ERROR/XFAIL/XPASS/SKIP/UNCERTAIN保留；环境selftest不计硬件点。
- 输入UID从驱动前声明建立，不从相同payload、返回值或PC猜来源；采样、消费、响应、
  真正比较交付和控制终态分开。
- `finish()`只等待自主尾部，不补输入、ready、回复、flush或reset清债；正文PASS/吞错/
  缺报告仍严格收尾，正文已报告非PASS只cleanup且保留独立cleanup错误。
- DataBank/MetaBank reset是逐row宏清扫，不是瞬时存储清零；DFT的bypass等输入在
  行为宏不适用，不冒称已验证硅片DFT/timing。
- 历史结果继续归其原源码、日期、基线；不把本文件的阶段结束改写成整体目标完成。

新贡献者按 [协作模板](../CONTRIBUTING.md#给-ai-的任务说明模板)说明负责的DUT及共享文件，
从实际发布commit新建分支；先实现边界内的一条调用链，再提交带证据的增量。
