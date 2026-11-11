# FTQ 新基线适配与回归（public-a0c2a26cb，2026-11-08）

## 结论边界

本页只覆盖 FTQ / DefaultConfig / `public-a0c2a26cb`
（`a0c2a26cbe3c862175174bad03a1a23c406315ed`）。旧 `public-893e1580b` 的
905 PASS / 2 XFAIL 结果和 2026-10-30 覆盖数字保持原义，不与本轮拼接。
硬件仍未签核；本轮的 XFAIL 是真实 RTL 缺陷，不计入 PASS。

## 源码、构建与工具身份

| 项目 | 值 |
|---|---|
| 基线 | `public-a0c2a26cb` / DefaultConfig |
| 源码 checkout | `.cache/sources/f3ac6022d07c5c05d28869ac811f91038f9103677796dd6f051bd1981408be9b` |
| `ResolveQueue.sv` | `b5387db07bfdfaaf697b64fcccf860783b573d8a827c5a68d32628e562eac012`（与旧基线相同） |
| `CommitQueue.sv` | `1f843a42e1cc3dfaf5adcfc739be59bd11c272210fee4b5a0cfa125424793c5d`（与旧基线相同） |
| `Ftq.sv` | `88544217a5d3b3893100984828019fa65386345c0f0e45ff26c3574526e13f4f`（旧 `abbc7914…`） |
| `PrefetchQueue.sv` | `bfab73b506d92d275d792488641be029fc5cf61750fc7b12c22ca4cf4faf2651`（新进入闭包） |
| `ResolveQueue.scala` | `f6c0858a95c6cf61107d99b95a72afb8d0f033325afc7547dcb4e52dca3bc389`（相同） |
| `CommitQueue.scala` | `de22d2ea81b56e13c6aed64e92b9f4e069b9f8c47da1bee04b709862eb5bf261`（相同） |
| resolve_queue 构建 | `d1f653f7094a28496750694db159f8769396f904ba8d51d5a944741dca2e573e` |
| commit_queue 构建 | `0cdc47520b14a18b98dfa280408f94007a8a163fe6676325caa191066a20d5c1` |
| ftq 构建 | `d181e4c48a0df7cd40bbcc545780ed7484f8662fd3bfb35922f07f60151aca28` |
| toffee | `f57150021791535d4b2fd01056c106f0cad53177`（uc-toffee） |
| picker | `4dd442c4a80c92549381e417c608836e3b78a8e9` |
| xcomm | `2e4a4a99293360c2a642025000c6948b24cf8e88` / ABI 3 / coverage protocol 5 |
| Verilator | 5.052 |

构建命令：

```sh
.venv/bin/ucv prepare ftq --require-unified-baseline
.venv/bin/ucv build ftq --require-unified-baseline
```

输出为 3/3 `BUILT + SMOKE PASS`。构建日志与完整产物哈希见
[机器记录](../../../../../../../docs/history/ftq-closeout-a0c2a26cb-20261108.json)
（构建身份仍见[首轮记录](../../../../../../../docs/history/ftq-baseline-a0c2a26cb-20261108.json)）。

## 相对旧基线的 RTL/Scala 变化

基线区间 `893e1580b..a0c2a26cb` 中触及 FTQ 的上游提交只有两个：

1. `4b9f938b7`（#6691，enhanced iprefetch part 1）：新增 `PrefetchQueue.scala`、
   `PrefetchQueuePtr.scala` 和 `FtqPrefetchQueueParameters`；`Ftq` 增加 3 个
   `softPrefetch` 输入并实例化 8 槽预取队列；`FtqPrefetchReq` 增加 `source`；
   `TwoFetch`/`Bundles` 增加 `PrefetchSource`。
2. `b716aade5`（#6751，carry true PC guard bit）：`FrontendRedirect.pc` 从 50 位
   变为 51 位 `GuardedVAddrBits`，`IfuRedirectReceiver` 显式保留 guard 位；FTQ 的
   cfiPc 半字投影由 49 位变为 50 位。

`ResolveQueue.scala`、`CommitQueue.scala` 及对应生成 `.sv` 逐字节不变；
两个 leaf 的功能点、oracle、槽位/容量/身份合同继续成立。Ftq 顶层新增行为：

- 软件预取队列容量 8，但保留 1 槽，实际最多 7 项；load unit 无 ready 回压，
  超出容量或超出端口的请求静默丢弃。
- 选择优先级：FDIP 双发 > FDIP+队列混合双发 > 队列单发（当 FDIP 距离 > 2 或
  FDIP 不可用）> FDIP 单发。队列单发不推进 `pfPtr`；混合双发推进 1；
  FDIP 双发推进 2。
- 队列请求的 `source=Sw`（1），`startVAddr` 为 `PcInit(vaddr).signGuard` 的
  半字坐标，`nextLineVAddr`/`isCrossLine`/`vSetIdx[1]` 为 0；输出 `ftqIdx`
  仍是当前 `pfPtr` 标签，不是软件预取输入 UID。
- 前置/后置两阶段采样、输入 UID、取消与有界收尾合同未因上游变化放宽；新增的
  队列输入身份在入队时建立，比较器不从输出或内部存储反推。

## ABI 适配

`ftq/bundle/abi.py` 的固定 ABI 从 433 输入/468 输出更新为
**439 输入/470 输出**：

- 新增 `io_softPrefetch_{0,1,2}_valid` 和 `bits_vaddr[49:0]`（6 个输入）；
- 新增 `io_toICache_toPrefetch_bits_req_{0,1}_source_value`（2 个输出）；
- `io_fromBackend_redirect_bits_pc`、`io_fromIfu_wbRedirect_bits_pc` 宽度 50→51；
- `io_toBpu_redirect_bits_cfiPc_addr` 宽度 49→50。

metadata 输入仍为 329 项；未增加豁免。`FtqInput` 增加 3 个 `SoftPrefetch`
输入槽，checker 的 `PrefetchStore` 仅在容量允许时入队；`FtqInputPorts`、
`FtqInputDriver` 和 `PrefetchRequest`/`PrefetchLane` 增加 source 字段。

## 回归与逐 nodeid 对账

权威完整回归（收口后）：

```sh
.venv/bin/ucv run ftq --workers 2 --seed 2 --require-unified-baseline \
  --output results/ftq-a0c2a26cb-closeout-seed2b-20261108 -- tests
```

- **931 PASS / 2 XFAIL / 0 FAIL / 0 ERROR**（933 nodeid）；
- 源码 `4462a4b8…` 运行前后一致；manifest `committed`、`coverage_complete=true`、
  `gaps=[]`；
- 结果目录 `results/ftq-a0c2a26cb-closeout-seed2b-20261108`。

与旧权威 `results/ucv-goal-ftq-frontend-integrated-v4-20261102`（907 nodeid，
905 PASS/2 XFAIL）逐 nodeid 对账：

- 删除 **0**；判定变化 **0**；旧 905 PASS 和 2 XFAIL 全部保留；
- 新增 **26** 个 nodeid，全部 PASS：
  - 前轮 17 项：4 个 prefetch source 字段比较、2 个 redirect PC guard 控制、
    11 个软件预取队列原生用例；
  - 收口 9 项：4 个 IFU/backend 同索引合并用例（1 个四源宽度控制 + 3 个 lane
    参数化）和 5 个队列覆盖用例（8 槽/回绕、Fdip/Sw source、resolve 并发、
    commit 并发、redirect/flush 交互）。

同源码 seed1 完整回归
`results/ftq-a0c2a26cb-closeout-seed1-20261108` 同为 **931 PASS/2 XFAIL**，
933 个 nodeid 与 seed2 逐项判定一致；旧 `results/ucv-goal-ftq-*` 的历史目录不重标。
nodeid 分母从 924 增加到 933，分支分母仍为 1722（ftq）/734/520；新增用例只增加
命中，不改变分支分母。

## 两个容量 XFAIL 的复核与 RQ-011 可达性

`tests/resolve_queue/test_resolve_overflow.py` 的两个 strict XFAIL 在新基线上
仍是真实硬件失败。`--runxfail` 证据见
`results/ftq-a0c2a26cb-closeout-runxfail-20261108/`：

- `test_ninth_branch_resolve_is_dropped_not_overwritten`：第 9 条报告覆盖 slot 7
  （`branches[7]` position 8→9，target `0x9000_0800`→`0xA000_0000`）；
- `test_same_cycle_group_overflow_preserves_existing_branch`：6+3 同拍覆盖 slot 0
  （`branches[0]` position 1→9，target `0x9000_0100`→`0xA000_0000`）。

两次首因均为 `resolve_queue.transactions` 的 `ScoreboardMismatch`，不是 setup、
清理或覆盖失败。`ResolveQueue.sv`/`.scala` 与旧基线字节相同，缺陷状态仍是
`confirmed-rtl`；未删除 XFAIL、未改宽容量、未转正。

### 只读可达性追踪（2026-11-08）

从 `ResolveQueue.scala:32-33,86-99,101-155,165-178` 与
`Ftq.scala:402-403,408,420-453` 追踪：

1. `ResolveQueue` 的输入是 `backendParams.BrhCnt` 个 backend lane 加 1 个 IFU
   resolve；DefaultConfig 的生成端口为 `io_backendResolve_0/1/2`，即每拍最多
   **4** 个报告（3 backend + 1 IFU）。`:99` 把它们拼成同一个 `resolve` Vec，
   `:116-130` 的 `needNewEntry/enqIndex` 和 `:132-155` 的写循环都不限制多条
   报告指向同一 `ftqIdx`；`hitPrevious` 正是为同索引合并准备的。
2. `:86-94` 的后端过滤只去掉“正确 direct”和 return；条件分支即使
   `mispredict=0` 仍合法。DefaultConfig 的 BPU meta 有 10 个位置
   （`CommonHRMeta.position_0..9`），一个 64B fetch block 可以合法产生 9 个
   条件分支解析；这些报告可以分多拍到达，也可以在已有 6 条时由同一拍 3 个
   backend lane 补齐到 9。
3. `Ftq.scala:408` 的 `resolveQueue.io.bpuTrain.ready` 在 `trainCache.valid`
   且 BPU 未 fire 时为 0；`:420-453` 的 trainCache 使入口在 ResolveQueue 中
   保持。`ResolveQueue.scala:165-178` 只在本拍有同索引报告时抑制出队，没有把
   入口提前清掉。训练背压是合法消费者行为，因此第 9 条可以在入口仍驻留时到达。
4. `:139-140` 的 `firstEmpty + PopCount(hitPrevious(i))` 直接作为
   `branches(...)` 的动态下标，没有与 `ResolveEntryBranchNumber=8` 比较；
   `indexWhere` 无空槽时返回 8，越界回绕覆盖 slot 0 或 7。两条 XFAIL 的激励
   （8 条后第 9 条；6 条后同拍 3 条）都在这个合法域内。

**结论：可达（confirmed-rtl）**，不是端口级任意压力。两条 strict XFAIL 与
`--runxfail` 证据原样保留；本轮没有实施任何 RTL 修复。影响面：被覆盖槽的
`target/cfiPosition/attribute` 被替换，BPU 训练分支集合可能丢失最早或最晚的
分支，首误预测掩码和后续训练随之错误。候选修复方向（仅文档，交用户决策）：
在写 `branches` 前用完整宽度比较
`firstEmpty + PopCount(hitPrevious(i)) < ResolveEntryBranchNumber.U`，不满足时
丢弃该报告并可选增加 `resolveQueueBranchOverflow` 性能计数；修复后需重跑两条
XFAIL、`resolve_queue` 全量、`ftq` 顶层相关用例与覆盖，并重新评估是否转为正向
契约测试。

## 覆盖闭环

最终 seed2 完整回归的原生覆盖（只统计 RTL 闭包）：

| DUT | 行 | 分支 | Toggle |
|---|---:|---:|---:|
| resolve_queue | 8045/8045 = 100.0% | 733/734 = 99.9% | 17587/19708 = 89.2% |
| commit_queue | 2259/2259 = 100.0% | 519/520 = 99.8% | 1364/1364 = 100.0% |
| ftq | 52193/52193 = 100.0% | **1718/1722 = 99.8%** | **128620/152622 = 84.3%** |

未覆盖行：三个 DUT 均为 **0**；`PrefetchQueue.sv` 208/208 行覆盖。未覆盖分支
共 **6 个计数 / 4 个 distinct 站点**，全部是 Verilator `initial` 初始化块的
`else if (reset)`：

| 站点 | 出现在 | 计数 | 归因 |
|---|---|---:|---|
| `CommitQueue.sv:4089` | commit_queue + ftq | 2 | 初始化块 reset else；运行期复位只走 `if (reset)` |
| `ResolveQueue.sv:12172` | resolve_queue + ftq | 2 | 同上 |
| `Ftq.sv:110836` | ftq | 1 | 同上 |
| `PrefetchQueue.sv:468` | ftq | 1 | 同上 |

leaf 与 Ftq 闭包重复计的原因：`ftq` DUT 的 RTL 闭包实际包含 `CommitQueue.sv`
和 `ResolveQueue.sv`，同一个初始化块的 `else if (reset)` 在 leaf DUT 的闭包和
Ftq 闭包中各产生一个分支点；覆盖报告按 DUT 汇总，因此 4 个 distinct 站点计为
6 个计数。不是 6 个新的功能缺口。

原“9 个缺口”逐条处置（收口后）：

| # | 站点（DUT 闭包） | 类别 | 处置 |
|---:|---|---|---|
| 1 | `CommitQueue.sv:4089`（commit_queue） | 初始化 reset else | 保留；运行期不可达 |
| 2 | `CommitQueue.sv:4089`（ftq，重复计） | 初始化 reset else | 同上，闭包重复 |
| 3 | `ResolveQueue.sv:12172`（resolve_queue） | 初始化 reset else | 保留；运行期不可达 |
| 4 | `ResolveQueue.sv:12172`（ftq，重复计） | 初始化 reset else | 同上，闭包重复 |
| 5 | `Ftq.sv:110836`（ftq） | 初始化 reset else | 保留；运行期不可达 |
| 6 | `PrefetchQueue.sv:468`（ftq） | 初始化 reset else | 保留；运行期不可达 |
| 7 | `ResolveQueue.sv:2587`（ftq） | 原“结构不可达” mux 臂 | **已覆盖**：`hitPrevious_3_0` 选 `enqIndex_0` |
| 8 | `ResolveQueue.sv:2589`（ftq） | 原“结构不可达” mux 臂 | **已覆盖**：`hitPrevious_3_1` 选 `enqIndex_1` |
| 9 | `ResolveQueue.sv:2591`（ftq） | 原“结构不可达” mux 臂 | **已覆盖**：`hitPrevious_3_2` 选 `enqIndex_2` |

第 7-9 项由 `test_ftq_ifu_backend_merge.py` 的 lane 0/1/2 参数化用例逐项命中；
不是 XFAIL 转正，旧分类撤回。

原先的“9 个缺口”中另有 3 个顶层 IFU 合并 mux 臂
（`ResolveQueue.sv:2587/2589/2591`）。收口时用合法顶层序列验证：IFU 重定向在
T 拍被接收，IFU resolve 经 `RegNext` 在 T+1 拍有效；同一拍 backend lane 0/1/2
可带同一 `ftqIdx`、来自同一 64B block 的不同 offset 的后端报告。此时
ResolveQueue 中尚无该 entry，IFU 分支与 backend lane 共同创建 entry，
`hitPrevious(3)` 选中 `enqIndex(0/1/2)`。`test_ftq_ifu_backend_merge.py` 的
1 个四源宽度控制和 3 个 lane 参数化用例覆盖了这三条臂；旧“结构不可达”结论是
测试台假设错误，不是 RTL 不可达。因此 ftq 分支从 1715/1722 提升到 1718/1722，
总缺口从 9 降到 6；新用例不改变分支分母，只增加命中。

Toggle 未覆盖 24002 点（ftq 128620/152622；resolve_queue 17587/19708；
commit_queue 1364/1364），主要归因：

- 原有 Ftq/ResolveQueue 的 payload 高位、meta/entry 初值与部分单向位；
- 新增 `PrefetchQueue` 的 1920 点中覆盖 1545（80.5%）；未覆盖集中在地址高位、
  mem 槽 payload 和同一信号只出现单方向（软件预取 source 恒为 1、queued
  overlap 臂恒为 0 等）。

本轮新增 enqueue 物理相位×lane 子集矩阵，把 `PrefetchQueue` 行覆盖从 28 条
未覆盖降到 0；8 槽/指针回绕/并发/source/redirect 用例覆盖全部 208 行。新增
全 1/全 0 地址扫描覆盖三个 softPrefetch 输入和 mem 槽的双向位。未覆盖 toggle
不改变本次已验证的控制/所有权/身份语义，但仍是未证明的高位数据通路范围。

### PrefetchQueue 逐项 reached/checked

“reached”指该情形在原生 DUT 上执行到目标 RTL 臂；“checked”指自动 checker
逐字段比较请求、队列距离/顺序、训练或 commit 输出，而不是只断言 agent 返回值。

| 情形 | 用例 | reached / checked |
|---|---|---|
| 8 个物理槽 + 指针回绕 | `test_eight_physical_slots_and_pointer_wrap_preserve_fifo_order`（17 项流式） | enq/deq 3-bit 指针多次回绕；mem_0..mem_7 全部使用，`PrefetchQueue.sv` 208/208 行；每项 start/source/FIFO 顺序逐项比较 |
| 容量 / 静默丢弃 | `test_soft_prefetch_queue_capacity_drops_excess_and_keeps_fifo_order` | 7 项保留、2 项丢弃；队列距离与 7 项顺序逐项比较 |
| enqueue 相位 × lane 子集 | `test_every_enqueue_pointer_phase_and_lane_subset_is_offered` | 8 个 enqPtr 相位 × 6 个 lane mask；所有槽写路径命中 |
| FDIP source=0 | `test_fdip_lane_source_is_zero_and_sw_source_is_one` | 纯 FDIP lane source=0；与 Sw 混合时 lane0=0/lane1=1；checker 比较 `source/req1_source` |
| Sw source=1 | 同上的混合 + `test_two_queued_prefetch_requests_report_the_declared_case` | 队列单发/双发 source=1；`PrefetchLane.source` 逐 lane 比较 |
| 与 resolve 并发 | `test_soft_prefetch_and_backend_resolve_share_one_edge` | 同一沿入队 Sw 与接收 backend resolve；队列距离=1、训练分支 `[1]`、Sw 请求均比较 |
| 与 commit 并发 | `test_soft_prefetch_and_callret_commit_share_one_edge` | 同一沿入队 Sw 与 callret；commit `ras=1`、队列距离=1、Sw 请求均比较 |
| redirect/flush 交互 | `test_redirect_suppresses_fdip_but_keeps_a_queued_sw_prefetch` | redirect 抑制 FDIP，队列 Sw 仍以 `source=1` 发出；queue 不被 redirect 清空 |
| reset | `test_reset_clears_a_pending_software_prefetch_queue` | reset 清空队列，之后重新入队/发出 |

全部 16 个 `test_ftq_prefetch_queue.py` 用例和 4 个
`test_ftq_ifu_backend_merge.py` 用例在 seed1/seed2 完整回归中均 PASS；
原有 11 个队列用例已包含 enqueue 相位/全地址位，收口新增 5 个覆盖上述并发、
回绕和 flush 维度。

## 复现命令

```sh
.venv/bin/ucv prepare ftq --require-unified-baseline
.venv/bin/ucv build ftq --require-unified-baseline
.venv/bin/ucv run ftq --workers 2 --seed 2 --require-unified-baseline \
  --output results/ftq-a0c2a26cb-closeout-seed2b-20261108 -- tests
.venv/bin/ucv run ftq --workers 2 --seed 1 --require-unified-baseline \
  --output results/ftq-a0c2a26cb-closeout-seed1-20261108 -- tests
cd suites/frontend/ftq
PYTHONPATH=/home/xyl/ucv4xs .venv/bin/python -m pytest -q --runxfail \
  tests/resolve_queue/test_resolve_overflow.py
```

自检通过不等于硬件通过；收集成功不等于功能通过。本页的 931 PASS 不包含
2 个真实 XFAIL，也不把 XFAIL 改写成 PASS，不写成“FTQ 全通过”。
