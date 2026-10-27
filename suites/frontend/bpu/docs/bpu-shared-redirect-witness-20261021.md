# 上级 BPU：一个重定向是否真的同时比较了两个预测器窗口

## 为什么需要这一格

`BPU-ABTB-054` 证明 ABTB 自己会撤销在途窗口，`BPU-UTAGE-026` 证明 MicroTAGE
自己会撤销。两者都不能证明**组合层**的事实：

- `io.fromFtq.redirect` 是否真的在同一拍到达两个预测器；
- 独立检查器在该拍是否**同时**比较了两个窗口，而不是只比较其中一个。

如果只比较一个，那么“另一个预测器在重定向拍的行为”完全没有证据，而运行仍可能是绿的。

## 做法

新增 `BPU-INT-108` 与 `tests/bpu/testcase/test_composition_shared_redirect.py`：

1. 用真实的 `early_direction_program` 跑完“冷启动 → Ahead 条件路径 → 负向短历史学习”，
   期间两个预测器都已服务过原预测；
2. 向 `PipelineObservation` 注入一个 `WitnessChecker`（继承默认 `PipelineChecker`，
   不改变任何比较逻辑）；
3. 在每个采样拍，若 `redirect.valid` 为真且该拍确实被比较（`last_tick == tick`），
   检查期望字典里是否**同时**含 `ahead` 与 `early_direction`；
4. 断言这个集合非空，并且其中至少一拍 `ahead.meta_valid == 1`——否则“空窗口与空期望
   一致”会让见证空转。

关键实现细节：`records` 是有界 deque（len=8），早期版本用“长度变化”判断是否新增，
在稳态下长度恒为 8 而恒不成立；现在按 `last_tick == event.tick` 判断。

## 实测见证

`results/bpu-composition-redirect-20261021-v1` 与 `-v2` 的见证文件：

```
pc 0x40000000  cycles 5
 tick 294  ahead_meta_valid=1  ahead_hits=(0,0,0,0)  early_hits=(0,0,0,0)
 tick 338  ahead_meta_valid=1  ahead_hits=(0,0,0,0)  early_hits=(0,0,0,0)
 tick 376  ahead_meta_valid=1  ahead_hits=(0,0,0,0)  early_hits=(0,0,0,0)
 tick 434  ahead_meta_valid=1  ahead_hits=(0,0,1,0)  early_hits=(0,0,0,0)
 tick 478  ahead_meta_valid=1  ahead_hits=(0,0,0,0)  early_hits=(0,0,0,0)
```

五拍都在重定向有效时同时比较了两个窗口，且其中一拍 ABTB 有真实命中
（`ahead_hits[2]=1`），所以比较不是空转。

## 这一格**没有**证明什么

- 没有证明两个预测器在重定向拍都执行了撤销（各子模块分别证明）；
- 没有证明 `early_hits` 全 0 是“正确的撤销结果”还是“本拍窗口刚好无效”——
  见证只统计比较是否发生，不把 DUT 实际值当期望；
- 没有覆盖完整 FTQ 寿命、后端真值或所有预测器组合。

## 边界

`BPU-INT-108` 是组合层**见证**功能点，`evidence.coverage` 为空，不授予覆盖率信用，
也不改变任何原生分母。

## 八、位置冲突格（明确未验证）

对现有 `early_direction` 程序统计 29 个“双窗口同时比较”的拍：

```
repair2 = 0
taken-position-disagree = 0     # 没有“两边都 taken 但位置不同”的拍
```

即这些程序里 Ahead 与 Main 从未在**位置**上真正冲突，因此 `BPU-INT-109`
只覆盖了“两边都命中且仲裁有答案”，没有覆盖“两边都 taken 但位置不同”。

构造它需要同一 PC 上 Ahead 预测 taken@P、Main 预测 taken@Q（P≠Q）。用两条独立
训练临时拼该状态，会被检查器的 origin 规划拒绝
（`planned origin at actual feedback acceptance`），说明需要专用组合程序。
本轮登记为**显式未验证**，不用临时激励硬凑。
