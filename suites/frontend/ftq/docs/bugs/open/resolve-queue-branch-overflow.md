```ucv-bug
{
  "id": "RQ-011",
  "title": "ResolveQueue 第 9 条及同拍超容量解析覆盖已记录分支",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "open",
      "evidence": [
        "tests/resolve_queue/test_resolve_overflow.py::test_ninth_branch_resolve_is_dropped_not_overwritten",
        "tests/resolve_queue/test_resolve_overflow.py::test_same_cycle_group_overflow_preserves_existing_branch",
        "docs/spec/verification/evidence/evidence-20261030.md"
      ],
      "note": "2026-10-29 首次复现，两个 strict XFAIL；真实 RTL 溢出写覆盖 slot 7/slot 0。"
    },
    {
      "baseline": "public-a0c2a26cb",
      "status": "open",
      "evidence": [
        "tests/resolve_queue/test_resolve_overflow.py::test_ninth_branch_resolve_is_dropped_not_overwritten",
        "tests/resolve_queue/test_resolve_overflow.py::test_same_cycle_group_overflow_preserves_existing_branch",
        "docs/spec/verification/reports/baseline-adaptation-a0c2a26cb.md"
      ],
      "note": "2026-11-08 复检 ResolveQueue.sv 与旧基线逐字节相同，--runxfail 两条均真实 FAIL；未实施 RTL 修复。"
    }
  ]
}
```

# ResolveQueue 分支槽溢出缺陷（2026-10-29）

## 结论等级

`confirmed-rtl`：在 `public-893e1580b` 和复检的 `public-a0c2a26cb` + DefaultConfig RTL
上，用合法激励对真实 `ResolveQueue` 原生 DUT 复现；期望来自微架构契约（保留已记录的
分支，丢弃超容量报告），不是从 RTL 行为反推。

## 2026-11-08 新基线复检

`public-a0c2a26cb` 的 `ResolveQueue.scala`
（`f6c0858a95c6cf61107d99b95a72afb8d0f033325afc7547dcb4e52dca3bc389`）和生成的
`ResolveQueue.sv`
（`b5387db07bfdfaaf697b64fcccf860783b573d8a827c5a68d32628e562eac012`）与旧基线
逐字节相同，上游没有修复本缺陷。两个 strict XFAIL 原样保留；用
`--runxfail` 重跑仍为两条真实 FAIL，首因均为 `resolve_queue.transactions` 的
`ScoreboardMismatch`：

- `test_ninth_branch_resolve_is_dropped_not_overwritten`：第 9 条报告把 slot 7
  覆盖为 position 9 / target 0xA0000000；
- `test_same_cycle_group_overflow_preserves_existing_branch`：6+3 组把 slot 0
  覆盖为第三条同拍 lane。

结果目录 `results/ftq-a0c2a26cb-closeout-runxfail-20261108/`。未删除、
改宽或转正 XFAIL；修复仍需单独设计变更和回归授权。

## 生产者可达性（2026-11-08 收口）

只读追踪 `ResolveQueue.scala:32-33,86-99,101-155,165-178` 与
`Ftq.scala:402-403,408,420-453`：

| 事实 | 源码/端口依据 |
|---|---|
| 每拍最多 4 个同索引报告 | `backendResolve` 是 `backendParams.BrhCnt` 个 lane（DefaultConfig 生成 `io_backendResolve_0/1/2`，共 3 个），加 1 个 `ifuResolve`；`:99` 拼成同一 `resolve` Vec |
| 同拍多报告可指向同一 entry | `:101-130` 的 `hit/hitPrevious/needNewEntry/enqIndex` 明确支持同 `ftqIdx` 合并；`:132-155` 的写循环不禁止多条报告同一 `enqIndex` |
| 后端过滤不排除条件分支 | `:86-94` 只过滤“正确 direct”和 return；`branch_type=Conditional, mispredict=0` 仍合法 |
| 9 条分支在配置域内 | DefaultConfig BPU meta 有 `CommonHRMeta.position_0..9` 共 10 个位置；64B block 在 32 个 RVC 半字槽内可含 9 个条件分支 |
| 入口可在第 9 条到达时仍驻留 | `Ftq.scala:408` 的 `bpuTrain.ready` 在 `trainCache.valid` 且 BPU 未 fire 时为 0；`:420-453` 的 trainCache 保持入口；`ResolveQueue.scala:165-178` 只在当前拍有同索引报告时抑制出队 |
| 写槽无容量守卫 | `:139-140` 的 `firstEmpty + PopCount(hitPrevious(i))` 直接作为动态下标；`indexWhere` 无空槽返回 8，未与 `ResolveEntryBranchNumber=8` 比较 |

因此，单条跨拍的第 9 个报告和“6 条驻留 + 同拍 3 条”的超量组都由真实 IFU/后端
生产者可达；不是端口级任意压力。**结论：`confirmed-rtl`，可达。**

### 最小复现

```sh
cd suites/frontend/ftq
PYTHONPATH=/home/xyl/ucv4xs /home/xyl/ucv4xs/.venv/bin/python -m pytest -q \
  --runxfail tests/resolve_queue/test_resolve_overflow.py -rxX
```

- `test_ninth_branch_resolve_is_dropped_not_overwritten`：
  `branches[7].position` 期望 8、实际 9；target 期望 `0x9000_0800`、实际
  `0xA000_0000`。
- `test_same_cycle_group_overflow_preserves_existing_branch`：
  `branches[0].position` 期望 1、实际 9；target 期望 `0x9000_0100`、实际
  `0xA000_0000`。

两次首因都是 `resolve_queue.transactions` 的 `ScoreboardMismatch`，不是 setup、
清理或覆盖失败。顶层另有 `test_ftq_ifu_backend_merge.py` 证明“3 backend + 1 IFU”
四源同拍可创建同一 entry；顶层第 9 条报告的完整复现受 BPU 训练背压驱动，本轮没有
新增第三个 XFAIL，只保留 leaf 最小复现。

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

`suites/frontend/bpu/XiangShan/src/main/scala/xiangshan/frontend/ftq/ResolveQueue.scala:139-140`
（2026-10-29 文档记为 137-138；文件字节未变，行号按当前检出更正）：

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
  同拍多条，可能丢失最早或最晚的分支，首误预测掩码和后续 BPU 训练随之错误。
  写循环还无条件写 `startPc/debug_source`；同一 entry 的正常报告应给出同一起点，但缺陷
  路径不保证这一点，属于同一越界写的影响面。
- 触发前提：同一 FTQ entry 的分支解析报告超过 8 条。DefaultConfig 的 BPU meta 容量为 10，
  且后端过滤仍保留条件分支，因此不是端口级任意压力，而是配置允许的输入范围。
- 顶层通过实例化同一个 ResolveQueue 继承该行为；收口的四源用例证明每拍 4 个同索引报告
  合法，顶层随机模型仍限制在 8 条容量内以覆盖其余语义。没有新增第三个 XFAIL。
- 未修改 RTL，也未放宽/删除检查；修复需要单独的设计变更与回归授权。

## 建议修复与下一动作（仅文档，未实施）

在 `branchSlot` 写入前增加宽度安全的容量守卫，例如先算
`val slot = firstEmpty + PopCount(hitPrevious(i))`，仅在
`slot < ResolveEntryBranchNumber.U` 时写槽，否则丢弃该报告；可选增加
`resolveQueueBranchOverflow` 性能事件。不要把 `firstEmpty` 的 8 直接交给动态
`Vec` 下标。修复后：

1. 重跑两个 strict XFAIL，预期转为 XPASS，再删除/改写为正向契约测试；
2. 重跑 `resolve_queue` 全量、`ftq` 顶层相关用例与覆盖率；
3. 在报告中把该缺陷状态从“未修复”改为“已修复并复验”，保留原失败证据；
4. 由用户/设计负责人决定是否实施并安排回归，不由验证侧改 RTL。
