# BPU-BUG-01：MainBTB 把一条分支的反馈用于另一条分支的方向计数

两条不同地址的分支共用一组存储位置，并且在各自取指块内的偏移相同。其中一条没有命中 MainBTB，但它的训练反馈仍改变了另一条已保存分支的方向计数，最终把后者从“预测跳转”改成“预测不跳转”。

状态：已确认 RTL 问题。2026-10-22 重跑后，同位置、不同 tag 的场景失败，不同位置对照通过；首个差异与方向更新漏掉地址命中约束一致。尚未修改 RTL 或验证修复效果。

## 怎样触发

1. 先让分支 A 留在 MainBTB 中，方向计数为 2，预测会跳转。
2. 查询另一地址的分支 B。B 与 A 使用相同组、相同块内偏移，但地址标签不同，因此不能算命中 A。
3. 用 B 那次查询的真实预测元数据提交一条不跳转反馈。
4. 再查询 A，检查 A 的方向计数和预测方向。

预期依据：B 的反馈可以触发 B 自己的学习或分配，但不能仅因块内偏移相同，就把 A 当成此次反馈命中的条件分支来减计数。

## 已观察到的结果

代表用例：`test_unhit_feedback_preserves_foreign_tag_direction[same-position]`。

| 检查项 | 预期 | 实际 |
|---|---:|---:|
| A 的方向计数，日志字段 `1.counter` | 2，保持不变 | 1 |
| A 的预测方向，`1.taken` | 1，跳转 | 0，不跳转 |

这里的 `1` 是该次观测中的存储槽编号，不是功能要求必须使用的槽位。问题是“反馈属于谁”，而不是某一条物理路的计数有没有变化。

## 代码线索与待确认项

[MainBtbAlignBank.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/mbtb/MainBtbAlignBank.scala) 的方向计数更新条件检查了“条件分支”和“位置相同”，但问题路径没有同时要求 `meta.rawHit`。后者表示预测时地址确实命中了该表项。

同文件的其他更新路径使用了包含地址命中的判定。本次重跑确认：未命中的反馈只因位置相同，就令已保存分支的计数从 2 减为 1；改变位置后不会误更新。当前 DUT 中该方向路径确实没有地址命中门控。

若当前源码已有 `meta.rawHit` 检查，还需核对它是否进入了待验证的 DUT 构建。归档失败与当前版本的修复状态是两件事，不能只看源码片段就宣布问题已解决。

## 上游输入审核

这是 FTQ 的慢训练，不是 S3 fastTrain。实际漏预测的条件分支仍可由后端送来；FTQ 不会因 MainBTB 原预测 `rawHit=0` 就丢弃该反馈，因此不能用“上游只训练命中的记录”排除本例。

仍须满足 FTQ 的首误预测掩码和重定向年龄规则。当前结论是这种输入形态没有被上游过滤，不是已经运行过包含 FTQ 的整核反例。依据与统一判定边界见[输入契约](input-contracts.md)。

## 复现与回归检查

```bash
python3 tests/run_all.py --workers 1 \
  --run-dir results/repro-bpu-bug-01 \
  --select 'tests/mbtb/testcase/test_semantic_reference.py::test_unhit_feedback_preserves_foreign_tag_direction[same-position]'
```

[测试入口](../../tests/mbtb/testcase/test_semantic_reference.py)还有 `other-position-control` 对照：地址和位置都不匹配时，不应误改 A。修复后也应检查正常命中时的方向训练没有被禁止。

相关功能点：`BPU-MBTB-027`。早期报告关联 28 个 FAIL，不能在未重跑前把其他模块的级联差异全部归到本条。

证据版本与阅读方法见[目录说明](README.md)。历史定位线索：`d25652d597`，不是已证实的缺陷引入提交。
