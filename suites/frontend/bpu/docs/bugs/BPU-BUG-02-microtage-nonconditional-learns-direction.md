# BPU-BUG-02：MicroTAGE 为同一位置的非条件跳转更新了条件分支学习

MicroTAGE 学习条件分支“跳还是不跳”。如果早期预测把某个位置识别成条件分支，但较晚的 S3 预测将那里纠正为直接或间接跳转，就不应把该跳转的 taken 当作原条件分支的方向奖励。这里是预测阶段之间的快训练，不是执行反馈。

归档中，这类反馈不仅改变了方向计数，也出现了保护值变化。两者是不同的检查项，不能混成“表项被覆盖”或“命中丢失”。

状态：模块训练差异及资格筛选路径已定位。同位置直接、间接跳转失败，条件分支对照通过。但真实 ABTB、PHR、S3 是否共同产生完整复现序列仍待集成见证，不能仅凭直接构造的快训练定性 SoC 缺陷。尚未修改 RTL。

## 怎样触发

1. 先训练好一个条件分支，让 MicroTAGE 保存稳定的学习状态。
2. 发起一次预测，保存那次预测携带的条件分支信息。
3. 提交快训练，指定晚阶段结果：同一位置是一条直接跳转或间接跳转，而非条件分支。
4. 再检查原条件分支的方向计数与保护值。

预期只限制**同一位置的指令类型不符**。如果条件分支位于实际跳转之前，它属于已经执行的前缀，仍可能需要学习“不跳转”；不能把这类合法训练一起禁掉。

## 已观察到的结果

| 代表场景 | 检查项 | 预期 | 实际 |
|---|---|---:|---:|
| 双预测来源中，后一个位置实际为直接跳转 | 方向计数 `2.counter` | 6 | 7 |
| 已训练条件分支，同位置反馈改为直接跳转 | 保护值 `(0, 0)` | 1 | 0 |

第二行来自 `test_resolved_nonconditional_same_position_preserves_warm_conditional[direct]`。其中的 `(0, 0)` 是保护值字典的索引，不是“有效位由 1 变 0”，也不能据此声称方向计数或命中消失。

第一行对应下方复现命令，直接显示非条件跳转反馈奖励了方向计数。

## 代码线索与待确认项

[MicroTage.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/utage/MicroTage.scala) 中，`trainHasAbtbBranch` 主要按“预测分支有效、位置不晚于最终跳转”筛选训练对象：

```scala
t0_abtbResult(i).valid &&
  (finalPrediction.cfiPosition >= t0_abtbResult(i).cfiPosition)
```

位置相等时，这个条件没有区分最终指令是否还是条件分支。后面的 `actualTaken` 又把“位置相同且实际跳转”交给方向学习，于是非条件跳转也奖励了原条件分支。附近的误预测判定已检查 `finalPrediction.attribute.isConditional`，两条路径的资格不一致。

修复方向应区分“更早的条件分支”和“同一位置的非条件跳转”。直接给全部训练加 `finalPrediction.isConditional` 限制，会误伤前者，不是可直接采用的修复方案。本次确认的是方向计数被错误奖励；保护值变化及早期关联失败仍需分别验证。

## 上游输入审核

这里的“最终结果”实际是 BPU 的 S3 预测，不是执行单元任意返回的结果。ABTB 曾把同位置识别为条件分支，而 MainBTB 在晚阶段给出直接／间接跳转，这种属性不一致未被父模块直接禁止。

但原测试直接构造 ABTB 向量，并没有让真实 BPU 的首跳裁剪、PHR 和 S3 共同生成整条训练序列。现有证据确认模块更新差异及代码原因；SoC 可达性仍需集成见证，不能把 warm-up 和两次反馈都默认视为合法。详见[输入契约](input-contracts.md)。

## 复现与回归检查

```bash
python3 tests/run_all.py --workers 1 \
  --run-dir results/repro-bpu-bug-02 \
  --select 'tests/utage/testcase/test_dual_source.py::test_two_warm_providers_learn_only_their_executed_instruction_prefix[short-earlier.in-order-holes.later-direct.serial]'
```

测试入口：[双来源前缀训练](../../tests/utage/testcase/test_dual_source.py)、[同位置指令类型变化](../../tests/utage/testcase/test_semantic_reference.py)。修复后至少检查直接跳转、间接跳转，以及它们之前的条件分支仍正常学习这三个场景。

相关功能点：`BPU-UTAGE-025`。早期报告关联 18 个 FAIL，这不是已证明共享一个根因的数量。

证据版本见[目录说明](README.md)。历史定位线索：`d0b3436f5f`。
