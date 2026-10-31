# ResolveQueue 分支槽溢出缺陷（2026-10-29）

## 结论等级

`confirmed-rtl`：在当前 `public-893e1580b` + DefaultConfig RTL 上，用合法激励对真实
`ResolveQueue` 原生 DUT 复现；期望来自微架构契约（保留已记录的分支，丢弃超容量报告），
不是从 RTL 行为反推。

## 观察

一个 FTQ entry 的 `ResolveEntryBranchNumber` 为 8，但 DefaultConfig 的 BPU meta 可描述
10 个 BTB 结果位置（生成端口 `CommonHRMeta.position_0..9`；公式
`NumBtbResultEntries = (NumWay + 1) * NumBtbAlignBanks`）。因此一个 64B fetch block 可以
合法产生第 9、10 个分支解析。

已复现两种表现：

1. 已有 8 条报告后再来 1 条：新报告的 `cfiPosition`/target 覆盖 slot 7，原第 8 条丢失。
2. 已有 6 条报告，同拍到达 3 条：前两条填入 slot 6/7，第三条回绕覆盖 slot 0，原第 1 条丢失。

实测（2026-10-29 首次复现，2026-10-30 在 `results/ftq-final-20261030` 继续以 strict XFAIL 保留）：

```text
after 8:  [1,2,3,4,5,6,7,8]
after 9:  [1,2,3,4,5,6,7,9]        # target of slot 7 replaced by 0xA0000000
6 + 3:    [9,2,3,4,5,6,7,8]        # slot 0 replaced by the third lane
```

## 根因

`suites/frontend/bpu/XiangShan/src/main/scala/xiangshan/frontend/ftq/ResolveQueue.scala:137-138`：

```scala
val firstEmpty = mem(enqIndex(i)).bits.branches.indexWhere(!_.valid)
val branchSlot = mem(enqIndex(i)).bits.branches(firstEmpty + PopCount(hitPrevious(i)))
```

`indexWhere` 在无空槽时返回 8；`firstEmpty + PopCount(hitPrevious)` 没有与
`ResolveEntryBranchNumber` 比较。动态 `Vec` 下标被截断/回绕，于是越界写落到一个仍有效的
槽位，`branchSlot.valid := true.B` 还把该槽重新标记为有效，覆盖已记录分支。

这不是测试台对未定义字段的比较：被比较的 slot 0/7 在覆盖前均为 `valid=1` 且属于契约内的
8 条分支报告。

## 复现

```sh
cd suites/frontend/ftq
PYTHONPATH=. /home/xyl/ucv4xs/.venv-uc-toffee/bin/python \
  -m pytest -q tests/resolve_queue/test_resolve_overflow.py -rxX
```

- `tests/resolve_queue/test_resolve_overflow.py::test_ninth_branch_resolve_is_dropped_not_overwritten`
- `tests/resolve_queue/test_resolve_overflow.py::test_same_cycle_group_overflow_preserves_existing_branch`

两者均为 `strict XFAIL` + `rtl_defect`：当前 RTL 违反契约，测试保留真实失败；若未来 RTL
修复，strict XPASS 会要求重新评估，而不是静默通过。

## 影响与边界

- 影响：一次 FTQ entry 的 BPU 训练分支集合可能被篡改；具体表现取决于溢出发生在单条还是
  同拍多条，可能丢失最早或最晚的分支。
- 触发前提：同一 FTQ entry 的分支解析报告超过 8 条。DefaultConfig 的 BPU meta 容量为 10，
  因此不是端口级任意压力，而是配置允许的输入范围。
- 未把 `resolve_queue` 的这项失败归因于 FTQ 顶层：顶层通过 ResolveQueue 继承同一行为；
  当前顶层随机模型测试主动限制在 8 条容量内，以覆盖其余语义。
- 未修改 RTL，也未放宽/删除检查；修复需要单独的设计变更与回归授权。

## 建议修复与下一动作

在 `branchSlot` 写入前增加容量守卫，例如仅在
`firstEmpty + PopCount(hitPrevious(i)) < ResolveEntryBranchNumber` 时写槽，否则丢弃该报告
（并可用 perf event 计数溢出）。修复后：

1. 重跑两个 strict XFAIL，预期转为 XPASS，删除/改写为正向契约测试；
2. 重跑 `resolve_queue` 全量、`ftq` 顶层相关用例与覆盖率；
3. 在报告中把该缺陷状态从“未修复”改为“已修复并复验”，保留原失败证据。
