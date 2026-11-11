# CF-DEQUEUE-PIPELINE-NO-RESET：短复位后 CounterFilter 出队流水可能永久偏移

状态：**RTL 行为保留，上游未修复；系统内良性但仿真场景需要规避**。该条不是当前功能
用例的 FAIL，目录保持 open 是因为修复/复验没有完成，而不是宣称真实系统会出错。
当前默认基线 `public-a0c2a26cb` 尚未重新构建或回归，`versions` 记该基线为 `unverified`，
不把旧结论直接当成当前复现。

## 问题

CounterFilter 的 3 级出队计数流水 `last3CycleAlloc_REG/_REG_1/_REG_2` 位于无复位的
`always @(posedge clock)` 块中，只有末级 `last3CycleAlloc` 被复位。短复位后这些寄存器
保留复位前或随机的值；复位释放后的第一个时钟沿会按旧值出队，把 `deqPtr` 推过
`enqPtr`，FIFO 指针从此永久偏移。

## 独立预期

复位应清空所有影响 FIFO 指针的流水状态；复位释放后第一次入队/查询不能因为复位前的
残留计数而错误出队。若设计有意不复位该流水，则真实系统的复位宽度和发射前等待必须
提供等价保证，并记录该前提。

## 复现与对照

多 seed 扫描发现：seed=1 时同一份确定性用例全过；seed=2 时
[test_single_entry_lifetime](../../../tests/counter_filter/test_counter_filter.py)::test_single_entry_lifetime、[test_query_ports_are_independent](../../../tests/counter_filter/test_counter_filter.py)::test_query_ports_are_independent、
[test_index_and_way_full_range](../../../tests/counter_filter/test_counter_filter.py)::test_index_and_way_full_range、[test_capacity_full_and_pointer_wrap](../../../tests/counter_filter/test_counter_filter.py)::test_capacity_full_and_pointer_wrap 全部失败，报
query 期望命中而 DUT 不命中（occupancy=1）。相同激励只差 Verilator 随机初值，定位
到唯一无复位寄存器组（`rtl/counter_filter/CounterFilter.sv` 的
`last3CycleAlloc_REG/_REG_1/_REG_2`）。把复位保持 5 拍（期间 `ld_valid=0`）后三个寄存器
被清零，seed 1/2/3/4 全部通过。

## 根因、范围与处理

- 根因：无复位流水在短复位后保留旧计数，首拍 dequeue 使指针跨过 enqueue。
- 范围：对 DCache 功能无影响——真实系统复位至少持续数百拍，且 DCache 复位后还要等
  256 拍 SRAM 清扫才会发出 load，流水早已清零。只影响“复位后立刻打流量”的仿真。
- 当前处理：本工程 `counter_filter` 环境的 `reset()` 保持复位 5 拍，并在功能点和报告
  中记录该前提；没有修改 RTL。
- 待上游决定是否给这三个寄存器加复位。修复后应移除本环境的加长复位前提，并保留多
  seed 对照。

## 证据

- [P0 收口报告第 2.4 节](../../spec/verification/evidence/p0-closure-20261026.md)
- 功能点 [CF-FP-001](../../spec/design/functional-points-counter-filter.md)
- [counter_filter/env.py](../../../counter_filter/env.py) 的 reset 注释；[manifest/known-issues.json](../../../manifest/known-issues.json) 同名条目

```ucv-bug
{
  "id": "CF-DEQUEUE-PIPELINE-NO-RESET",
  "title": "短复位后 CounterFilter 出队流水可能永久偏移 FIFO 指针",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "open",
      "evidence": [
        "suites/memblock/dcache/docs/spec/verification/evidence/p0-closure-20261026.md",
        "suites/memblock/dcache/tests/counter_filter/test_counter_filter.py",
        "suites/memblock/dcache/counter_filter/env.py"
      ],
      "note": "多 seed 定位；环境以 5 拍复位规避，RTL 未修改，上游修复未确认"
    },
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "suites/memblock/dcache/README.md"
      ],
      "note": "当前默认基线尚未重新 prepare/build/run，不能沿用历史结论"
    }
  ]
}
```
