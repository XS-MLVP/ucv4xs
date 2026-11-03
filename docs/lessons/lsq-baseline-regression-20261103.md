# 基线升级后的 LSQ 回归：区分上游修复、模型滞后与真实缺陷（2026-11-02/03）

## 原问题与范围

用户要求：按 ucv4xs 当前 xiangshan 版本对 LSQ 做回归，使此前 Fail 的用例不再 Fail；
尽量不改测试逻辑（允许调引脚）。

起点是一个容易忽略的陷阱：根 `ucv.json` 默认基线已在 2026-11-02 切到
`public-a0c2a26cb`（`a0c2a26cbe3c862175174bad03a1a23c406315ed`），但当时
**没有生成 RTL、没有构建、没有跑过任何功能回归**。仓库里所有 LSQ 历史判定都属于
`public-893e1580b`。因此第一步不是跑测试，而是按新基线重建。

本页记录结论边界：只覆盖 LSQ 一个工程、seed 1、32 workers、DefaultConfig；不证明
其他九个工程在新基线上同样可跑。

## 建立的执行顺序（与踩过的错误）

1. `ucv prepare lsq --require-unified-baseline` → 整芯片 RTL，收据记录
   baseline=public-a0c2a26cb、2020 个 RTL 文件。
2. 逐个核对 38 个 DUT 闭包的 `source.json` 指向新生成缓存，确认无旧基线混入。
3. `ucv build lsq --require-unified-baseline` → 38/38 `BUILT + SMOKE PASS`。
4. 完整回归 → 新结果目录。

**错误一：先启动完整回归，又在运行期间修改 harness。** v1 运行 53 分钟后被自己
判废——`ucv` 在运行前后比对 `source_identity`，源码在运行中变化的结果不能作为证据。
正确顺序是：先把适配改完并做定向验证，冻结源码，再启动完整回归。作废目录已删除，
不进入任何结论。

**错误二：用 `git checkout -- <model>` 回退"实验性改动"。** 该文件里同时有
**已定向验证但尚未提交**的合同修正，回退把两者一起抹掉，导致重新跑出 8 条假回归。
发现后按 `git diff` 重放两处改动，并用 835 项定向运行确认与已验证结果 **零差异**。
教训：回退实验前先 `git diff` 区分"实验改动"和"已验证未提交改动"，或先临时提交。

## 三类结果的分离方法

同一批 2575 个 nodeid，新旧基线逐项对比后必须分开陈述，不能只报总数：

| 类别 | 数量 | 判据 |
|---|---:|---|
| 上游修复（FAIL→PASS） | 34 | 新基线 Scala 中对应缺陷已消失，且失败断言原样保留 |
| 模型滞后（PASS→FAIL） | 28 | RTL 有意的时序/合同变更，模型编码的是旧延迟 |
| 真实缺陷仍在（FAIL→FAIL） | 216 | 新基线 Scala 中缺陷仍在，逐条对照源码确认 |

上游修掉的三类（可直接引用提交）：
`302c0fe19`（PA 匹配与 VA tag 解耦）、`73cc6ee42`（无真实 enq 不再清 strict）、
`4efe9f034`（Sbuffer credit 前缀出队，替代逐信号相加）。

模型滞后的一类来自 `0a164bbf6`：cross-16B 入场从"FIFO 全空"放宽为
"两个入口 ready"，因此 split 可与 Sbuffer 同一拍完成。参考模型的
`not queue` 编码的是旧延迟。**判别依据不是"改了就过"，而是新 RTL 的
`toSbufferValid` 明确以 `fromDeqModule(0).ready && (1).ready` 为条件**，
模型改为 `capacity >= 2` 是同一语义的公开表述。

## 引脚适配与模型改动要分清

新基线带来三处接口变化，属于允许的引脚层适配：

- `DeqModule` 实际开始消费 `deqCtrlEntries.isCbo` 与 `deqDataEntries.memoryType`
  （`deqUsesSbufferCredit`），Picker 因此多导出 4 个输入（61→65）。
- `ExceptionInfoGen.gpaddr` 从 `GPAddrBits` 扩到 `XLEN`，旧的 50 位截断必须去掉。
- `LoadQueueRAR.matchMask` 改成无复位 `RegEnable`，perf 管线出现 6 拍上电未定义值；
  只延长 perf 的"已知窗口"，之后仍逐拍比较。

未做的一处：`psq/model.py` 尚未把 `memory_type` 接到 `DeqControl`。本轮没有失败
追溯到它，但它是真实缺口，已登记。

## 为什么"照抄 RTL"不是优雅的更新

剩余 3 条只在 post-edge 采样不一致（RTL 计 2、模型计 1，形态是
普通/NC 条目的 lane0 + `vecInactive` 的 lane1）。尝试过四种改法并实测：

| 改法 | 修好 | 引入回归 |
|---|---:|---:|
| 完全复刻 RTL（credit 计数器 + `deqUsesSbufferCredit` 前缀，前后沿同一公式） | 10 | 16 |
| 删除 `after` 分支，改用 post-advance 的 `plan()` | 4 | 21 |
| after：任意 credit 产生即可搭车 | 0 | 19 |
| after：`base in credit_lanes` | 0 | 19 |

纯复刻失败的机制原因：PSQ 的 `handleFinish` 是在 `deq.advance()` **之后**才置位，
比 RTL 的 `wb.fire` 晚一拍；现有 `after` 分支里那句看起来别扭的
`credit_lanes[0] is not None` 正是在补偿这一拍时序差。照抄 RTL 丢掉了补偿。

更根本的判据：**参考模型与 RTL 表达式同构时，只能证明"实现符合该表达式"，
不能证明表达式本身正确**，等于把独立 oracle 退化成语义等价检查。所以"复刻更准"
不是可接受的目标。三种局部改法又都被实测证伪，最终保留 3 条真实 FAIL。

## 结论与残余

- 权威完整结果：`/tmp/opencode/lsq-runs/full-a0c2a26cb-v3`，**2356 PASS / 219 FAIL**
  （旧基线 2325/250），2575 个 nodeid 完全一致，运行前后源码 hash 稳定，
  `manifest committed`、`coverage_complete=true`、`gaps=[]`。
- 219 条里 197 条能对上历史 11 个 RTL 根因，逐条源码确认仍未修复
  （`DEQ-WB-001` 50、`LQU-SID-001` 29、`FWD-RANGE-001` 28、`RAR-REL-001` 19、
  `DEQ-SPLIT-WLINE-001` 15、`DEQ-ZERO-001` 15、`DEQ-FINISH-ORDER-001` 13、
  `FWD-ALIAS-001` 12、`LSQ-BUS-OWNERSHIP-001` 6、`FWD-SQID-001` 3）。
- 3 条 post-edge 残余、`psq/model.py` 的 `memory_type` 缺口未关闭。
- 修这 11 个根因需要改香山 Scala 并进命名基线补丁清单，超出"调引脚"授权范围。

机器记录：[LSQ 新基线回归](../history/lsq-regression-a0c2a26cb-20261102.json)。
