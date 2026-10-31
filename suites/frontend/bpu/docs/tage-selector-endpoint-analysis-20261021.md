# TAGE `useAltOnNa` 端点：可达性量化与实测覆盖（2026-10-21 起，2026-10-22 全桶闭合）

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


> **最终状态（2026-10-22）**：独立 TAGE DUT 的 8 个桶全部有双端点 + 越界钳位证据，
> `useAltOnNa` 未覆盖 arm 8 → 0（`results/tage-selector-full-20261022-v3`）。
> 下面第一节起的更正过程保留，供后续避免重复踩坑。
>
> **更正（2026-10-21 晚）**：本文原先的结论“端点可构造但代价很高，本轮没有实现”是
> **假阴性**。集成选择器用例 `tests/bpu/testcase/test_tage_selector.py`（`BPU-INT-072`）
> 早已用真实 DUT 到达并保持两个端点，本轮只是补上了“越界那一拍”的显式证据：
>
> | 端点 | 阶段反馈数 | 阶段前 → 后 | 越界事件（模型与 DUT 逐项比较） |
> |---|---:|---|---|
> | 0 | 32 | 15 → 0 | `lower-saturation`：before 0、after 0、`decrements=1` |
> | 31 | 32 | 16 → 31 | `upper-saturation`：before 31、after 31、`increments=1` |
>
> 每个比较帧都把**8 个** `useAltOnNa` 寄存器与独立模型逐项比较；
> 每笔反馈还把 DUT 的 T3 `index/inc/dec` 逐槽比较。选择器索引为
> `2*providerTable + altConf`（本例 index 7 = table 3、altConf 1），即本文原先
> 认为“需要先扩展”的 (table, altConf) 维度在集成参考模型里**已经存在**
> （`suites/frontend/bpu/tage/model/semantic.py`：`self.selectors = [16] * 8`）。`pair.py` 的
> 两项实现不是集成路径使用的模型。
>
> 因此端点不再列为未闭合；`BPU-INT-072` 已加入“越界投票仍产生 inc/dec 而寄存器停在
> 端点”的语义要求与证据，`BPU-TAGE-020` 的 `open_endpoint_note` 已删除并注明端点
> 义务归 `BPU-INT-072`。
>
> 下文保留原始分析（下界推导、每分支最多 ±1、单拍最多 8）作为**成本**说明，
> 但它不再表示“未验证”。

## 一、端点在哪

`rtl/tage/TageDut.v` 中每个 `useAltOnNaVec_*_value` 的更新表达式：

```systemverilog
? (_updatedCtr_T > 6'h1E ? 5'h1F : _updatedCtr_T[4:0])                 // 上钳位到 31
: useAltOnNaVec_0_value <= _GEN ? 5'h0 : useAltOnNaVec_0_value - _GEN  // 下钳位到 0
```

## 二、每次反馈的贡献条件（源码）

`XiangShan/.../tage/Tage.scala`：

```scala
val trainUseAltOnNa = hasProvider && provider.takenCtr.isWeak && providerPred =/= altOrBasePred
val incUseAltOnNa   = trainUseAltOnNa && altOrBasePred === actualTaken   // +1
val decUseAltOnNa   = trainUseAltOnNa && providerPred  === actualTaken   // -1
```

以及按拍聚合：

```scala
val increaseCount = PopCount(increaseMask)   // 最多 = 每拍分支槽位数
val step = Mux(increase, increaseCount - decreaseCount, decreaseCount - increaseCount)
```

`NumBtbResultEntries = NumWay x NumBtbAlignBanks`，生成 DUT 有 **8 个训练槽**
（`io_train_branches_0..7`），所以单拍最大步长是 **8**。

## 三、每个分支最多贡献一次

设某分支 provider 计数为 3（weak），providerPred=0、alternate=1：

| 反馈 | 结果 |
|---|---|
| actual=1（alternate 对） | `inc`，selector +1，provider 3→4 |
| 下一次反馈 | provider=4 仍 weak，但 providerPred=1 已等于 alternate → `trainUseAltOnNa=false`，不再贡献 |

若想让它再次贡献，必须把 provider 拉回 3（或让 alternate 翻向），而拉回 3 需要一次
`dec`，`dec` 同样要求 `providerPred =/= altOrBasePred`——在计数 4 且双方同向时不成立。
**因此在 alternate 方向不变的前提下，每个准备好的分支对同一 selector 桶最多贡献 ±1。**

## 四、到达端点的下界

初始值 `WeakPositive = 16`，5 位饱和计数器上界 31、下界 0：

| 目标 | 需要净变化 | 每拍最多 | 最少贡献分支 |
|---|---:|---:|---:|
| 31（并触发上钳位） | +15，且再来一次 +k 使 `>30` | 8 | **≥ 16**（8 + 7 + 1） |
| 0（并触发下钳位） | −16 | 8 | **≥ 16** |

一个用例要同时覆盖“到 31 并保持”“回 0 并保持”，需要两套方向相反的贡献者：
约 **32~48 个**独立分支，且它们必须落在**同一 (providerTable, altConf) 桶**、
互不冲突的 512 个索引内，每笔都要先完成真实分配、把 provider 计数准备到 weak 态。

这远超现有 `BPU-TAGE-020` 的 2 贡献批量场景（该场景已真实验证“同拍两步”），
但它证明的是普通增减，不是端点。

## 五、为什么原判断不成立

原文列出的三条理由，逐条核对后都不成立：

1. **规模**：并不需要“32~48 个独立分支”。同一 PC 在不同上下文（不同 PHR）下是不同
   的索引，选择器桶只按 `(table, altConf)` 划分，因此 32 笔反馈可以分布在多个上下文，
   每笔各贡献 ±1；`test_tage_selector.py` 用同一 PC、同一位置、32 笔反馈完成两端，
   其中一半是 `agreement-suppressed`（无投票）。
2. **模型维度**：集成路径用的不是 `pair.py`。`suites/frontend/bpu/tage/model/semantic.py` 早已是
   `self.selectors = [16] * 8`、`votes[2 * provider[0] + int(confident)]`，
   即 `(table, altConf)` 八项；本文原文把另一个文件当成了集成模型。
3. **模型反推**：没有发生。端点阶段每笔反馈的 `index/inc/dec` 都是模型先给出，
   再与 DUT 的 T3 投票逐槽比较；选择器寄存器每帧八项全比较。越界事件由模型判为
   `lower/upper-saturation` 后才在用例里断言其存在。

## 六、实测覆盖（不是静默跳过）

| 项目 | 证据 |
|---|---|
| 下端点 | 32 笔反馈：15 → 0；`lower-saturation` 事件 before 0/after 0/`decrements=1` |
| 上端点 | 32 笔反馈：16 → 31；`upper-saturation` 事件 before 31/after 31/`increments=1` |
| 每帧 | 8 个选择器寄存器与独立模型逐项比较 |
| 每笔 | DUT T3 `index/inc/dec` 八个槽逐项比较 |
| 其他桶 | 其余 6 个选择器全程保持 16（`all_other_logical_selector_registers_unchanged`） |

`BPU-INT-072` 的语义要求已补上“越界那一拍仍产生真实 inc/dec，而寄存器停在端点”，
`BPU-TAGE-020` 的 `open_endpoint_note` 已删除，并注明端点义务归 `BPU-INT-072`。
原生分母不扣除。**后续（2026-10-22）已复核**：该条在独立 DUT 全量选测上成立（当时 8 个
未覆盖 arm），随后由 `test_selector_buckets.py` / `_high_bucket` / `_odd_bucket` /
`_even_bucket` 全部补齐，最终 `useAltOnNa` 未覆盖 arm 为 **0**（见第九、十节）。

## 七、教训

- 判断“某维度未建模”前必须确认**实际加载的是哪个模型**，不能拿同目录的近似实现代替；
- 判断“某端点未验证”前必须**读断言**（`checker.check(31, ...)`、`checker.check(0, ...)`），
  不能只读用例名或早先的结论文档；
- 这是本轮第三个由“未读断言/未核对模型”造成的假阴性（前两个是 B×C 位置冲突与
  SC×TAGE 共享列）。


## 八、剩余 7 个选择器桶：当时的构造路径（2026-10-22 已全部实施）

> 本节是 2026-10-21 的中间状态记录，其中“独立 TAGE 没有 selector 公开观测”等说法
> 已被第九节的 monitor 与最终的 8/8 覆盖取代；保留原文是为了说明当时的阻塞判断。

`useAltOnNa` 的索引是 `2*providerTable + altConf`，共 8 个**语义桶**（不是物理副本）。
当时双向端点证据只在 bucket 7（table 3、altConf 1）。当时把其余 7 个的构造路径探明如下：

### 独立 TAGE（`dut/tage/TageDut.v` 的 8 个钳位臂）

实测：单分支冷态误预测 → `TageTraining` 分配 → `predict(base_conf=0)` 得到
**table 0、altConf 0**（= bucket 0）；`base_conf=1` 得到 **table 0、altConf 1**（bucket 1）。
即 bucket 0/1 只需 `base_conf` 区分，无需额外准备。

- bucket 0/1：单 provider + `base_conf∈{0,1}`，可直接构造；
- bucket 2–7：需 `reach_highest_provider` 式升级到 table 1/2/3，同时控制 alternate
  置信度（table≥1 时 `altConf` 由第二匹配的计数决定，而不是 base）。

**阻塞点**：独立 TAGE 目前**没有 selector 的公开观测**（无 `useAltOnNaVec_*` monitor），
且 `suites/frontend/bpu/tage/model/pair.py` 的参考模型只有按 altConf 的两项，不是按
`(table, altConf)` 的八项。要在独立 DUT 上断言端点，需要先补 monitor 与模型维度，
这属于参考模型能力扩展，不能用实际 DUT 值回填。

### 集成 BPU（`rtl/bpu/Tage.sv` 的 7 个钳位臂）

集成路径**已有**八项 selector 模型（`suites/frontend/bpu/tage/model/semantic.py`) 与
`TageSelectorMonitor`（每帧比较八个寄存器），所以只缺“把 table 0/1/2 的 provider
造出来”的程序。本轮尝试直接用
`BpuTraining` + `BpuBatchTraining` 造 table-0 provider，被 MainBTB 位置捕获前提拒绝
（`tage_meta_for_position` 要求该位置有真实 MBTB 主人），说明需要走
`prepare_pair` 那样的 MBTB 计数准备路径，只是把目标表从 3 改成 0/1/2。

结论：这条路径**可行但未实施**，需要“按目标表参数化的 provider 准备 + 32 笔端点反馈”
的专用程序；本轮不伪造，也不把“桶 7 已证”当成 8 个桶都已证。


## 九、独立 TAGE 的桶 0/1 已实测（2026-10-21 收尾）

第八节说“独立 TAGE 没有 selector 公开观测”，本轮已补上：

- `suites/frontend/bpu/tage/monitor/state.py`：`TageSelectorMonitor` 通过 memory-direct 读
  8 个 `useAltOnNaVec_N_value`；
- `suites/frontend/bpu/tage/agent/main.py`：`sample_selectors()` 为**纯 pull** 采样（无后台订阅）。

新增 `tests/tage/testcase/test_selector_buckets.py` 用闭式算术逐步预测投票并对 8 个
寄存器逐项比较，覆盖 bucket 0（table 0/altConf 0）与 bucket 1（table 0/altConf 1）：

| 桶 | 锚定 | 上端 | 上行程投票 | 下端 | 下行程投票 | 钳位 |
|---|---:|---:|---:|---:|---:|---|
| 0 | 16 | 31 | 15 | 0 | 31 | 两端均保持 |
| 1 | 16 | 31 | 15 | 0 | 31 | 两端均保持 |

全量 TAGE 选测 `results/tage-selector-full-20261022-v3`：**234 PASS / 1 XFAIL**，
branch **1513 → 1533（+20）**、toggle **+40**，行不变，FAIL/XFAIL 集合与基线完全相同；
`useAltOnNa` 的未覆盖 arm **8 → 0**，8 个桶全部有双端点与越界钳位证据。

**追加：bucket 2 也已实测**（`tests/tage/testcase/test_selector_high_bucket.py`）。高表桶需要
强替代项，构造路径：把 table 0 的桶投到 10（`useProvider=1` 冻结该表项）→ 计数推到 7 →
一次真实误预测升级到 table 1，冻结项成为强替代（`altConfig=0`）。

| 方向 | 锚定 | 最终 | 投票 | 越界钳位 |
|---|---|---:|---:|---|
| 上行 | 16 | 31 | 15 | 再投 1 票仍 31 |
| 下行 | 16 | 0 | 16 | 再投 1 票仍 0 |

两个方向各用一次全新 reset、同一 shift 复现同一张表；投票全部落在同一寄存器（索引 2），
其余保持 16。未覆盖 `useAltOnNa` arm 由 8 个降到 5 个（index 3–7）。

**桶 2–7 的阻塞点（当时的判断，2026-10-22 已推翻）**：独立 TAGE 的公开输入只有单一
provider 表，探针在 table 1 的 10 个驱动拍上观察到 `moved=[]`，即
`altOrBasePred` 恒等于 `provider_pred`，于是当时判断“只有 table 0 能让
‘弱 provider 且两个预测相反’成立”。这个判断漏掉了两种同样有效的形态（饱和负向替代项、
直接分配到高表且无替代项），见第十节的最终结果。

### 最终结果（2026-10-22）：8/8 桶全部双端点

| 桶 | 形态 | 上端 | 下端 | 越界钳位 | 用例 |
|---|---|---:|---:|---|---|
| 0 | 无 provider，`base_conf=0` | 31 | 0 | 两端保持 | `test_selector_buckets.py` |
| 1 | 无 provider，`base_conf=1` | 31 | 0 | 两端保持 | `test_selector_buckets.py` |
| 2 | 冻结强替代项（计数 7） | 31 | 0 | 上下各再投 1 票保持 | `test_selector_high_bucket.py` |
| 3 | 饱和负向替代项（计数 0） | 31 | 0 | 上下各再投 1 票保持 | `test_selector_odd_bucket.py` |
| 4 | 直接分配 table 2，无替代项 | 31 | 0 | 上下各再投 1 票保持 | `test_selector_even_bucket.py` |
| 5 | 饱和负向替代项（计数 0） | 31 | 0 | 上下各再投 1 票保持 | `test_selector_odd_bucket.py` |
| 6 | 直接分配 table 3，无替代项 | 31 | 0 | 上下各再投 1 票保持 | `test_selector_even_bucket.py` |
| 7 | 饱和负向替代项（计数 0） | 31 | 0 | 上下各再投 1 票保持 | `test_selector_odd_bucket.py` |

全量证据 `results/tage-selector-full-20261022-v3`（234 PASS/1 XFAIL，`changed=0`）：
branch 1513 → **1533**、toggle 10711 → **10751**，`useAltOnNa` 未覆盖 arm **8 → 0**。


## 十、桶 2–7 的机制探针（2026-10-22：全部已交付，本节保留为纠错记录）

在第九节之外，本轮还专门探过“给 provider 配一个强替代项”的路径，结论有进展但
**没有达到可交付的稳定用例**，如实记录以免后续重复踩坑：

| 步骤 | 结果 |
|---|---|
| 把 table 0 的选择器桶先降到 10（`useProvider=1`） | 成功，且此后该表项被**冻结**（不再被替代训练） |
| 冻结后把 table 0 计数推到 7 | 成功 |
| 用一次真实误预测升级到 table 1–3 | 成功，但**落到哪张表由 LFSR 决定**（不同轮次分别落到 table 2 与 table 3） |
| 升级后替代项计数 | 有时 ≥5（`altConf=0`，桶 2/4/6），有时为 3/4（`altConf=1`，桶 3/5/7） |
| `altConf=1` 的稳定性 | **不稳定**：下一次训练拍会把替代项从 4 减到 3，桶立刻从 3 翻到 2（探针实测 `assert (2*1+0)==3` 失败） |
| `altConf=0` 的稳定性 | 可以连续驱动：探针把桶 4 从 15 一路降到 5，`altPred` 始终保持 1 |
| 但要把 `altConf=1` 变成 `altConf=0` | **不可能**：此时 `useProvider=1`（替代项被冻结），无法再训练替代项把计数推回 ≥5 |
| 桶 2 的完整端点 | **已解决**：用有界 shift 搜索找“替代项足够强”的布局（shift=2 时 table 1、altConf=0），并在两个方向各用一次全新 reset。`test_selector_high_bucket.py` 上线：上行 16→31（15 票 + 1 票越界）、下行 16→0（16 票 + 1 票越界），票全部落在寄存器 2，其余保持 16 |

**机制结论（已更正）**：投票条件 `weak && provider_pred != alt_pred` 与“冻结替代项”
(`useProvider=1`) 确实互相牵制，但那不是唯一出路。真正稳定的是另外两种形态：

- **饱和负向替代项（计数 0）**：计数 0 在继续 not-taken 训练下保持 0，
  `altConf=1`、`altPred=0` 恒定，provider 在 3/4 往返时两个方向都有票
  → 覆盖桶 3、5、7。
- **直接分配到 table 2/3 且无替代项**：`altConf` 取自 base 计数，而 base 由调用方
  每拍重给 `base_conf=0`、不参与训练，所以 `altConf=0`、`altOrBasePred=0` 恒定，
  provider 在 4 时 `providerPred=1 != 0` → 覆盖桶 4、6。

本节早期“bucket 4/6 需要替代项在投票后仍 ≥5”的结论**是错的**，原因是当时假设
altConf 只能来自替代项。改用无替代项形态后，桶 4/6 一次就到达双端点。
`test_selector_even_bucket.py` 里对 `altOrBasePred == 0` 的断言就是防止这个假设回退。

因此 `BPU-TAGE-020` 的端点证据保持 **bucket 0、1（独立 DUT）+ bucket 7（集成）**，
不把探针里的中间观察当作覆盖。
