# BPU 覆盖率未命中项逐项归因（2026-10-21）

> 目的：把每个模块的未命中行/分支归到「已有功能点缺情况」「整体功能点缺失」
> 「结构不可达」「工具/物理副本」四类之一，并给出可复核的文件与证据。
> 完整回归边界仍为 **24776 PASS / 88 FAIL / 3 XFAIL**；本文不改变任何分母。

## 一、按模块的覆盖与未命中归因

| 模块 | 选测运行 | 用例 | 源码行 | Branch | Toggle | 未命中归因 |
|---|---|---|---:|---|---|---|
| ITTAGE | `ittage-late-source-qualification-20261020-v2` | 33P/4F | **1398/1398** | 655/658 | 12698/18994 | 3 个 arm：①`RegionWays.sv:586` 备用端口旁路需 provider 未定且同拍分配，合法序列不可兼得（守卫不可达）；②`WriteBuffer.sv:436`/`WriteBuffer_4.sv:436` 父 guard 排除（父 `if` 已要求 `writeValid`）。源级审计见该运行的 `uncovered_triage`。 |
| RAS | `ras-module-qualification-20261020-v4` | 20P/5F/1X | 569/585 | 200/216 | 3382/7720 | 16 键全部在 `RasStack.sv:507–570` 的 `commitStack_N_ctr`：8 个递减副本位于 increment 优先分支的 `else if`（同条件需既真又假），另 8 个副本在外层 push 内又要求 pop；父 `Ras.sv` 由同一已注册 `rasAction` 产生 `==2`/`==1`，两态互斥。源绑定 guard 审计覆盖 16/16。 |
| MicroRAS | `uras-module-qualification-20261020-v3` | 23P/4F | **91/91** | **24/24** | 382/3976 | 源码行与 branch 均满；toggle 低是因为 24 个选择端在短程序里未翻转（非功能缺口）。 |
| MicroBTB | `ubtb-module-qualification-20261020-v2` | 40P/2F | **794/794** | 188/192 | 3653/8430 | 4 个 arm：①`UbtbDut.v:770` 的 `getDecrease()` 保持臂与 ②`:1790` 的隐式 else 臂：外层 `otherwise` 已由 `initEntryIfNotUseful` 保证 `useful != 0`（`MicroBtb.scala:199–212`），`isSaturateNegative` 即 `useful==0`，二者矛盾 → 结构不可达；③`:1785`、④`MicroBtbReplacer.sv:283` 的 `else` 臂：同块的 else 体赋值（`UbtbDut.v:1800ff`）与 `:284` 的 predTouch 更新均为**已覆盖源码行**，且该模块未命中源码行数为 0，属分支归属边界，不是缺功能情况。 |
| MainBTB | `mbtb-module-qualification-20261020-v2` | 110P/10F | 1007/1056 | 385/442 | 7328/11830 | 49 行全部是 `ReplacerState.sv` 的 `states_N <= io_write_1_bits_state`（set 9–60）：同一 64 set PLRU 写模板的逐 set 物理副本，端口 0/1 的语义在已命中的 set 上验证；逐 set 扫是 `docs/coverage-gap-completion-20261016.md` 明确拒绝的物理枚举。57 arm 中 49 同在 `ReplacerState`，7 在 `MainBtbInternalBank`（按 entry 副本），1 在 `ram_2x12`。 |
| TAGE | `tage-selector-full-20261022-v3` | 234P/1X | 4467/4587 | **1533/1598** | **10751/15514** | 120 行分类 120/120、64 producers：同一赋值在多处发射 + 逐 cell 副本。85 个 branch arm 实际分布：`WriteBuffer.sv` 50（槽位 hit/row 副本）、`TageDut.v` 34（含 **8 个 `useAltOnNa` 钳位桶**、9 个 hitMask、5 个 tag-match）、`ram_4x9.sv` 1。**selector 桶已全桶闭合**：独立 DUT 覆盖 bucket 0–7（`test_selector_buckets.py` 0/1、`test_selector_high_bucket.py` 2、`test_selector_odd_bucket.py` 3/5/7、`test_selector_even_bucket.py` 4/6），每桶都到 0 与 31 两端、越界再投 1 票仍停端点、票全部落在同一寄存器；bucket 7 另由集成 `BPU-INT-072` 端到端印证。**未覆盖的 `useAltOnNa` arm 8 → 0**；`TageDut.v` 的未覆盖 arm 由 34 个减到 **14 个**（9 个 hitMask、5 个 tag-match 等逐副本），全模块未覆盖 arm 65 个（`WriteBuffer.sv` 50、`TageDut.v` 14、`ram_4x9.sv` 1） |
| SC | `sc-module-qualification-20261020-v2` | 51P | 3145/3481 | 890/1038 | 10518/15076 | 336 行全部在 `WriteBuffer.sv`/`WriteBuffer_8.sv` 的两个死发射点，guard 分类 336/336、16 producers（同一赋值重复发射）。148 个 branch arm：`ScDut` 128（bias 4、MBTB 选择 17、阈值端点 8 结构不可达、path 6、bias 29、槽→way 46、global 18 均为逐副本）、`WriteBuffer` 20（全脏 victim 2 = 已判定当前形状不可达；死三元 2；死 guard 头 16）。 |
| MicroTAGE | `utage-slot2-upper-20261021-v1` | 218P/35F/3X | 9954/11053 | 3249/3746 | 9152/13376 | 1099 行模板审计 1099/1099（367 奖励 + 366 惩罚 + 366 `else if` 头，`BypassShadowBuffer` 低表逐 cell 副本）；497 个 branch arm 全在该文件的逐 cell aging else 臂；`UtageDut.v:1100–1200` 的恢复选表臂本轮已**全部命中**（1133 归零）。 |
| AheadBTB | `abtb-final-20261021-v4` | 75P/1F | **17854/17854** | 4811/4876 | 11984/16320 | 65 个 arm：64 个为每 set PLRU 链尾（`victim` 守卫并集使 fall-through 不可满足），1 个 `WriteBuffer` 三元 else；7 项负对照拒绝放松守卫。行已满。 |

## 二、集成 BPU 的未命中

完整回归为 **37998/46541**（8543 行未命中）。该运行的逐文件报表在历史归档中已被
裁剪，因此**不能**为完整回归给出逐文件的精确计数。作为替代，本轮用
`tools/attribute_integrated_residual.py` 对最近一次收敛的集成选测
（`results/bpu-final-20261021-v3`，23 个硬件用例）做**逐发射点归因**：它把每个
未命中行按（文件, 规范化模板）分组，模板中的下标被折叠为 `_N`，于是同一物理模板的
副本会在 `count` 上体现。

该选测 35 个文件共 **17972** 行未命中、**7625** 个未命中 branch arm。
最大 14 个文件：

| 文件 | 未命中行 | 发射点 | 最大单点副本数 | 最大发射点（规范化） |
|---|---:|---:|---:|---|
| `rtl/bpu/AheadBtb.sv` | 5084 | 6 | 1022× | `if (\|takenCounter_N_N_N_value) // /home/xyl/bpu-verify-kunmingh` |
| `rtl/bpu/BypassShadowBuffer.sv` | 3679 | 25 | 512× | `usefulEntries_N_N_value <=` |
| `rtl/bpu/BypassShadowBuffer_1.sv` | 3168 | 29 | 512× | `usefulEntries_N_N_value <= {N'h0, usefulEntries_N_N_value[N]}; /` |
| `rtl/bpu/Phr.sv` | 2054 | 109 | 663× | `phr_N <= phrWriteLowBits[N]; // /home/xyl/bpu-verify-kunminghu-v` |
| `rtl/bpu/AheadBtbReplacer.sv` | 1059 | 15 | 187× | `else if (set_touch_ways_N_N_valid) // /home/xyl/bpu-verify-kunmi` |
| `rtl/bpu/WriteBuffer_38.sv` | 841 | 11 | 299× | `entries_N_N_wayData_N <= io_write_N_bits_wayData_N; // /home/xyl` |
| `rtl/bpu/WriteBuffer_8.sv` | 431 | 22 | 62× | `entries_N_N_entry_takenCtr_value <= io_write_N_bits_entry_takenC` |
| `rtl/bpu/MicroBtb.sv` | 277 | 31 | 32× | `entries_N_tag <= t1_updatedEntry_tag; // /home/xyl/bpu-verify-ku` |
| `rtl/bpu/WriteBuffer_30.sv` | 230 | 11 | 72× | `entries_N_N_wayData_N <= io_write_N_bits_wayData_N; // /home/xyl` |
| `rtl/bpu/RasStack.sv` | 222 | 87 | 24× | `commitStack_N_ctr <= _commitStack_ctr_T; // /home/xyl/bpu-verify` |
| `rtl/bpu/ReplacerState.sv` | 186 | 63 | 124× | `states_N <= io_write_N_bits_state; // /home/xyl/bpu-verify-kunmi` |
| `rtl/bpu/WriteBuffer_4.sv` | 154 | 19 | 14× | `entries_N_N_setIdx <= io_write_N_bits_setIdx; // /home/xyl/bpu-v` |
| `rtl/bpu/Tage.sv` | 106 | 29 | 11× | `: s2_readResp_N_entries_N_takenCtr_value[N])` |
| `rtl/bpu/WriteBuffer_28.sv` | 86 | 26 | 4× | `entries_N_N_entry_valid <=` |

**读法**：`AheadBtb.sv` 只有 **6 个发射点**却占 5084 行，最大单点 **1022×** 正是
`takenCounter[bank][index][way]` 的逐 cell 计数器更新；`BypassShadowBuffer*` 的
512× 是 512 个 useful cell；`Phr.sv` 的最大两点 663×/390× 是 PHR 每个比特的寄存器副本；
`ReplacerState.sv` 的 124× 是逐 set PLRU 状态写入。所有大块都是**按 cell / set / bit
的物理副本**，与本报告第一节的模块级审计一致。

**因此**：集成 BPU 的未命中在**类别**上是明确的（物理副本为主），且在最近选测上
**逐发射点可数**；但“完整回归的 8543 行按文件精确分布”仍缺报表，本轮**不宣称**
已对该分布逐行归因，这一限制保留。归因脚本自身另有 4 项负对照
（`tests/framework/test_residual_attribution.py`）。

## 三、结论

- 每个子模块的未命中项都已落到具体文件/行/arm 并给出分类；
- 其中 **结构不可达** 与 **物理副本** 保留原生分母、不授予覆盖信用；
- **没有发现「整体功能点缺失」**：所有已归因缺口都能对应到既有功能点的缺情况
  或物理/guard 副本；
- 集成 BPU 的未命中已在最近选测上**逐发射点归因**（35 文件 / 17972 行 / 6–109 个
  发射点，最大单点 1022×/663×/512× 均为逐 cell/bit/set 副本）；完整回归的 8543 行
  因历史报表裁剪，仍只有类别归因而无逐文件精确分布，已在第二节明确保留该限制。
