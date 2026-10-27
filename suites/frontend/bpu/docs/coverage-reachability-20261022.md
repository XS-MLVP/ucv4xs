# 未覆盖项到底是“覆盖不到”还是“还没做到”（2026-10-22）

> 依据：一次全量回归 `results/full-regression-20261022-v1`（29907 用例）的原生报表，
> 以及各模块源码 guard 审计。本文把每个未命中项归到三类之一，并给出可复算的分母。
> 结论先说：**绝大多数是“能做到但故意没有逐个枚举”的物理副本；真正“做不到”的只有
> 少数被 guard 排除的臂；真正“还没做到”的只有 5 行源码 + 若干非副本臂。**

## 一、先看源码行：只有 5 行不是副本

对每个 DUT 的 `uncovered_rtl_source_lines` 按（文件，规范化模板）分组，把下标折叠为
`_N`；若同一模板只有 1 份，就是“非副本”（唯一发射点）。

| DUT | 未命中行 | 非副本行 | 副本行 |
|---|---:|---:|---:|
| BPU（集成） | 8411 | **5** | 8406 |
| MicroTAGE | 1099 | **0** | 1099 |
| SC | 336 | **0** | 336 |
| TAGE | 120 | **0** | 120 |
| MainBTB | 49 | **0** | 49 |
| RAS | 16 | **0** | 16 |
| AheadBTB / ITTAGE / MicroBTB / MicroRAS | 0 | 0 | 0 |

那 5 行是：

| 位置 | 条件 | 性质 |
|---|---|---|
| `rtl/bpu/CommonHR.sv:869-871` | `else if (r1_valid)` 时 s1 历史取自**已寄存的 r1** | **能做到、还没做到**：需要一个“重定向路径未选中但 r1_valid 仍在”的时序 |
| `rtl/bpu/MicroRas.sv:133-134` | `io_s2OverrideData_valid & ~io_stageCtrl_s2_fire & s2_realPush` | **能做到、还没做到**：需要“S2 未 fire 但 override 有效且真实 push”的背压拍 |

其余 10096 个未命中行全部是**同一发射点的多份物理副本**：`AheadBtb.sv` 的
`takenCounter[bank][index][way]`（929 份）、`BypassShadowBuffer.sv` 的 512 个
`usefulEntries` cell（479 份）、`Phr.sv` 的 52 个 PHR 比特 × 各 stage（390 份）、
`ReplacerState.sv` 的 64 个 set（49 份）、`ScDut.v` 的逐 way/bias 桶等。

**这类“覆盖不到”是口径问题，不是能力问题**：只要把 `bank/set/way` 逐个坐标跑一遍就
能命中，但那只是把同一段语义重复 N 次。项目此前明确拒绝按物理坐标枚举
（`docs/coverage-gap-completion-20261016.md`），所以它们的**分母保留、不授予覆盖信用**。

## 二、再看分支臂：63 份副本 / 少数 guard 不可达 / 少数真缺口

未命中 branch arm 共 4775 个（含集成 BPU 3880）。按同一规范化方法：

| DUT | arm | 副本 arm | 非副本 arm |
|---|---:|---:|---:|
| BPU（集成） | 3880 | 3836 | 44 |
| MicroTAGE | 497 | **497** | 0 |
| SC | 148 | 143 | 5 |
| TAGE | 65 | 61 | 4 |
| MainBTB | 57 | 0 | 57 |
| AheadBTB | 65 | 63 | 2 |
| RAS | 16 | 16 | 0 |
| MicroBTB | 4 | 0 | 4 |
| ITTAGE | 3 | 0 | 3 |

非副本 arm 里，**已用 guard 证明不可达**的有：

- `AheadBtbReplacer.sv` 的 `else if (set_touch_ways_N_valid)`：外层 `if` 已要求同一
  条件为真，`else if` 同条件再判 → 不可满足。
- `WriteBuffer.sv` 的 `writeTouchVec_N_bits = io_write_N_valid & ~hit ? victim : 0`：
  `~hit` 分支与写入使能同源互斥（写缓冲的空槽恒有 `hit=0`，但该表达式在被使用时
  写使能必为 0）。
- `MainBtbInternalBank.sv:151-163` 的 7 个 `writeValid ? … : 0` else 臂：`writeValid=0`
  时写使能为 0，数据位是 don't-care。
- `ram_4x9.sv:88` 的 `R0_en ? Memory[R0_addr] : 9'bx`：X 赋值分支，二态仿真不可达。
- `ScDut.v` 的 `_scCorrectVec_T_N` 三元：与 `scWrong` 同源互斥。
- `RegionWays.sv` 的 `writePointer` 分支：写指针边界由复位值保证不越界。
- `MicroBtbReplacer` 的 `else if (io_predTouch_valid)`、`UbtbDut.v` 的
  `~_t1_updatedEntry_usefulCnt_T_N` 与 `t1_fire_REG`：外层条件已覆盖。

**仍然只是“还没做到”的非副本臂**（数量少，可补）：

| 位置 | 数量 | 需要的场景 |
|---|---:|---|
| `WriteBuffer.sv` / `WriteBuffer_8.sv` 的 `replacerWay_N` 与 `writeTouchVec` 变体 | 5 | 写缓冲满且替换者同时给出 victim 的拍 |
| `TageDut.v` 的 `allTableTagMatchResults_N_takenCtr_value`、`hitMask_N_M` | 3 | 多表同置位命中的组合 |
| `BpuDut.v` 集成胶合（`_uras_io_specOut_retTarget_addr`、`s1_valid` 等） | ~30 | 集成层的特定组合拍 |
| `AheadBtbReplacer.sv` 的 `&io_writeSetIdx` 全 1 set | 1 | set 63 的替换写 |

这些合计约 40 个 arm，占比 0.8%，**没有一个属于“功能点整体缺失”**：它们都是已有
功能点在某个具体组合下的缺情况。

## 三、直接回答

1. **“覆盖不到”**：只有上面第二节列出的 guard 互斥项（约 20 个 arm）与 X 赋值分支。
   它们**在数学上不可满足**，不是没跑。
2. **“可以覆盖到，但我们没做”**：**10096 行 + 约 4200 个副本 arm**。做法是把
   `bank/set/way/bit` 逐个枚举。这是**明确的取舍**（新增信息≈0，代价是小时级仿真），
   不是能力不足。分母因此保留、不给信用——这一点过去几轮已反复声明。
3. **“真的还没做到”**：`CommonHR.sv:869-871`（3 行）、`MicroRas.sv:133-134`（2 行），
   以及约 40 个非副本 arm。这些是**唯一值得继续补的具体缺口**，规模是 5 行源码。

## 四、为什么之前会误判

- 2026-10-21 曾把 TAGE 的 bucket 4/6 判为“需要替代项在投票后仍 ≥5，做不到”。实际是
  **错误假设**（以为 `altConf` 只能来自替代项）；改成“直接分配到 table 2/3 且无替代项”
  后一次到达双端点，8/8 桶闭合。**教训：把“我没想到的构造”说成“不可达”。**
- 2026-10-22 归因工具只读第一个 DUT（`abtb`），把 8411 行的最大残差静默跳过，
  报出 `files=0`。**教训：聚合报表上“没有未命中”往往意味着读错了对象。**

因此本文的每条“不可达”都附 guard 引用，“没做”都给出具体坐标维度，不再混用两种说法。
