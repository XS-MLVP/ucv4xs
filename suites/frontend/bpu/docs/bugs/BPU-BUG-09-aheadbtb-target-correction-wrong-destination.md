# BPU-BUG-09：AheadBTB 把不同分支的待写纠正合并，丢掉较早更新

同一取指块内两条不同位置的间接跳转，分别有自己的预测记录。读请求占用 SRAM 时，两次目标纠正都需要暂存在写缓冲。当前缓冲把它们当成同一项更新，后来的请求覆盖前一个，导致前一条分支仍返回旧目标。

状态：模块缓冲覆盖及缺失写回已定位。但两份真实 S3 预测及读压力、flush、历史的共同可达性尚未证明，不能只凭该单元压力序列认定 SoC 缺陷。

## 怎样触发

1. 在同一取指块建立 A、B 两条记录，位置分别为 3、9。
2. 持续查询，暂时阻止单端口 SRAM 写入。
3. 分别纠正 A、B 的目标，保持两次更新都处于待写状态。
4. 停止查询，等待缓冲排空，再查询 A、B。

两份反馈是独立的模块级训练输入，携带真实预测元数据；不是声称两条间接跳转在同次执行中都跳转。完整前端能否产生完全相同的序列，需要另外验证。

## 直接观测

2026-10-22 的 memory-direct 复核，A 位于 way 0，B 位于 way 2；两者 bank、set 和 tag 相同。

| tick | 事件 | 同一个缓冲槽的内容 |
|---|---|---|
| 184 | 接收 A 的纠正 | A：位置 3、way 0、目标低位 2496 |
| 188 | 接收 B 的纠正，A 尚未写出 | 被替换为 B：位置 9、way 2、目标低位 2816 |
| 194 | 解除查询压力，实际写回 | 只有 B 写出，没有 A |

tick 是仿真事件编号。缓冲中其他槽没有为 A 保留待写副本，因此排空后不能再补上 A。

最终 A 的 `0.target` 预期 `0x400009C0`（1073744320），实际仍是旧目标 `0x40000980`（1073744256）。B 已得到新目标。丢失发生在缓冲合并阶段，不是检查读回太早。

## 根因在哪里

[AheadBtbBank.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/abtb/AheadBtbBank.scala) 将请求交给通用 WriteBuffer。[BankWriteReq](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/abtb/Bundles.scala) 携带 `setIdx`、`wayIdx` 和表项内容，但提供给缓冲比较的 `tag` 只是 `entry.tag`。

[WriteBuffer.scala](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/WriteBuffer.scala) 只按 `setIdx + tag` 判断命中，没有区分不同 way。命中尚未写出的记录时，直接用整个新请求覆盖旧请求。A、B 的位置不同、way 不同，但该比较仍认为它们是同一个更新对象。

因此本例不是容量耗尽时的合法替换，而是**把不同写入目的地误合并成同一个**。

修复需保证不同目的地能分别保留待写更新；同时应检查未命中时优先复用同 set 槽位的选择逻辑，不能只给命中比较多加一个字段就认为所有路径都正确。

## 为什么撤回“缺少 tag 检查”

预测阶段已经在 [getHitMask](../../XiangShan/src/main/scala/xiangshan/frontend/bpu/abtb/Bundles.scala) 中比较 `e.valid && e.tag === getTag(startPc)`，结果保存为元数据的 `e.hit`，训练时再使用它。

旧报告把“训练处没有再次写出 tag 比较”误认作完全没检查 tag。真正的问题在更后的写缓冲：已有 tag 比较，但 tag 无法区分同一取指块内的不同分支。

## 上游输入审核

两次纠正实际必须来自两个独立的 S3 预测实例，带各自对齐的 ABTB 元数据；S3 override 还会冲刷年轻流水，PHR 与查询地址共同决定 bank 读压力。

原单元用例直接复用保存的元数据发送两次纠正，没有证明这些上游关系。元数据位值相同本身不非法，多个真实原预测也可能相同；缺少的是两个真实实例、正确 flush 时序和持续读压力的共同见证。

所以缓冲覆盖根因已经定位，但它仍不能独自证明这条完整压力序列可由 SoC 生成。详见[输入契约](input-contracts.md)。

## 复现与对照

```bash
python3 tests/run_all.py --workers 1 \
  --run-dir results/repro-bpu-bug-09 \
  --select 'tests/abtb/testcase/test_semantic_reference.py::test_pending_target_corrections_preserve_destination_ownership[distinct-destinations]'
```

[测试入口](../../tests/abtb/testcase/test_semantic_reference.py)的复核结果：

| 场景 | 结果 |
|---|---|
| 两条不同分支，前一次写完再提交下一次 | PASS |
| 同一条分支，两次纠正同时待写，保留最新目标 | PASS |
| 两条不同分支，两次纠正同时待写 | FAIL |

相关功能点：`BPU-ABTB-053`。复核方法与版本说明见[目录说明](README.md)。
