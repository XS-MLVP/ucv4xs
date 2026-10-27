# Sbuffer flush/empty 合同复核

结论：**当前 RTL 在 flush/empty 上的行为与文档化的设计意图和 RISC-V CMO 排序规则一致，
之前把 `flush.empty` 受 `sqempty` 门控当成 CMO 缺陷是一个假阳性。** 该结论由独立文档、
上游 PR、消费者 FSM 和信号接线得出，不是靠参考模型与 RTL 互相印证。

## 1. 问题

`Sbuffer` 有两个“空”输出：

- `sbempty`：`cmo_empty = 行全部无效 && mshr_store_empty && 无 in.req.valid`；
- `flush.empty`：`all_empty = cmo_empty && sqempty`。

CMO 排空时 `flush.empty` 会一直为 0（只要 `sqempty=0`），而 CMO 路径实际消费的是
`sbempty`。需要确认“CMO 不等 SQ 空”是正确设计，而不是漏等。

## 2. 独立证据

### 2.1 RISC-V CMO 规范

RISC-V Unprivileged ISA，Chapter 19 “CMO Extensions”，19.1.4.1 Memory Ordering：

> For cache-block management instructions, the resulting invalidate, clean, and flush
> operations behave as stores in the PPO rules subject to one additional overlapping
> address rule. Specifically, if *a* precedes *b* in program order, then *a* will precede
> *b* in the global memory order if:
> - *a* is an invalidate, clean, or flush, *b* is a load, and *a* and *b* access
>   overlapping memory addresses

同节还规定 `cbo.zero` 产生的 store “behave as stores in the PPO rules and are ordered by
other instructions that order stores”。

由此得到两个独立于 RTL 的要求：

1. CMO 必须排在**更老的 store** 之后（store→CMO 的顺序），所以更老的已提交 store
   必须真正到达一致性点；它们可能还在 Sbuffer/MSHR，因此要排空 Sbuffer 和 MSHR。
2. CMO **不要求**排空更年轻的 store；更年轻的 store 本来就必须排在 CMO 之后。

### 2.2 上游设计意图：PR #6183

`fix(Sbuffer): split CMO sbuffer drain empty checks (#6183)`（2026-07-08，合并到
`kunminghu-v3`）的正文：

> Add an signal to indicate CMO flush when io.in.flush.valid of sbuffer is set. CMO flush
> needs to drain sbuffer and input valid requests.
> State x_drain_sbuffer does not need mshr drain.

同一提交把原来的单一 `empty` 拆成：

```scala
val sbuffer_empty      = Cat(invalidMask).andR
val sbuffer_mshr_empty = sbuffer_empty && io.mshr_store_empty
val inReq_empty        = !Cat(io.in.req.map(_.valid)).orR
val cmo_empty          = sbuffer_mshr_empty && inReq_empty
val all_empty          = cmo_empty && io.sqempty

io.sbempty     := GatedValidRegNext(cmo_empty)
io.flush.empty := GatedValidRegNext(all_empty)
// x_drain_all 的退出条件：
when(Mux(io.flush.isCmo, cmo_empty, all_empty)) { sbuffer_state := x_idle }
```

也就是说，“CMO 用 `cmo_empty`、fence/atomics 用 `all_empty`”是上游明确的设计，不是
偶然的接线。

### 2.3 消费者接线

`MemBlock.scala`（当前基线）：

```scala
val cmoFlush     = lsq.io.flushSbuffer.valid
val fenceFlush   = io.ooo_to_mem.flushSb
val atomicsFlush = atomicsUnit.io.flush_sbuffer.valid
val stIsEmpty    = sbuffer.io.flush.empty && uncache.io.flush.empty
io.mem_to_ooo.sbIsEmpty := RegNext(stIsEmpty)

sbuffer.io.flush.valid := RegNext(fenceFlush || atomicsFlush || cmoFlush)
sbuffer.io.flush.isCmo := RegNext(cmoFlush)
lsq.io.flushSbuffer.empty := sbuffer.io.sbempty
atomicsUnit.io.flush_sbuffer.empty := stIsEmpty
```

| 信号 | 实际消费者 | 消费者要求的语义 |
|---|---|---|
| `sbuffer.io.sbempty` | `lsq.io.flushSbuffer.empty` → `SbufferCtrlIO.Resp.empty` → CBO FSM | CMO：Sbuffer + 输入 + MSHR 空即可，不要求 SQ 空 |
| `sbuffer.io.flush.empty` | `stIsEmpty` → `mem_to_ooo.sbIsEmpty`（Fence）和 AtomicsUnit | fence/atomics：整条 store 路径（含 SQ）都空 |

`Fence.scala`：

```scala
val sbEmpty = toSbuffer.sbIsEmpty
when (state === s_wait && func === FenceOpType.fence && sbEmpty) { state := s_fence }
```

`AtomicsUnit.scala`：

```scala
val sbuffer_empty = io.flush_sbuffer.empty
state := Mux(sbuffer_empty, s_cache_req, s_wait_flush_sbuffer_resp)
```

`NewStoreQueue.scala` 的 CBO FSM：

```scala
is(CboState.flushSb) {
  when(io.sbufferCtrl.resp.empty && dataQueue.io.empty) {  // Ensure there are no in-flight request.
    cboStateNext := Mux(isCboZero(headDataEntry.cboType), CboState.writeback, CboState.sendReq)
  }
}
```

`io.sbufferCtrl.resp.empty` 就是 `io.flushSbuffer.empty`，在 `MemBlock` 中接
`sbuffer.io.sbempty`。所以 CBO 等的是 `sbempty`。

### 2.4 为什么 CMO 不能等 `sqempty`

CBO 必须在 StoreQueue 头部执行，且它的 SQ 条目只有在 CMO 完成后才释放：

- `NewStoreQueue.scala` 注释：
  > NOTE: when deq mmio/cbo, rdataPtr === deqPtr, because mmio/cbo need to execute at head of StoreQueue.
- `handleFinish` 在 `writeBack.fire` 时置位（`handleFinishSet`），而 `writeBack` 只在
  `cboState === CboState.writeback` 时有效。
- `io.sqEmpty := virtualStoreQueue.io.empty && physicalQueue.io.empty`。

因此 CMO 处理期间 `sqempty` 必然为 0。如果 `sbempty` 也包含 `sqempty`，CBO FSM 就永远
等不到 `resp.empty`，形成死锁。这也解释了为什么上游要专门拆出 `isCmo` 和 `cmo_empty`。

### 2.5 为什么 CMO 要等 MSHR

`MissQueue.scala` 注释：

> sbuffer-flush must flush all store entries in mshr as well
> Store misses may reside either in MSHR entries or in the miss_req_pipe_reg.
> sbuffer-flush should wait until both places are clear.

如果 CMO 越过仍在 MSHR 中的 store miss，clean/inval 可能在 store 数据到达 L2 之前执行，
破坏 store→CMO 的顺序。因此 `cmo_empty` 包含 `mshr_store_empty` 是必要的。

### 2.6 `wline` 的合法域

上游只把 `wline` 用于 `cbo.zero`，且数据恒为 0：

- `NewStoreQueue.scala:1272`：`port.bits.wline := ctrlEntry.isCbo && isCboZero(dataEntry.cboType)`
- `NewStoreQueue.scala:1966`：`dataEntries(...).data := Mux(LSUOpType.isCboZero(...), 0.U, ...)`
- `Sbuffer.scala` difftest 断言：`"wline only supports whole zero write now"`

**结论：`wline=1` 且 payload 非 0 不是当前父块可达的合法请求。** 顶层 UT 只使用零
payload；`SbufferData` 模块级仍保留非零 payload 的广播能力检查，但明确标注为“模块能力，
不是父块可达行为”，不计入父块行为证据。

## 3. 测试如何按合同修正

| 用例 | 修正前 | 修正后 |
|---|---|---|
| `test_wline_zero_all_lines` | 用非零 payload 驱动 `wline`，父块不可达 | 只用零 payload；16 个槽全部写入；四 lane 都检查 mask 与全零数据 |
| `test_fence_flush_empty_requires_sqempty` | 只断言 `flush.empty` | 排空后断言 `sbempty=1` 而 `flush.empty=0`；`sqempty=1` 后 `flush.empty=1` |
| `test_cmo_completion_uses_sbempty_without_sqempty` | 只用 `flush.empty` 推断 CMO | 先断言 MSHR 非空时 `sbempty=0`；MSHR 空后断言 `sbempty=1` 且 `sqempty=0`；`flush.empty` 保持 0；`sqempty=1` 后才为 1 |

这些期望来自 2.1–2.5 的规范、PR 和消费者合同，不是从 DUT 输出反推的。两个新用例
直接断言公开端口 `sbempty`/`flush.empty` 与 `sqempty`/`mshr_store_empty` 的关系，
不经过参考模型；参考模型不参与 flush 语义的判定。

## 4. 仍未覆盖的边界

- 本 UT 验证 `Sbuffer` 消费的 `sbempty`/`flush.empty`；CBO FSM 本身、SQ 出队顺序和
  DCache 响应属于父块，未在本 DUT 内验证。
- `stIsEmpty` 还包含 `uncache.flush.empty`；本 DUT 没有 Uncache，未覆盖该合取项。
- 不注入非法 CMO 输入；不为实现内部状态编造端口。
- 现成 RTL 未编译 `--assert`，内部不变量靠外部检查。

## 5. 判定

| 问题 | 判定 | 依据 |
|---|---|---|
| CMO 期间 `flush.empty=0` 是 bug 吗 | **不是** | PR #6183 明确拆分；`flush.empty` 是 fence/atomics 的整条 store 路径空 |
| CMO 只等 `sbempty` 会漏掉更老 store 吗 | **不会** | CMO 在 SQ 头执行，更老 store 已提交并进入 SB/MSHR；`cmo_empty` 等 SB+MSHR+输入 |
| CMO 会越过更年轻 store 吗 | **不会** | SQ 顺序出队，CBO 的条目阻塞头部直到 writeback；年轻 store 不可能先进入 SB |
| `wline` 非零 payload 需要验证吗 | **不需要作为父块证据** | 父块只在 cbo.zero 产生 `wline`，数据恒 0 |

如果未来出现以下任一变化，则应作为真实缺陷重新审查：

1. `sbempty` 被改成包含 `sqempty`；
2. CBO FSM 改为消费 `flush.empty`；
3. `wline` 被用于非 `cbo.zero` 的场景或非零 payload；
4. CMO 不再等待 `mshr_store_empty`。

## 6. 证据

- 运行：`results/sbuffer-top-contract-03/`（16 PASS，功能覆盖 8 组 100%，
  DUT 行 12648/13191，toggle 70275/85706，branch 2690/2724）。
- 覆盖率审计：`results/sbuffer-top-contract-03/coverage-audit.json`。
- 上游证据：`XiangShan` 提交 `102a72f83` / PR #6183、`MemBlock.scala:1175-1186,1239`、
  `Fence.scala:58-83`、`AtomicsUnit.scala:125,312,509`、
  `NewStoreQueue.scala:967-1003,1296-1310,1659`、`MissQueue.scala:1255,1285`。
- 规范：RISC-V Unprivileged ISA 20260120，Chapter 19（CMO），19.1.4.1。
