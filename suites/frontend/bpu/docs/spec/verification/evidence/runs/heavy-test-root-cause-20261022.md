# 为什么会有这么重的测试脚本（2026-10-22 实测归因）

> 本文回答一个问题：`tests/bpu/testcase` 只有 1031 个用例，为什么串行要
> **35171 秒（9.8 小时）**，而且 `tools/run_cost.py` 当时只预测 4480 秒（差 7.9 倍）。
> 结论是三层放大，全部有实测数字；文末给出已经落地的调整和仍需决策的大改。

## 一、时间去哪了：5 个用例占 30%

用已完成运行的 JUnit 报告 `results/bpu-composition-full-20261021-v1/pytest.xml`
（1031 个用例、实测总时长 35171 秒）统计：

| 阈值 | 用例数 | 占总时长 |
|---|---:|---:|
| ≥ 600 s | 5 | **30.0%** |
| ≥ 300 s | 13 | **42.2%** |
| ≥ 120 s | 28 | **50.2%** |
| ≥ 60 s | 64 | 57.8% |
| ≥ 30 s | 116 | 64.5% |

按文件看，前 11 个文件占 8.7 小时：

| 文件 | 实测合计 | 峰值/单例 | 用例数 |
|---|---:|---:|---:|
| `test_history_working_set.py` | **209.7 min** | 7919 s | 11 |
| `test_sc_provider_role_matrix.py` | 69.6 min | 34.4 s | 192 |
| `test_short_context_ownership.py` | 52.4 min | 597 s | 10 |
| `test_training_alignment.py` | 49.2 min | 25.3 s | 200 |
| `test_sc_used_nonzero.py` | 32.0 min | 75.5 s | 32 |
| `test_integrated_state.py` | 17.2 min | 415 s | 17 |
| `test_sc_masked_feedback.py` | 15.0 min | 20.2 s | 96 |
| `test_sc_threshold_bounds.py` | 14.9 min | 188 s | 8 |
| `test_sc_admission.py` | 11.8 min | 78.3 s | 22 |
| `test_integrated_abtb_counters.py` | 9.1 min | 289 s | 3 |
| `test_short_competition.py` | 7.9 min | 128 s | 4 |

## 二、三层放大（这是根因）

### 第一层：每个仿真周期要读约 8000～30000 个 DUT 值

对一个 279 个周期的 `test_training_alignment` 用例插桩测量：

| 指标 | 实测 |
|---|---|
| 周期数 | 279 |
| 墙钟 | 10.4 s |
| **每周期成本** | **37 ms** |
| 每周期 `compile_signal_sampler` 叶子读取 | **8 115** 次 |

`cProfile` 的分布与之一致：`xspcomm.XData__getattribute__` 1165 万次、
`xreactor.signals.sample` 226 万次。也就是说——**Verilator 本身不慢，慢的是
Python 观测层：每个时钟沿都把所有观测字段重新读一遍、转成普通 Python 对象、
再与八预测器参考模型逐项比较。**

按观察根采样器归因（同一个用例、279 个周期）：

| 绑定 | 叶子数 | 每周期调用 | 每周期叶子读取 |
|---|---:|---:|---:|
| 集成 ABTB 观察 | 1953 | 2.0 | 3906 |
| PHR 观察 | 1473 | 2.0 | 2946 |
| 写回观察 | 1260 | 2.0 | 2520 |
| AGTB/影子 | 630 | 4.0 | 2520 |
| 旁路 SRAM | 601 | 4.0 | 2404 |
| 影子状态 | 1024 | 2.0 | 2048 |
| PLRU `states`+`shadow` | 512 | 4.0 | 2048 |
| 主方向观察 | 1954 | 1.0 | 1954 |
| **合计** | | | **≈ 30 700** |

三个可直接指认的浪费：

1. **同一个宽 bundle 每周期被采样 2～4 次**（2473 项里 `2.0/4.0` 两个调用率）。
   上升沿与 `DriveStable` 两个订阅各自把整包读一遍，而 `DriveStable` 那侧只用到
   `reset/training.valid/read` 三个字段。
2. **PLRU 全 64 set 每周期全比**：`checks_aging/general/zero.py:43-44` 把
   `self.counter.plru[bank]` 与 `actual['states']`、`actual['shadow']` 各比一次，
   4 bank × 64 set × 2 组 = 512 个值/周期。而每个 bank 每周期最多只有一个 set
   （读集/写集/替换集）会变。这是"逐 set 物理副本"在**采样成本**上的第二次出现
   ——第一次出现在覆盖率的 65 个不可达 arm 上。
3. `PairChecks(coverage=None)` 走 `compact_history=False`，每条控制沿把整行
   `deepcopy` 一次并追加到**无上界**的 `control_records`。实测这一项不是主因
   （去掉后 10.35 s → 10.69 s，属噪声），但它是无界内存增长。

### 第二层：单例周期数与业务规模成正比

| 用例 | 周期数量级 | 为什么 |
|---|---:|---|
| `history_working_set[capacity-reverse]` | ≈ 21.4 万 | 512 条真实历史 × 4 个阶段（正向/重访/混合/末次消费） |
| `short_context_ownership[*]` | ≈ 1.6 万 | 10 个 profile，每个要两条分支共存 + 选择性修复 |
| `integrated_state::test_natural_failed_allocation_reaches_useful_aging` | ≈ 1.1 万 | 真实失败分配一路走到 useful 老化 |

7919 s ÷ 37 ms ≈ 21.4 万周期，与"512 × 418 周期/身份"吻合。**这一类不是写错了，
是功能点本身要求的枚举规模**（"32 与 512 历史的有界真实路径程序"）在 37 ms/周期的
观测成本下直接变成 2.2 小时。

### 第三层：`estimated_runtime` 是"每个测试函数"，而矩阵是"每例"

这是 `run_cost.py` 差 7.9 倍的直接原因。改动前全仓只有 19 处 hint，最重的
`test_history_working_set.py`、`test_sc_provider_role_matrix.py`、
`test_training_alignment.py` 一个都没有。补上 hint 后仍然差 2.6 倍，因为：

| 文件 | 实测合计 | 声明值 | 实测/声明 |
|---|---:|---:|---:|
| `test_sc_provider_role_matrix.py` | 4178.7 s | 34 s | **122.9×** |
| `test_training_alignment.py` | 2949.2 s | 25 s | **118.0×** |
| `test_sc_masked_feedback.py` | 902.7 s | 20 s | **45.1×** |
| `test_sc_used_nonzero.py` | 1920.9 s | 76 s | **25.3×** |
| `test_sc_admission.py` | 706.7 s | 78 s | 9.1× |
| `test_history_working_set.py` | 12579.7 s | 7920 s | 1.6× |

hint 描述的是"一个函数多贵"，而代价是"一个函数多贵 × 参数化出多少例"。
调度器只按前者排序，于是 200 例 × 25 s 的矩阵在调度上看起来只有 25 s。

## 三、已经落地的调整（本轮，均已验证）

| 调整 | 效果 | 证据 |
|---|---|---|
| 给 11 个实测长尾文件补 `estimated_runtime`（模块级，取实测峰值） | `run_cost` 的 hinted 从 4480 s → 13480 s；最重文件能被调度器前置 | `tests/framework/test_long_pole_budget.py`、`test_run_cost.py` 33 PASS |
| `tools/run_cost.py` 新增 `--measured <pytest.xml>` | 直接给出实测总时长、每文件实测/声明比；BPU 全量 35171 s 一眼可见 | `run_cost --select tests/bpu/testcase --measured …` → `measured=35171s (9.8h)` |
| 新增长尾门禁 `tests/framework/test_long_pole_budget.py` | ①实测 ≥300 s 的文件必须带 hint 且 ≥ 实测峰值的一半；②已复核的 hint 文件清单必须精确相等（新增必须显式登记）；③昂贵矩阵的用例数作为复核过的数字固定下来 | 33 PASS |
| 记录"per-case × cases"这个放大形状 | 让下一个 200 例矩阵无法悄悄出现 | `test_hint_multiplication_is_visible_for_parametrized_matrices` |

**没有做的事**：没有删除、跳过、降权任何一个用例；没有改 RTL/DUT/SDK；没有放宽
任何断言。hint 只影响收集顺序，`--measured` 只读历史报表。

## 四、还没做的结构性改动（需要决策，按收益排序）

1. **上升沿与 `DriveStable` 共用一次采样**（预计省 30～40%）。
   `PipelineObservation.__aenter__` 现在为 `DriveStable` 另建采样器读
   `reset/training.valid/training.ready/training.reads`；ABTB 路径则在
   `observe_controls` 里又采整包。把"控制沿只读它真正用到的字段"做成独立的小
   binding，宽包每周期只采一次。
2. **PLRU 改为"按访问集比较 + 静默边界全 64 集扫描"**（预计省 15～20%）。
   每周期只比 `readSetIdx/writeSetIdx/replaceSetIdx` 三个 set，流水线静止时再全扫。
   代价：未访问 set 的越权改动要到下一个静止点才被发现。这是**真实但有限的检查强度
   下降**，必须在 `BPU-ABTB-*` 里显式登记，不能悄悄做。
3. **`control_records` 改为有界**（内存安全，不影响判定）。
   `compact_history=False` 时每条控制沿一条无上界记录，长用例会持续增长。
4. **512 身份容量用例拆分**（不改断言，只改运行粒度）。
   把 `capacity-reverse` 按 64 身份分 8 块，每块独立 DUT、独立断言；失败定位更细，
   也能并行。总周期数不变，但墙钟可降到 1/8 左右。

## 五、不变式

- 完整回归边界仍为 **24776 PASS / 88 FAIL / 3 XFAIL**；本轮全部为选测。
- 本文所有数字来自 `results/bpu-composition-full-20261021-v1/pytest.xml`（1031 例）
  与本轮的插桩运行（279 周期 / 10.4 s / 8115 叶子读取/周期）。
- 每个结论都给出可复算的分母；没有"看起来很快"的主观判断。
