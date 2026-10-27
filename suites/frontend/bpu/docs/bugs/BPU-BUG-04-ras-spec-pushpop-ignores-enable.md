# BPU-BUG-04：RAS 禁用时仍处理推测调用

RAS 用栈保存函数调用后的返回地址。按照当前检查约定，模块禁用时不应接受新的推测调用、返回操作。但归档用例中，禁用状态下的一次调用仍改变了被检查的栈状态。

本条讨论的是**禁用时是否更新栈**，不是“返回并调用”这种组合操作该怎样处理。

状态：已确认 RTL 问题。2026-10-22 的最小复核中，禁用调用、禁用返回均改变了栈状态；启用时的普通调用、返回对照通过。尚未修改 RTL。

## 怎样触发

1. 复位 RAS，使栈处于空状态。
2. 保持 `enable=0`，同时在推测输入上提供有效的调用操作。
3. 比较操作前后的栈状态。

预期是栈不接受这次推测调用。是否向外提供可用返回地址是另一个问题，MicroRAS 的输出门控见 [05](BPU-BUG-05-microras-ignores-enable.md)。

## 已观察到的结果

来自 `test_ras_functional_coverage_closes_defined_bins` 中的禁用调用步骤：

| 检查项 | 预期 | 实际 |
|---|---:|---:|
| 栈状态摘要 `calls` | 0 | 1 |
| 栈状态摘要 `group` | 0 | 1 |

这两个字段是检查器用于比较栈状态的摘要，不是 pytest 的用例统计。它们从 0 变成 1，说明禁用调用并未像参考约定要求的那样被忽略；不能由字段名进一步推断所有提交态寄存器都受影响。

## 代码线索与待确认项

[Ras.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/Ras.scala) 的推测路径如下：

```scala
stack.spec.pushValid := specPush && !stackNearOverflow
stack.spec.popValid  := specPop && !stackNearOverflow
stack.spec.fire      := io.specIn.valid && io.enable
```

`specPush`、`specPop` 由推测输入有效及操作类型生成，本身没有要求 `enable`。虽然 `fire` 使用了 enable，但 [RasStack.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/ras/RasStack.scala) 的推测栈更新直接受 `pushValid`、`popValid` 控制。因此“fire 已经门控”不能保证栈不变。

本次另用非空栈检查禁用返回：`group` 预期保留为 1，实际变成 0，栈顶也被弹出。因此问题同时影响入栈、出栈，不只是一种操作。修复时还应核对栈写入、旁路和延迟更新是否使用同一个操作接受条件。

## 不应混在本条中的失败

早期报告把 5 个 FAIL 放在一起，其中 4 个属于“返回并调用”：同一条指令既返回、又发起新调用。它们涉及栈顶替换、恢复或提交时的组合操作语义，不能用禁用门控解释。

例如 `test_speculative_return_and_call_replaces_only_the_youngest_frame` 检查的是启用状态下的栈顶替换。本次已分别重跑这 4 个失败，并确认组合操作译码遗漏，现单列为 [10](BPU-BUG-10-return-and-call-treated-as-no-action.md)。本条修复不能替代组合操作修复。

## 上游输入审核

已在完整 BPU DUT 中确认：保持 `rasEnable=0`、MainBTB 启用，BPU 仍自然产生 `specIn.valid=1, rasAction=Push`。这与生产连接 `specIn.valid := s3_fire` 一致，父模块没有替 RAS 屏蔽禁用期间的调用。

CSR 中 RAS_ENABLE 是软件可写字段，因此不是只能靠直接驱动子模块得到的配置。这个见证证明输入在 BPU 边界可达，不代表已执行整核 CSR 程序；禁用期间应该冻结哪些状态仍应按接口约定判断，而不是只凭 enable 名字。详见[输入契约](input-contracts.md)。

## 复现与回归检查

```bash
python3 tests/run_all.py --workers 1 \
  --run-dir results/repro-bpu-bug-04 \
  --select 'tests/ras/testcase/test_coverage.py::test_ras_functional_coverage_closes_defined_bins'
```

[测试入口](../../tests/ras/testcase/test_coverage.py)。它包含多个功能步骤，并非只检查禁用门控；阅读归档失败时，应定位到上述禁用调用步骤。后续回归需分别检查禁用调用、禁用返回及重新启用后的正常操作。

证据版本见[目录说明](README.md)。历史定位线索：`636a9c4b5f`；`37ce1b50b5` 可用于追踪 fire 门控的后续变化。
