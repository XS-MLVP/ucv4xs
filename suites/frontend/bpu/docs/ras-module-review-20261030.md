# RAS（MicroRas + RasStack）DefaultConfig 迁移复核与覆盖率闭环（2026-10-30）

本文记录整芯片 DefaultConfig RTL 下 `Ras`（`MicroRas` + `RasStack`）单 DUT 的复核结果。
功能点沿用 `BPU-RAS-001..017`；4 个已归档真实 RTL FAIL 原样保留，不登记 XFAIL。

## 整芯片端口裁剪与适配

| 实际端口 | 处理 |
|---|---|
| `io.enable` | 真实引脚存在（`Ras` 顶层仍消费）；新增独立 `control` 驱动，复位后置 1 |
| `specIn.bits.attribute` | 只剩 `attribute_rasAction` 叶；`branchType` 被裁，不再驱动/比较 |
| `redirect.bits.meta` | 整芯片展平为 `meta_ras` 叶；`topRetAddr_addr` 是输出字段，不是驱动输入 |
| `commit.bits.meta` | 展平为 `meta_ras` |
| `sramResetDone` / `trainReady` | Scala 常量，按常量绑定 |
| `stageCtrl` | 只有 s1/s2/s3_fire；复位/使能顺序由 agent 管理 |

## 语义适配修正

1. **独立 enable 门控**：`Ras.scala` 用 `io.enable` 门控 spec/commit；之前适配误以为该引脚被裁。
   新增 `ras.control` 驱动，并在每次 reset 后置 1。
2. **属性只剩 RAS action**：`RasOperation.frame()` 不再输出 `branch_type`；用例和纯模型测试同步删除该字段。
   这是 DCE 裁剪，不是把字段当作无关数据忽略。
3. **meta 回灌投影**：`redirectMeta` 多出只读 `topRetAddr_addr`；把 checkpoint 回灌时必须投影到真实
   `meta.ras` 叶（ssp/sctr/tosw/tosr/nos），否则驱动形状不匹配。
4. **复位边界**：输出侧采样 `dut.reset`，复位为高的拍不参与语义比较；此前跨 reset 场景的“top 突然为 0”
   假失败由此消除。

## 运行结果

```sh
.venv/bin/ucv run bpu --workers 8 --output results/ut-ras-final-20261030 -- tests/ras
```

- 原生 RAS：**23 PASS / 5 FAIL / 1 XFAIL**；纯模型 **565 PASS / 0 FAIL**。
- 5 个 FAIL 与迁移前逐条一致：
  - `test_real_original_commit_applies_its_resolved_stack_action[return-and-call]`（BPU-BUG-10 相关）；
  - `test_recovery_return_and_call_restores_before_redo`；
  - `test_resolved_return_and_call_retires_real_source_address`；
  - `test_speculative_return_and_call_replaces_only_the_youngest_frame`（3 条均为 BPU-BUG-10）；
  - `test_ras_functional_coverage_closes_defined_bins`（由上述失败导致的覆盖门禁）。
- XFAIL 为既有 `test_disable_gate_preserves_stack`，保持原判定。

## 覆盖率（`results/ut-ras-final/rtl-line-coverage.json`）

| 指标 | 结果 |
|---|---|
| RTL 源行 | **804/838 = 95.94%** |
| `v_branch` 分支臂 | **282/316 = 89.24%** |
| `v_toggle` 位方向 | **3911/7218 = 54.18%** |

未覆盖归类：

| 项 | 归类与依据 |
|---|---|
| `RasStack` commit 队列 33 行 | **整体功能点缺失**：提交栈的重复提交/队列回绕路径没有独立用例（现有用例集中在 speculative/redirect 侧）；也对应真实 FAIL 的 return-and-call 语义未被消费 |
| 初始化复位 else 臂 | 结构不可达 |
| 内部 toggle | 提交栈大数组的数据模式未遍历；属数据值覆盖 |

## 结论边界

- 本轮把 RAS 恢复到迁移前判定：4 个真实 FAIL 保留、其余用例与纯模型全部通过；覆盖率缺口集中在
  `RasStack` 提交队列，需要补“重复提交/回绕”语义用例并复核 return-and-call 缺陷是否同源。
