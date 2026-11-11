# 为什么一次选测会跑两小时，以及如何避免（2026-10-21）

## 一、实测数据

`tests/bpu/testcase` 共 **1031 个收集项**。按 `estimated_runtime` 提示统计：

| 文件 | 提示合计 | 单个最大 | 测试函数 |
|---|---:|---:|---:|
| `test_integrated_abtb_counters.py` | 1840s | 800s | 3 |
| `test_integrated_state.py` | 1340s | **1340s** | 11 |
| `test_direction_recovery.py` | 930s | 930s | 1 |
| `test_sc_threshold_bounds.py` | 280s | 220s | 1 |
| `test_early_aging.py` | 90s | 90s | 1 |
| 其余 145 个文件 | 0 | 0 | 172 |

UTAGE 侧同样：`test_useful_update_full_required_address_matrix` 单项 **894s**，
`test_useful_allocation_address_matrix` 101s，其余多在 5s 以内。

也就是说：**一个选测的墙钟时间几乎完全由 3~5 个矩阵级用例决定**，
其余 140+ 个文件加起来不到 6 分钟。

## 二、四个真实原因

### 1. 没有超时机制（结构性）

`pytest.ini` 明确写着：

```
estimated_runtime(seconds): deterministic scheduling hint, never a timeout or selection rule
```

`pytest-timeout` 未安装，`tools/refresh_coverage.py` 也没有墙钟上限。
所以一个慢用例（或卡住的用例）可以无限期占用一个 worker，而其余 7 个 worker
只能等它——这就是"97% 之后停了一个多小时"的形态。

### 2. 长尾 + `--maxschedchunk=1`

`order_tests` 把提示最贵的放在最前，这本身是对的；但当一个用例本身就是
20 分钟量级时，**它比其余全部用例加起来还长**，并行度在这段时间里塌缩为 1。
`--max-worker-restart=0` 又意味着没有 worker 补位。

### 3. 我在运行期间改工作树（可避免，且伤害最大）

`refresh_coverage` 在结束时比对冻结 epoch，一旦不一致就整轮作废：

```
ValueError: execution source epoch changed
```

本轮至少有两次整轮运行因此被丢弃并重跑：

| 运行 | 时长 | 作废原因 |
|---|---:|---|
| `utage-override-feedback-20261021-v1` | 15:07 | 运行中新增/修改了测试与文档 |
| `bpu-composition-full-20261021-v1` | >2h | 运行中修改了 `test_composition_shared_redirect.py` |

用新工具核对，后者只有 **1 个文件**变了：

```
frozen=3050 current=3050 changed=1
  changed test_composition_shared_redirect.py
```

### 4. 顺序选择不当

把 1031 项的 BPU 全量当成"验证一次组合格"的手段，是把小时级回归和秒级定向
混在一起。组合格只需要相关文件，不需要 150 个文件。

## 三、已实现的防复发措施

新增 `tools/run_cost.py`（4 项纯测试 PASS）：

```bash
# 运行前预览成本，按 900s 预算分块（不拆文件）
python3 tools/run_cost.py --select tests/bpu/testcase --budget 900

# 运行被作废时，直接指出是哪些文件改了
python3 tools/run_cost.py --epoch-delta results/<run>
```

实测输出：

```
files=150 tests=187 hinted=4480s hints=8 unhinted_files=145
heaviest:
  1840s max= 800 tests=  3 tests/bpu/testcase/test_integrated_abtb_counters.py
  1340s max=1340 tests= 11 tests/bpu/testcase/test_integrated_state.py
   930s max= 930 tests=  1 tests/bpu/testcase/test_direction_recovery.py
suggested chunks (budget 900s):
  chunk0: 1840s files=1
  chunk1: 1340s files=1
  chunk2: 930s files=1
  chunk3: 370s files=147
```

`--epoch-delta` 只比对冻结键（绝对路径），不会把 site-packages 算成 36000 个
"变更"，因此作废原因一眼可见。

## 四、之后的运行纪律

1. **先预览再启动**：`run_cost.py --select <path>`，确认最贵用例与总提示时长。
2. **按块运行**：把 ≥900s 的文件单独跑，其余合并跑；一块作废不会连累全部。
3. **运行期间冻结工作树**：只读、只分析，不改测试/计划/文档。要改就等运行结束，
   或先复制到临时目录验证。
4. **优先定向**：验证一个组合格用 1~7 个文件（如本轮的
   `bpu-composition-redirect-*`，13 项 / 28s），不用全量 1031 项。
5. **单用例耗时纳入审查**：`test_run_cost.py` 断言"hinted 文件不超过 6 个、
   最大≥900s 的文件必须显式存在"，新增一个 20 分钟级用例会被注意到。
6. **依旧没有超时**：这是刻意的（模拟器里强杀会留下不干净的进程/共享库状态）。
   替代手段是上面的分块与预览，而不是加 `pytest-timeout`。

## 五、诚实的边界

- 本次分析基于提示值与实际日志；**未安装**新的超时插件，也没有改
  `refresh_coverage` 的合并/冻结逻辑。
- 该工具不减少任何测试、不改变任何判定、不触碰覆盖率分母。
- 分块运行得到的仍是选测证据，不替代保留的完整回归
  （24776 PASS / 88 FAIL / 3 XFAIL）。
