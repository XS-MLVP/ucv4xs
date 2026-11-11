# 全量回归（2026-10-22）：结果、无回归证明与集成残差逐发射点归因

> 一次完整运行，覆盖仓内全部 29907 个用例，未做任何选择裁剪。
> 运行期工作树冻结：`source_epoch_unchanged=true`、`canonical_reports_unchanged=true`，
> 结束后 `--epoch-delta` 为 `frozen=3068 current=3068 changed=0 added=0 removed=0`。

## 一、运行结果

| 指标 | 数值 |
|---|---|
| 精确收集 | **29907** |
| PASS | **29777** |
| FAIL | **123** |
| XFAIL | **7** |
| 全量执行完成 | `full_execution_complete=true` |
| 覆盖率合并完成 | `coverage_complete=true` |
| 功能点 | **353/353 已执行（100%）**：307 PASS、42 FAIL、4 XFAIL |
| 功能组 | 673 组，其中 **566 组 100%** |

`full_regression_complete` 仍为 `false`，这是**设计如此**：该字段要求
`process_exitstatus == 0`，而存在真实 FAIL 时退出码为 1。它不是"没跑完"。
`full_execution_complete=true` 才是"每个收集到的用例都执行过"的判据。

### 与上一轮 BPU 程序集的逐节点比对（无回归证明）

| 项 | 数量 |
|---|---|
| 两轮共有的用例节点 | 1031 |
| **旧 PASS → 新 FAIL（回归）** | **0** |
| 旧 FAIL → 新 PASS（修复/收敛） | 4 |

4 个转 PASS 的都是 `test_conditional_prefix.py::test_atomic_conditional_prefix_ownership`
的 `compressed-entry` 四个 profile。

**关于 88 → 123**：上一轮的"24776 PASS / 88 FAIL / 3 XFAIL"是一次**覆盖范围更窄**的
历史全量（其逐用例报表已被裁剪，无法逐节点比对）。本轮把仓内全部 29907 个用例都跑完，
多出的 FAIL 分布在 `tests/utage`（35）、`tests/mbtb`（10）、`tests/ras`（5）等模块，
属既有真实缺陷；有共有节点可比的部分**没有任何新增失败**。

## 二、覆盖率（全量口径，非选择集）

| DUT | 源码行 | Branch | Toggle |
|---|---|---|---|
| AheadBTB | **17854/17854** | 4811/4876 | 11984/16320 |
| BPU（集成） | **38130/46541** | **9876/13756** | **84305/103292** |
| ITTAGE | **1398/1398** | 655/658 | 12698/18994 |
| MainBTB | 1007/1056 | 385/442 | 7328/11830 |
| RAS | 569/585 | 200/216 | 3382/7720 |
| SC | 3145/3481 | 890/1038 | 10518/15076 |
| TAGE | 4467/4587 | **1533/1598** | **10751/15514** |
| MicroBTB | **794/794** | 188/192 | 3653/8430 |
| MicroRAS | **91/91** | **24/24** | 382/3976 |
| MicroTAGE | 9954/11053 | 3249/3746 | 9152/13376 |
| 合计 | **77409/87440（88.5%）** | | |

集成 BPU 比历史全量（37998/46541）**多命中 132 行**；`useAltOnNa` 的 8 个桶全部命中。

## 三、集成残差逐发射点归因（此前"8543 行无法归因"已闭合）

方法：对全量运行的 `rtl-line-coverage.json` 用
`tools/attribute_integrated_residual.py` 按（文件, 规范化模板）分组，
把下标折叠为 `_N`，于是"同一物理模板的副本"体现为 `count`。

**8411 个未命中行只落在 11 个文件**，并且几乎全部是逐 cell / 逐槽副本：

| 文件 | 未命中行 | 发射点 | 最大单点副本 |
|---|---:|---:|---:|
| `rtl/bpu/AheadBtb.sv` | 4043 | 5 | **929×** |
| `rtl/bpu/BypassShadowBuffer.sv` | 2193 | 5 | **479×** |
| `rtl/bpu/Phr.sv` | 1417 | 84 | **390×** |
| `rtl/bpu/WriteBuffer_38.sv` | 264 | 3 | 128× |
| `rtl/bpu/WriteBuffer_8.sv` | 207 | 13 | 51× |
| `rtl/bpu/AheadBtbReplacer.sv` | 122 | 6 | 56× |
| `rtl/bpu/WriteBuffer_30.sv` | 72 | 3 | 32× |
| `rtl/bpu/WriteBuffer_4.sv` | 72 | 14 | 7× |
| `rtl/bpu/RasStack.sv` | 16 | 1 | 16× |
| `rtl/bpu/CommonHR.sv` | **3** | 3 | 1× |
| `rtl/bpu/MicroRas.sv` | **2** | 2 | 1× |

- 前 9 个文件共 **8406 行（99.94%）**，最大单点都是 7–929 份的逐 cell/逐 set/逐槽
  物理副本（`takenCounter[bank][index][way]`、`usefulEntries[...]`、`phr_N`、
  `states_N`）。
- **唯一的非副本残差只有 5 行**：
  - `CommonHR.sv:869-871` —— `else if (r1_valid)` 的 s1 历史从**已寄存的 r1** 回填；
  - `MicroRas.sv:133-134` —— `s2OverrideData_valid & ~s2_fire & s2_realPush` 同拍时
    返回地址取 override 载荷。
  这两处是**真实缺失情况**（不是物理副本），但合计 5 行 / 8411 行 = 0.06%，
  本报告只登记，不声称已覆盖。

未命中 branch arm 3880 个，分布同样集中在 `AheadBtb.sv`（2433）、
`BypassShadowBuffer.sv`（902）、`AheadBtbReplacer.sv`（129）、`Sc.sv`（111）。

## 四、本轮顺带修复的两个证据缺陷

1. **归因工具只读第一个 DUT**：`attribute()` 用 `next(iter(duts.items()))`，
   在全量报表里会拿到按字母序第一的 `abtb`（0 行未命中），从而报告
   "`files=0 uncovered_lines=0`"，把最大的 DUT 静默跳过。
   已改为**默认选未命中行最多的 DUT**，并新增 `--dut` 显式指定。
   这正是"绿报告可能在空转"的一类假阴性。
2. **`BPU-UTAGE-027` 文档声称已覆盖、代码无标记**：
   `test_write_pressure_bank.py` 的断言已完整覆盖该功能点（压力可达
   `pressured=True`、八条经验逐条读回自己的方向与计数、积压实际下降），
   但只标了 `BPU-UTAGE-001`。已补标记，功能点统计不再把它算作未覆盖。

## 五、约束与保留项

- 未修改 RTL / DUT / SDK；未新增或放宽任何 XFAIL。
- 7 个 XFAIL 仍为严格预期失败，不允许 XPASS 冒充通过。
- 123 个 FAIL 是真实设计问题，原样保留；本轮**没有**为了变绿而放宽任何断言。
- 选择集不再作为证据：本文件所有数字来自这一次全量运行。
- `CommonHR.sv` 3 行、`MicroRas.sv` 2 行是已知未覆盖的真实情况，保留在分母中。
