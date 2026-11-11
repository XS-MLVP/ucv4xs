# BPU 功能点辅助索引（public-a0c2a26cb / DefaultConfig）

**设计先读[模块行为目录](../../design/module-behavior-matrix.md)，而不是从本页点数开始。**
本页解释既有功能 ID、责任 DUT 和测试层级，以便定位代码和合同。工程根的
`verification_plan.json` 已删除；当前要求从模块规格、功能点文档和验证合同查阅。
行为目录由需求、producer/consumer 和合同建立，再反查旧 ID；不能将“ID 全部已分组”
作为功能行为清单穷尽的证明。场景的前态、独立答案、禁止副作用和完成义务另见
[覆盖设计](../coverage/behavior-coverage-design.json)保存33行为族的有界代表分区和关键交互；
[场景证据记录](behavior-scenarios.json)仍仅3条示例，不将设计入口或旧PASS冒充新场景闭环。

## 四种不同对象

| 对象 | 用途 | 不可混用的结论 |
|---|---|---|
| 功能点 ID | 既有合同/绑定/残余的追溯；保留原 nodeid | 一个 ID 可能跨多个行为和场景，不是一个独立 bin |
| 模块行为族 | 说明模块应该做什么；稳定 `behavior_id` 不随中文名称改变 | 旧 ID 全部关联不代表目录无遗漏或该族整体 PASS |
| 场景等价类 | 指定合法输入/历史、结果和区分性检查 | 同族其它场景、其它结果域和时序交叉不能继承其通过 |
| 参数实例 | 场景的具体数据和坐标 | 参数不同但输入/后果相同，不重复增加语义类；例如 cold NT 的旧 target region 并不存在 |

## 责任域

删除旧计划前，本索引记录 **371 点**：**361 个硬件功能点**，以及 **10 个验证环境合同点**。
下表保留该分类快照，不代表当前运行器注册数量或新一轮执行结果。
硬件点按唯一责任 DUT 分类，不把一个顶层 Bpu 点的所有子模块自动各算一次：

| 责任 DUT | 索引点数 | 本层主要责任 |
|---|---:|---|
| Bpu / INT | 114 | 预测选择、历史、恢复和跨预测器集成 |
| AheadBtb / ABTB | 54 | ahead 目标预测和学习 |
| Tage | 36 | 长历史条件方向、分配及维护 |
| MainBtb / MBTB | 34 | 分支目标/方向与 Main/VBTB 原件归属 |
| MicroTage / UTAGE | 28 | 前级条件方向和保护 |
| Sc | 23 | 统计修正、资格、权重与阈值 |
| Ittage | 20 | 间接目标、置信度与来源 |
| Ras | 18 | 主返回栈恢复与提交 |
| MicroBtb / UBTB | 17 | 前级目标/方向预测 |
| MicroRas / URAS | 17 | 前级返回栈、转发及取消 |

环境合同另列：Driver 4、Binding 2、Monitor 2、Scoreboard 2；环境点数和自检通过不增加
硬件功能的已验证范围。旧结果保存在原报告，不在这里复写成当前状态。

## 测试层级（逐点唯一）

下表沿用原分类的 domain（硬件/环境）与 level（测试层级）口径；它表示验证角度，
不等于用例已通过或该行为完整覆盖。当前场景须按合同、合法前态和实际检查确认归属。
当前运行中的功能标记统计采用 `scope=collected-test-markers`，仅来自实际收集标签；
下表的历史分类点数不作为新报告的完整计划分母。

| 层级 | 点数 | 分组含义与示例 |
|---|---:|---|
| functional | 154 | 单 DUT 功能与局部组合；例如 `BPU-MBTB-033` 的 NT 类型纠正 |
| integration | 87 | Bpu 多预测器、FTQ 反馈及历史组合；例如 `BPU-INT-034` 的原检查点恢复 |
| pipeline | 62 | 在途读写、反馈与版本服务；例如 `BPU-MBTB-025` 的保留记录 owner |
| stress | 30 | 容量、替换、饱和及压力边界；例如 `BPU-ABTB-015` 的持续冲突 |
| boundary | 19 | 地址/位宽、跨区及守护边界；例如 `BPU-INT-114` 的 guard/sign 组合 |
| contract | 15 | 其中 10 点为环境合同，其余 5 点为硬件接口/关联约束 |
| state | 3 | TAGE/SC 的真实来源状态、维护与归属 |
| qualification | 1 | 学习资格能否由合法原件建立；`BPU-TAGE-032` |

## 证据边界

- **原完整结果**：`results/bpu-a0c2a26cb-full-seed1-v2-20261103/`，源码
  `18a8e5d2…`，只覆盖当时的 358 个硬件点。版本、判定、残余及证据索引保持在
  [基线交付报告](../evidence/runs/baseline-update-a0c2a26cb.md)，不给后来新增点套用状态。
- **原矩阵定向结果**：`results/bpu-io-matrix-seed{1,2}-v4-20261103/`，源码
  `f22dc87a…`；真实选择、逐nodeid及65个语义类的记录见
  [矩阵交付报告](../coverage/io-matrix-extension-20261103.md)和
  [机器索引](../../../../../../../docs/history/bpu-io-matrix-extension-20261103.json)，不是361点完整重跑。
- **未关闭范围**：旧 FAIL/ERROR/未查根因、公开 target/perfMeta、完整 FTQ/IFU 可达性及
  输入/结果域矩阵的 21 个 gap 仍在；“有测试绑定”不能代表行为等价类已全面 checked。
  `BPU-INT-034/066/077` 在定向子集为 PASS，却在旧完整回归为 FAIL；两者选取的
  节点范围不同，**不得将该三点归为当前整体 PASS**。其他旧点也不以本轮子集代替全量。

单点按 ID 从[模块行为目录](../../design/module-behavior-matrix.md)、对应 DUT 规格与
[验证合同](../contracts)核对责任域、层级和行为切面；既有[功能点清单](functional-points.md)
中的阶段记录保持原基线含义。状态只能引用**同一轮**实际用例和报告；历史
`feature-points.json` 的 `status/tests` 也仅属于该轮测量。
不能将 `results/bpu-a0c2a26cb-full-seed1-v2-20261103/feature-points-aggregate.json`
与本轮 seed1/2 的 PASS 拼成一份新的“全量 361 点”报告。
