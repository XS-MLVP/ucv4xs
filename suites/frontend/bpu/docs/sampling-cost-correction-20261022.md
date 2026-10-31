# 采样成本：三项"优化"的实测结论与更正（2026-10-22）

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


> 上一轮我给出的三项改动里，**有两项是错的**：它们会真正削弱检查，而不是消除浪费。
> 本文记录实测证据、更正，以及实际落地的那一项的真实收益（约 0.80 倍墙钟，不是 13 倍）。

## 一、更正：我上一轮说错了两件事

### ① "preedge 只该采输入字段" —— 错

我当时的依据是 `BypassMonitor.start` 对同一个 2006 叶子节点建了两个订阅
（`RisingEdge` 与 `DriveStable`），因此判断 preedge 那半是"重复读"。

实测它不是重复读，而是**同一份寄存器状态被两个相位各自校验一次**：

```python
# suites/frontend/bpu/bpu/checker/abtb/checks_aging.py:104
self.states(abtb)          # 在 observe_controls 里，即 preedge 相位
#   -> compare(self.counter.plru[bank], actual['states'])   # 64 set
#   -> compare(self.counter.plru[bank], actual['shadow'])   # 64 set
#   -> compare(self.counter.cells, row['cells'])            # 1024 counter cell
```

如果照我原来说的把 preedge 采样缩到"只有输入字段"，`states()` 就读不到
`cells/states/shadow`，1024 个计数器 + 256 个 PLRU 的 preedge 校验会**整块消失**。
这不是省成本，是删检查。**不做。**

### ② "WriteObservation 与 NonzeroObservation 各建一个 monitor" —— 已经是这样

`WriteMonitor` 的 binding 就是 `Bundle(reset, banks=…)`（`monitor/abtb/write.py:61`），
本来只含写入路径，没有重复整棵 ABTB。我原来说的"同族绑定两份"不存在。
**无需改动。**

### ③ 唯一真实存在的是"两遍转换"，已落地

`compile_sampler` 产出 `BundleValue`/`LogicValue` 树，调用方随后用 `_plain` 再走一遍
把它转成 `dict`/`tuple`/`int`。每个叶子被分配两次对象、递归两次。
新增 `suites/frontend/bpu/runtime/plain_sampler.py::compile_plain`，一次成型，直接产出
`_plain(compile_sampler(node)())` 的等价结构。

## 二、`compile_plain` 的实测收益（不是 13 倍）

| 场景 | 改前 | 改后 | 比 |
|---|---:|---:|---:|
| 279 周期 `test_training_alignment[0]`（插桩） | 10.39 s | 8.27 s | **0.80×** |
| 同用例每周期成本 | 37.2 ms | 29.7 ms | 0.80× |
| 纯采样微基准（2000 叶子 × 279 次） | 2.98 µs/叶子 | 0.72 µs/叶子 | **4.1×** |

**为什么端到端只有 0.80×**：4.1× 只是"采样+转换"这一段的加速，而这一段在 37 ms/周期里
只占约 5 ms；其余约 32 ms 是**参考模型重算 + scoreboard 逐项比较**。所以把采样做到零，
上限也只有约 1.15×。

同一选择集里多数 BPU 监视器用例都稳定落在 **0.75–0.85×**：

| 用例 | 改前 | 改后 | 比 |
|---|---:|---:|---:|
| `integrated_state::test_natural_failed_allocation_reaches_useful_aging` | 415.5 s | 340.3 s | 0.82× |
| `integrated_state::test_two_program_full_shadow_eviction_and_sram_return` | 68.4 s | 56.2 s | 0.82× |
| `integrated_state::test_parent_training_policy_from_public_metadata` | 69.2 s | 56.8 s | 0.82× |
| `ahead_working_set::test_natural_branch_working_set…` | 57.7 s | 43.6 s | 0.76× |
| `ahead_working_set::test_lower_shadow_ring_wrap` | 60.9 s | 42.4 s | 0.70× |

### 一处 4.2× "变慢"是并行竞争，不是回归

`test_integrated_state::test_repeat_retirement_saturates_and_splits_entry[9]`
在并行跑里 3.2 s → 13.5 s。串行重跑两个参数各自 **0.45 s**（call），
差别全在 `setup`（DUT 构建）：`[9]` 7.78 s、`[10]` 1.75 s。
**DUT 构建在 8 路并行下有 1.6–7.8 s 的波动**，短用例因此完全被 setup 支配。
这也解释了为什么"小用例"跑起来也不快。

## 三、等价性门禁（防止优化偷改语义）

`tests/framework/test_plain_sampler.py`（5 项，无 DUT）+ `tests/bpu/testcase/test_plain_sampler_live.py`
（7 项，真实 DUT）：

| 断言 | 为什么必须有 |
|---|---|
| 结构与类型逐字段相同（dict/tuple/int） | 只比较值会漏掉 `dict` vs `BundleValue` 的区别 |
| 未知位（X/Z）仍然抛 `ValueError` | **这是关键**：如果新采样器把 X 位掩成 0，真实 RTL 分歧会变成 PASS |
| >64 位叶子走字节路径且不截断 | 我的快路径只覆盖 ≤64 位；宽叶子必须回退 |
| 宽叶子的 X 位也抛错 | 回退路径同样不能吞掉未知位 |
| 零宽按 1 位处理 | 与 `xreactor.signals.signal_width` 对齐 |
| 7 种真实 BPU bundle（main / sc / tage / ahead / ittage / ras / all）逐字段相等 | 合成假叶子证明不了真实绑定 |

## 四、下一步该怎么省（按收益，都需要决策）

1. **DUT 构建 1.6–7.8 s/用例**：短用例的主要成本。可考虑同一文件内复用 DUT + 完整
   `reset()`，但必须证明 reset 后状态与新建完全等价（否则就是最危险的一类假通过）。
2. **参考模型重算约占 85%**：`compare()` 每周期把 1024 计数器 + 256 PLRU + 全套
   metadata 与模型逐项比。真正的省法是"只在可能变化时比"，但那必须给出"为什么这个
   状态这一拍不可能变"的独立论证，否则等于抽样。
3. **512 身份容量用例拆块**：断言不变、总周期不变，但可并行，墙钟约 1/8。

## 五、不变式

- 未删除、跳过、降权任何断言；未改 RTL/DUT/SDK；未放宽 XFAIL。
- 本选择集 8 个 FAIL **全部**是 2026-10-21 全量回归中同样的既有失败，逐节点比对无新增。
- 完整回归边界仍为 **24776 PASS / 88 FAIL / 3 XFAIL**。
