# NewStoreUnit 族三个叶子 UT 报告（2026-10-25）

本报告覆盖 `p1-store-leaves` 阶段的三个 DUT：`Arbiter3_StoreStageIO`、
`MemTrigger_3`、`DelayPipeline`。三者都是 `StoreUnitS0/S1/S3` 的真实子块，
各自独立 Picker 构建、独立结果目录、独立覆盖率分母。

## 1. 结果汇总

| DUT | 用例 | 功能覆盖 | 行（DUT-only） | 分支 | Toggle（DUT-only） | 状态 |
|---|---:|---:|---:|---:|---:|---|
| `Arbiter3_StoreStageIO` | 22 PASS | 100% | 32/32 = 100% | 62/62 = 100% | 1126/1128 = 99.82% | PASS（2 点结构性不可达） |
| `MemTrigger_3` | 32 PASS | 100%（32/32 情形） | 48/48 = 100% | 16/16 = 100% | 762/762 = 100% | PASS |
| `DelayPipeline` | 14 PASS | 100%（18/18 情形） | 29/29 = 100% | 5/6 | 978/978 = 100% | PASS（1 点工具边界） |

全部 68 个用例普通 PASS，**0 FAIL、0 xfail、0 skip**。所有行/toggle/branch
分母按 DUT 独立保留，未跨 DUT 合并。

## 2. 各 DUT 的语义与关键发现

### 2.1 `Arbiter3_StoreStageIO`

合同：[store-arbiter.md](../contracts/store-arbiter.md)
证据：`store-arbiter-initial-03`

两处必须按生成 RTL 而不是 Scala 意图描述的边界：

1. **prefetch 源整源消除**：生成的 `StoreUnitS0` 没有 `io_prefetchReq` 端口，
   因此第三个仲裁源的 valid 被常量折叠为 0、`io_in_2_*` 整组端口消失，只剩
   bubble 输出里的常量（`entrance=0x2`、`instrType=4`、`size=4`、`mask=0xFFFF`）。
2. **unalign tail 无 ready**：`io_in_0` 只有 `valid`/`bits`，S1 回注的尾段
   不能被反压，`in_1.ready = ~in_0_valid`。

参考模型是独立的两路优先级选择器 + 显式 bubble 常量表；每个 beat 逐字段比较
22 个输出字段。唯一未覆盖的 toggle 是 `entrance[2]`（只有 `vectorIssue=0x4`
会置位，而本模块没有任何输入能选择它），已按结构性不可达归档。

### 2.2 `MemTrigger_3`

合同：[store-trigger.md](../contracts/store-trigger.md)
证据：`store-trigger-initial-02`

三种地址匹配模式按优先级 `isCbo → isVectorUnitStride → matchType`；四路
trigger 各自带 `!select && !debugMode && tEnable && store` 前置门控；chain 规则
要求前一路命中且 timing 相同；输出优先级 DebugMode > BreakpointExp（后者还需
`triggerCanRaiseBpExp`）。

**合同修正 1（真实端口宽度）**：`matchType` 在本接口只有 **2 bit**，
`TrigMatchEnum` 的 4 bit 编码被截断。因此可达编码只有 EQ(0)/NAPOT(1)/GE(2)/LT(3)，
NAPOT 是唯一"实现了名字但未实现行为"的编码（`Trigger.scala:171-188` 的
`isLegal` 只接受 EQ/GE/LT）。原计划的 "reserved encoding" 情形无法在本端口表达，
已从情形清单删除，而不是用越界值强行造一个 bin。

**覆盖闭环**：首轮 30 例时 toggle 为 650/762，缺口全部是 4×`tdata2[63:50]`
的高位（56 bit × 2 方向 = 112 点）。补 `test_tdata2_full_64bit_width_is_exercised`
（64 bit walking-one × 4 路，标量与 CBO 两种模式各一遍）与
`test_vaddr_and_mask_full_width_are_exercised` 后达到 762/762。

### 2.3 `DelayPipeline`

合同：[store-delay.md](../contracts/store-delay.md)
证据：`store-delay-final-01`

固定配置 `RAWTotalDelayCycles=1`，生成 RTL 只有一级寄存器。

**合同修正 2（不可观测路径）**：源码里除了"入口 beat 被本拍 redirect 命中就不
进寄存器"，还有一处针对**寄存器 beat** 的 `curKill`。但 `out.ready` 在父块被接成
`true.B`，firtool 把它常量传播掉（生成 DUT **没有 ready 端口**），因此 beat 只
在出现的那一拍被消费、不会驻留，`curKill` 在本边界上**不可观测**。

验证方式不是"假设它没用"，而是差分实验：同一条 40 拍输入流，把同一拍 redirect
指向寄存器里的 beat 与不指向它，两次输出逐字段完全相同
（`test_registered_beat_kill_is_not_observable`）。合同第 2 节据此改为只声明入口
过滤，并把出口路径记为结构性不可观测。

唯一未覆盖分支是 `DelayPipeline.sv:204` 的 `initial` 块内 `if (reset)`：Picker 的
`InitClock` 在测试能拉高 reset 之前就执行了 initial，属于工具边界；reset 的边界
行为仍由 `delay.reset_clears_valid` 在公开端口上验证。

## 3. 覆盖闭环过程（三个 DUT）

| DUT | 首轮 | 缺口分析 | 补例/修合同 | 终轮 |
|---|---|---|---|---|
| store_arbiter | 22 PASS，功能 coverage 88.72% | cross 里混入了由同一仲裁决定派生的维度（8 个 bin 逻辑不可能）；`unknown` 防御分支被当必需 bin；walking-one 生成器多置位 | 重设计为 4 个 `beat_kind`；删除 `unknown`；`shape` 收敛为 zero/all_ones/mixed；修 walking-one | 22 PASS / 100% / 32 行 / 62 分支 / toggle 99.82% |
| store_trigger | 30 PASS，toggle 650/762 | `tdata2[63:50]` 高位从未翻转；`matchType` 宽度理解错误导致一个不可能 bin | 补 64 bit × 4 路 walking-one、50 bit vaddr、16 bit mask 扫描；删除不存在的 reserved 编码情形 | 32 PASS / 100% / 48 行 / 16 分支 / 762 toggle |
| store_delay | 14 FAIL（首轮模型/采样约定错误） | 采样相位与原模型不一致；把"寄存器 beat 的 kill"当成可观测功能点 | 改为"采样当前拍、再施加本拍输入"的约定；模型改为 `valid_next=prevFire`；补差分实验 | 14 PASS / 100% / 29 行 / 5-6 分支 / 978 toggle |

`store-arbiter-initial-01/02`、`store-trigger-initial-01`、
`store-delay-initial-01/02` 全部保留，不追溯改写。`store-delay` 首轮的 14 个
FAIL 是**验证侧模型与采样约定错误**，不是 RTL 缺陷，已在该 DUT 的 gap 文件中
如实记录。

## 4. 证据入口

| 内容 | 路径 |
|---|---|
| 构建报告 | `results/builds/20261025T042333369715Z-store_arbiter/`、`...T043402933876Z-store_trigger/`、`...T043844886649Z-store_delay/` |
| 终轮运行 | `results/store-arbiter-initial-03/`、`results/store-trigger-initial-02/`、`results/store-delay-final-01/` |
| 覆盖率审计 | 各运行目录下 `coverage-audit.json` / `coverage-audit.md` |
| 功能覆盖 | 各运行目录下 `functional-coverage.json` |
| 缺口分类 | `docs/gaps/store-arbiter.json`、`store-trigger.json`、`store-delay.json` |
| 合同 | `docs/contracts/store-arbiter.md`、`store-trigger.md`、`store-delay.md` |
| RTL 哈希 | `manifest/lsu-rtl.sha256` |

## 5. 边界声明

- 三个叶子通过**不**代表 `StoreUnitS0/S1/S3` 或 `NewStoreUnit` 通过。
- 叶子 UT 的触发/被匹配对象来自测试环境，不是真实 IQ/CSR 行为。
- 未覆盖点没有删除分母：`store_arbiter` 2 个 toggle 点、`store_delay` 1 个
  分支点按上文的不可达/工具边界保留在原分母内。
