# FTQ 覆盖率闭环分析（2026-10-30）

## 运行与统计口径

- 基线：`public-893e1580b`，DefaultConfig 完整香山 RTL，DUT 闭包由 `ucv prepare` 提取。
- 构建：Picker 生成 `ResolveQueue`、`CommitQueue`、`Ftq` 三个原生 DUT，均通过独立进程冒烟。
- 运行：`.venv-uc-toffee/bin/python tools/run_regression.py --output results/ftq-final-20261030b`。
- 行覆盖：只统计 RTL 闭包中的 `v_line`/`v_branch` 原生 LCOV `DA` 行，排除了 Picker wrapper；
  锚点行和 `S` 行区间按 Verilator 的合并语义展开。
- 分支：独立的 `v_branch` 点，`arm` 保留 `if/else/cond_then/cond_else`。
- Toggle：独立的 `v_toggle` 点，按信号的每个方向分别计数。
- 本次实际判定：**109 PASS，2 XFAIL（strict，已确认 RTL 缺陷），0 FAIL，0 SKIP**。

结果文件：

```text
results/ftq-final-20261030b/run.json
results/ftq-final-20261030b/pytest.xml
results/ftq-final-20261030b/traceability.md
results/ftq-final-20261030b/coverage-report/coverage.json
results/ftq-final-20261030b/coverage-report/coverage-gaps.md
```

## 本轮变化：按 driver/monitor 重组

2026-10-30 把验证包从“测试直接操作引脚 + 集中式 harness”重组为 agent / driver /
monitor / checker / transaction 分层：

- 每个 DUT 一个 agent；agent 拥有 driver、monitor 和 checker，测试只提交事务。
- driver 按协议区分 pulse / level / reset，并声明引脚所有权；overlap 在 fixture 边界报错。
- monitor 只在上升沿被动采样公开输出，checker 只比较解码事务与独立 oracle。
- 三个 agent 共用 `common` 的 pin、driver、monitor 和 pytest fixture。

重组不改变 DUT 闭包、RTL 或检查强度；功能点与测试的映射由
`tools/traceability.py` 从 `@pytest.mark.feature` 重新生成。重组后第一次全量运行
（94 PASS / 2 XFAIL）暴露了顶层枚举缺口：`ftq` 行覆盖从 97.4% 回落到 92.6%，
原因是旧用例把 slot/source 扫描集中在独立 `resolve_queue` DUT，顶层只保留了
较粗的组合。随后补充了顶层物理槽 × 分支槽 × 来源矩阵，把缺口关闭。

## 逐轮闭环

每一轮都先补功能点/情况，再重新运行；下一轮数字包含本轮和此前全部用例。

| 轮次 | 补充内容 | resolve_queue 行/分支/toggle | commit_queue 行/分支/toggle | ftq 行/分支/toggle |
|---|---|---:|---:|---:|
| 0 初版子模块用例 | 准入、合并、过滤、背压、冲刷、容量、复位 | 36.8% / 54.2% / 2.8% | 43.7% / 89.4% / 47.5% | — |
| 1 顶层功能用例 | 预测、预取/取指、override、重定向、commit、train | 37.6% / 55.3% / 3.8% | 70.7% / 94.2% / 90.0% | 16.8% / 56.3% / 24.9% |
| 2 全索引/全槽枚举 | 64 个 meta 索引、8 个分支槽、32 条流式 wrap | 52.3% / 85.7% / 10.9% | 70.7% / 94.2% / 90.0% | 87.0% / 59.9% / 41.7% |
| 3 lane 矩阵与顶层组合 | 后端/IFU lane 组合、同索引部分 lane、顶层 resolve/commit 流 | 55.1% / 86.2% / 11.7% | 100.0% / 99.8% / 92.5% | 92.0% / 90.5% / 44.5% |
| 4 物理槽 × 分支槽 × 来源 | slot/source 扫描、顶层训练槽扫描、异常种类 | 100.0% / 99.9% / 18.8% | 100.0% / 99.8% / 92.5% | 97.4% / 97.5% / 45.6% |
| 5 全 1/全 0 payload | meta 全 bit、分支 payload、call/return payload | 100.0% / 99.9% / 89.3% | 100.0% / 99.8% / 100.0% | 97.4% / 97.8% / 83.5% |
| 6 合法激励、独立模型、缺陷定位 | `allocate()` 生产者序列、被动指针不变量、ResolveQueue 随机模型、溢出缺陷 | 100.0% / 99.9% / 90.0% | 100.0% / 99.8% / 100.0% | 97.4% / 97.8% / 82.8% |
| 7 driver/monitor 重组 + 顶层矩阵 | 每 DUT agent、pin 所有权、顶层物理槽 × 分支槽 × 来源、IFU 逐槽命中、首误预测全槽、同拍同索引 | 100.0% / 99.9% / 89.2% | 100.0% / 99.8% / 100.0% | **100.0% / 99.6% / 84.4%** |

第 7 轮新增的顶层用例直接对应原来的 R-02：

- `test_top_level_branch_slot_and_source_priority_sweep`：对每个物理槽（enq mod 16）、
  每个分支槽（0..7）和每个来源（backend lane 0..2、IFU）各写一次，使用单 lane 周期
  保证分支槽位置确定；同一 entry 的连续报告阻止提前出队。512 个组合逐一断言
  分支位置、顺序和 target。
- `test_ifu_resolve_hits_resident_entry_in_every_physical_slot`：IFU 重定向命中已驻留
  entry 的 16 个物理槽；IFU resolve 是寄存后的第二拍，因此用例在重定向拍保持一个
  后端报告，避免 entry 在 IFU 报告到达前被训练取走。
- `test_first_mispredict_mask_covers_every_branch_slot`：8 个分支位置分别成为首个
  误预测，验证训练端口只保留到该位置。
- `test_same_cycle_same_index_lanes_merge_in_program_order` 和
  `test_top_level_resolve_guard_limits_admission_and_preserves_order`：同拍同索引
  合并与顶层容量 guard。

## 最终覆盖

| DUT | 行覆盖 | 分支覆盖 | Toggle |
|---|---:|---:|---:|
| `resolve_queue` | 8045/8045 = 100.0% | 733/734 = 99.9% | 17573/19708 = 89.2% |
| `commit_queue` | 2259/2259 = 100.0% | 519/520 = 99.8% | 1364/1364 = 100.0% |
| `ftq` | 51996/51996 = **100.0%** | 1616/1622 = 99.6% | 127074/150606 = 84.4% |

## 未覆盖项逐项定位

### 1. 已确认 RTL 缺陷：ResolveQueue 分支槽溢出

- 独立 `resolve_queue` 的 100% 行覆盖并不代表容量边界正确。两个定向用例确认：
  8 条分支后再来第 9 条覆盖 slot 7；6 条后同拍来 3 条覆盖 slot 0。
- 归因：`ResolveQueue.scala:137-138` 的 `firstEmpty + PopCount(hitPrevious)` 未与
  `ResolveEntryBranchNumber` 比较，动态 Vec 下标越界回绕。
- 合法依据：DefaultConfig 的 `NumBtbResultEntries=10`，一个 fetch block 可合法产生
  第 9/10 个分支解析；8 槽是存储容量，超出应丢弃而不是覆盖。
- 两个用例以 `strict XFAIL` + `rtl_defect` 保留；完整说明见
  [`bugs/resolve-queue-branch-overflow.md`](bugs/resolve-queue-branch-overflow.md)。

### 2. 三个 DUT 的 `initial` reset else

- `ResolveQueue.sv:12172`、`CommitQueue.sv:4089`（顶层闭包中同样存在）、
  `Ftq.sv:110865`：这是 Verilator `initial` 随机初始化块中 `if (reset) ... else`
  的 else 分支。
- 本测试台在时间 0 之后不再让复位回到“初始化块执行时的 else 语义”，运行期复位只走
  `if (reset)` 的清零路径。归为**测试台不可达的初始化分支**，不是功能点缺失。
- 三个模块行覆盖均为 100%，没有未覆盖 RTL 行。

### 3. 顶层闭包中 3 个同拍 IFU 合并 mux 臂

- `ftq` 闭包剩余 3 个分支臂：`ResolveQueue.sv:2587/2589/2591` 的
  `? enqIndex_0/1/2`，对应“同一拍 backend lane 与 IFU lane 同索引”时选择已分配
  entry 物理槽的多路选择。
- 在 `Ftq` 中 IFU resolve 由重定向寄存一拍后产生，不能与本拍 backend lane 同拍，
  因此这三个臂对顶层是**结构不可达**。独立 `resolve_queue` DUT 可直接驱动同拍四源，
  已由 `test_backend_lane_and_ifu_same_index_merge_in_one_cycle` 覆盖，其闭包只剩
  reset else 一个臂。
- 不把子模块证据冒充顶层证据：顶层仍如实记录这 3 个臂未命中。

### 4. 顶层重复枚举缺口（已关闭）

- 上一轮的 1348 行 / 34 分支缺口已由第 7 轮顶层矩阵关闭；`ftq` 行覆盖从 97.4%
  到 100.0%，`Ftq` 模块自身未覆盖行继续保持 0。

### 5. Toggle 缺口

- `resolve_queue` 剩余 2135 个 toggle 点主要是未驱动的输入高位/flag 方向和部分数组位；
  指针 flag 身份用例已覆盖 flag 的两种取值，剩余属于 payload 位组合，不是控制路径。
- `ftq` 剩余 23533 个 toggle 点集中在 64 项 meta/entry 的高位、PC/target 的高位和部分
  一次性状态。全 1/全 0 meta 扫描已把顶层 toggle 从 45.6% 提升到 84.4%；剩余不改变
  已检查的 FTQ 所有权、重定向、训练和提交语义。
- `commit_queue` 的 toggle 已达到 100%。

## 结论边界

- 本次只证明 `public-893e1580b` + DefaultConfig RTL 与本次 Picker/uc-toffee 原生包上的
  上述功能点和覆盖数字。
- `109 PASS` 不包含 2 个 XFAIL；ResolveQueue 超容量行为是已确认缺陷，未修复。
- 行覆盖 100% 不表示所有分支和 toggle 已覆盖，也不表示没有功能缺陷；R-01 正是在
  100% 行覆盖之外由定向容量用例发现的。
- 剩余分类明确保留：测试台不可达初始化分支、顶层结构不可达的同拍 IFU 合并臂、
  payload toggle。不把“子模块覆盖 100%”改写成“顶层组合 100%”，也不删除或放宽
  任何失败检查。
- 结果目录和覆盖率数据库不进入 Git；本文件只保留运行入口、实际数字和缺口判断。
