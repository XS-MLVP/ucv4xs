# BPU-BUG-08：MicroBTB 因一次不跳转反馈重新给出跳转预测

MicroBTB 会降低反复预测无用的记录的可用程度，直到不再用它提供预测。测试先让一条记录达到这个状态，再提供一次“不跳转”反馈；预期它继续不可用，实际却重新给出了跳转预测。

这里的“旧记录失效”指不再用于预测，不是保证 tag、目标地址等存储位都已经清零。

状态：模块差异与重新初始化路径已观察到，但原 fastTrain 字段组合违反 BPU 生产者约束。合法字段变体仍有差异，完整事件序列的 SoC 可达性待证。尚未修改 RTL 或原用例判定。

## 怎样触发

1. 对同一条条件分支提供一次跳转反馈，建立记录。
2. 连续提供 3 次不跳转反馈，让该记录降到不再用于预测的状态。
3. 紧接着再提供第 4 次不跳转反馈，其携带的目标字段与最初目标不同。
4. 等这些连续训练处理后，再查询同一分支。

核心要求：不跳转反馈不能被当成“重新学习一条会跳转的记录”。这不禁止不跳转反馈正常降低一条仍有效记录的计数。

## 已观察到的结果

用例：`test_fallthrough_does_not_revive_a_dead_entry_with_its_target`。

| 检查项 | 预期 | 实际 |
|---|---|---|
| 预测是否有效，`valid` | 0 | 1 |
| 预测方向，`taken` | 无有效预测，不比较 | 1，跳转 |
| 预测目标，`target` | 无有效预测，不比较 | `0x80003650`（2147497552） |

失败不只是内部计数和模型不同：模块对外确实输出了一条本不应有效的跳转预测。日志中的 `MISSING` 表示期望结果没有该有效负载，不是要求目标地址必须为某个特殊值。

## 代码线索与待确认项

[MicroBtb.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/ubtb/MicroBtb.scala) 的 `initEntryIfNotUseful` 在记录已经无用时，会把可用程度重新置为强正值，并复制反馈中的位置、类型和目标。

命中路径在目标或属性不一致、或者实际不跳转时，都可能调用这个函数。它只看记录是否已经无用，没有同时要求实际跳转，因而把不跳转反馈也当作重新分配的理由。

本次观察到相邻反馈的更新计数依次为 `3 → 2 → 1 → 0 → 3`。最后一条反馈的 `t1_actualTaken=0`、`t1_hitNotUseful=1`，但 `t1_updatedEntry_usefulCnt_value=3`；说明已经归零的状态到达了该级，却仍被重新初始化，不是老化状态没有前递到达。修复时必须保留正常的“再次跳转后恢复学习”。

## 上游输入审核：原 fastTrain 字段组合不合法

真实 BPU 的不跳转 fastTrain 来自 FallThroughPredictor：类型为 None，位置为取指块／页结束位置，目标为顺序地址。原用例却保留条件分支类型、旧位置并改变分支目标，所以它不是合法的 S3 fastTrain 组合，不能直接作为 SoC 缺陷证据。

补充把字段改成当前配置的真实形式：`taken=0, kind=0, position=15, target=PC+32字节`，同样的连续单元训练仍产生 `valid=1, taken=1, kind=0` 的差异。

但“合法字段”仍不等于“合法事件序列”：真实 S3 预测、override/flush、下一 PC，以及执行纠正与快训练仲裁，可能限制连续同 PC 的更新。该变体尚未由真实 BPU 流水线自然生成。MicroBTB 的慢执行纠正是另一入口，也不能拿其合法字段替 fastTrain 背书。

因此保留模块差异与重新初始化机理，撤回原用例已足以证明正常 SoC 可触发的定性。详见[输入契约](input-contracts.md)。

## 复现与回归检查

```bash
python3 tests/run_all.py --workers 1 \
  --run-dir results/repro-bpu-bug-08 \
  --select 'tests/ubtb/testcase/test_contiguous_training.py::test_fallthrough_does_not_revive_a_dead_entry_with_its_target'
```

[测试入口](../../tests/ubtb/testcase/test_contiguous_training.py)。修复后应同时检查连续不跳转不恢复、真实跳转能够恢复，以及目标变化时的正常重新学习。

相关功能点：`BPU-UBTB-011`。早期报告关联 2 个 FAIL；另一个是 [test_semantic_reference.py](../../tests/ubtb/testcase/test_semantic_reference.py) 中的连续反馈对照。

证据版本见[目录说明](README.md)。历史定位线索：`4d9d83b11a`。
