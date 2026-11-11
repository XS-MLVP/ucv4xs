# LSQ 跨模块交互语义（以 Scala 为准）

本文按 [observation-precision](../../../../../../../skills/design/observation-precision.md) 的三层分工写：
**期望答案来自规格/合同**，**设计意图只从 Scala 读**，**可驱动可观测面只从生成 DUT 读**。
每条交互给出：谁发起、谁消费、握手条件、背压/撤销、身份传播、完成条件、以及会形成
时间窗口的交叉组合。

适用：`public-a0c2a26cb` / DefaultConfig。行号指锁定检出 `.cache/sources/f3ac6022…`。

覆盖状态词：`covered`（有用例且检查语义）/ `partial`（有用例但只查部分字段）/
`gap`（机制存在但无必达激励）/ `structural`（结构上不可达，附依据）/
`out-of-domain`（上层承接）。

## 0. 实例化层次（谁包含谁）

```
LsqWrapper                     LSQWrapper.scala:158-159
├── LoadQueue                  LoadQueue.scala:229-233
│   ├── LoadQueueRAR           (paddrModule = LqPAddrModule, freeList)
│   ├── LoadQueueRAW           (paddrModule = LqPAddrModule, maskModule = LqMaskModule, freeList)
│   ├── LoadQueueReplay        (age = AgeDetector, freeList)
│   ├── VirtualLoadQueue
│   └── LoadQueueUncache       (16× UncacheEntry, freeList, ncReqArb)
└── StoreQueue                 NewStoreQueue.scala:2185-2186
    ├── VirtualStoreQueue
    └── PhysicalStoreQueue
        ├── ForwardModule      NewStoreQueue.scala:1617
        ├── DeqModule          NewStoreQueue.scala:1618
        ├── UnalignQueue       NewStoreQueue.scala:1619
        └── EnterSbufferQueue  NewStoreQueue.scala:905 (as dataQueue)
```

## 1. 边界 B1：LsqWrapper ↔ LoadQueue / StoreQueue

| 项 | 内容 |
|---|---|
| 发起 | dispatch 的 `io.enq`（8 lane） |
| 消费 | `needAlloc(i)(0)`→LoadQueue、`(1)`→StoreQueue（`LSQWrapper.scala:181-190`） |
| 握手 | `io.enq.canAccept := lqCanAccept && sqCanAccept`（`:172`）；单侧 `lqCanAccept`/`sqCanAccept` 另出 |
| 身份传播 | load 的 `sqIdx` 来自 `storeQueue.io.enq.resp(i).physicalQueuePtr`（`:184`）——**load 的 SQ 依赖在入口就绑定到物理槽** |
| 背压 | `needAlloc=0` 时两侧 enq valid 都为 0（`:182/:190`），不占资源 |
| 完成 | `io.enq.resp(i).lqIdx/sqIdx` 回 dispatch（`:199-200`） |

**窗口**：`canAccept` 是 `&&`，所以任一队列满都会挡住整条 enq；但 `needAlloc` 为单侧时
另一侧不参与（`valid` 已 gate）。若把 `canAccept` 当作"两侧都能收"再按单侧发，会出现
一侧假接受。

覆盖：`partial` — `test_dispatch_filter_and_zero_flow_no_phantom_side_effect`（`testbenches/store_queue/tests/test_bytes.py`）
检查 `needAlloc=0`/filter/多 flow；`test_joint_capacity.py` 检查两侧同时满。
**未检查**：`sqIdx` 在 load 入口取的物理槽与后续 forward 使用的槽是否同一代（回绕 + 复用）。

## 2. 边界 B2：VirtualStoreQueue ↔ PhysicalStoreQueue

这是全工程最容易被误判的边界，因为有**两级指针 + 三拍传播**。

| 信号 | 方向 | Scala | 语义 |
|---|---|---|---|
| `physicalQueueEnqPtr` | VSQ→PSQ | `:310` | 虚拟分配推进后交给物理队列的入队指针 |
| `preCommitPtr.valid/bits` | VSQ→PSQ | `:330-331` | ROB head 命中时才允许 PSQ 置 committed（**预提交 ≠ 退休**） |
| `retiredPtr` | VSQ→PSQ | `:320` | ROB 退休后推进，PSQ 据此允许写出 |
| `redirectPtr.valid/bits` | VSQ→PSQ | `:371-372` | 撤销恢复点 |
| `headRobIdx` | VSQ→PSQ | `:374` | MMIO/CBO 写回用的 ROB 身份 |
| `deqPtr` / `deqCount` | PSQ→VSQ | `:2217-2218` | PSQ 出队反馈，VSQ 据此释放虚拟条目 |

三拍传播（源码注释 `:311` 明示）：
`rob retire → [next cycle] → virtualStoreQueue retire → [next 2 cycle] → physical storeQueue commit`。

**不变量**（都在 Scala 里，且**生成 RTL 中 `$fatal` 计数为 0**）：

```scala
// :323
XSError(retireValidReg && toPhysicalQueueRetirePtrNext =/= getEntryEndSqIdx(deqPtrVec.head - 1.U),
        "retirePtr update error!")
// :327-329
XSError(preCommitPtr < deqPtrVec.head && RegNext(retireCount === 0.U) && !deqPtrVec.head.isRotateBy(preCommitPtr), ...)
XSError(enqPtrVec.head < deqPtrVec.head && !deqPtrVec.head.isRotateBy(enqPtrVec.head), ...)
XSError(preCommitPtr > enqPtrVec.head && !preCommitPtr.isRotateBy(enqPtrVec.head), ...)
```

覆盖：`partial` — `testbenches/vsq/tests/test_extended.py`、`testbenches/vsq/tests/test_retire_batch_width.py` 逐拍检查
`retiredPtr_value`；`testbenches/store_queue/tests/test_remaining.py` 检查 `preCommit` 后
`sqEmpty`/`sqDeqPtr`。**`gap`**：没有"多 flow（segmented）+ 后续操作"的序列去触发
`retirePtr === getEntryEndSqIdx(deqPtrVec.head - 1)` 这条等式——这正是上游 #6597
（vsseg2e8.v LMUL4 + AMO 触发断言并停提交）的形态。当前 VSQ 激励只给 `flows` 计数，
不构造多寄存器分段 store。

## 3. 边界 B3：DeqModule ↔ EnterSbufferQueue

| 项 | 内容 |
|---|---|
| 发起 | DeqModule `writeToSbuffer.req(i)`（`NewStoreQueue.scala:1286-1292`） |
| 消费 | `dataQueue.io.fromDeqModule` → 内部 FIFO → `toSbuffer` |
| 握手 | `toSbufferValid(0)` 对 cross16B 要求 `dataQueue.io.fromDeqModule(0).ready && (1).ready`（`:1241`）；普通要求 `!uncacheStall && !cboStall && !unalignStall && committed && !vecInactive && 前缀有效`（`:1252-1260`） |
| 前缀约束 | `XSError(io.toSbuffer.req(i).valid && !io.toSbuffer.req(i-1).valid)`（`:832`）——低口无效时高口不得有效 |
| 完成 | 信用 `sbufferCreditIn = PopCount(dataQueue.io.deqPtrMove)`（`:1322`），`sbufferCreditUsed = PopCount(deqMask && deqUsesSbufferCredit)`（`:1358`） |
| 不变量 | `XSError(sbufferCreditUsed > sbufferCreditCount, "underflow")`、`XSError(next > StoreQueuePhysicalSize, "overflow")`（`:1362-1363`） |

`deqUsesSbufferCredit(i) = isCacheable(memoryType) && !isCbo && !vecInactive`（`:1323-1325`）。
**注意：credit 由 `deqCtrlEntries`/`deqDataEntries` 的类型决定，不由 `rdataDataEntries`**。

underflow 是 `structural`：`deqReady(i)` 要求 `sbufferCreditReady(deqCreditNeeded(i))`，
即 `count >= 前缀中可缓存条目数`，`deqMask` 是前缀 AND，故 `used <= count` 恒成立。

覆盖：`partial` — `testbenches/deq/tests/test_initial.py::test_single_cacheable_store_credit_waits_for_actual_sbuffer_consumption`
（credit 只在真实消费后到账）、`testbenches/store_queue/tests/test_bytes.py::test_real_second_page_or_line_split_partial_consumption_credit`
（只消费一段时原 owner 不释放）。`gap`：`testbenches/deq/model.py` 仍不按 `memory_type` 计算 credit 需求
（已登记 `GAP-PSQ-CREDIT`）。

## 4. 边界 B4：DeqModule ↔ UnalignQueue（跨页第二页）

| 项 | 内容 |
|---|---|
| 发起 | UQ `io.toDeqModule`（`NewStoreQueue.scala:1664`）→ DeqModule `fromUnalignQueue` |
| 命中 | `headCrossPage := headrdataPtr === fromUnalignQueue.bits.sqIdx && fromUnalignQueue.valid`（`:1166`） |
| 消费 | 端口 1 的 paddr 用 UQ 提供的第二页（`:1186-1189`） |
| **释放条件** | `io.fromUnalignQueue.ready := headrdataPtr === sqIdx && writeSbufferWire.head.fire`（`:1299`） |

**窗口（重要）**：释放条件是"第一页写出到 Sbuffer 的那一拍"。此后：
- UQ 条目消失 → `unalignQueue.io.forwardEntries` 不再含该第二页（`forwardModule.io.unalignEntriesIn`，`:1632`）；
- 但第二页片段可能仍未进 Sbuffer（端口 1 背压时停在 `writeSbufferWire(1)`）；
- PSQ 的前递 CAM 只按 16B 块匹配，第二页 16B 不在其中。

因此存在"第二页既不在 UQ、也不在 Sbuffer"的窗口，年轻 Load 查询第二页时看不到 hazard。
上游 #6822 正是这个（改为 `headDeqPtr === sqIdx && io.sqDeqCnt.orR`，并给 PSQ 加 `fwdHold`）。

覆盖：**已补探针并复现**（`testbenches/lsq_wrapper/tests/test_interaction_windows.py`）。
对照 `uq_held`（第二页仍在 UQ）3/3 PASS：拦截生效；`uq_released`（第一页已进 Sbuffer、
第二页仍在 EnterSbufferQueue）3/3 FAIL：`blocked=False`、`forwarded_ok=False`，且
`second_fragment_still_pending=True` 证明窗口真实存在。与上游 #6822 同根因。

## 5. 边界 B5：PhysicalStoreQueue ↔ ForwardModule

| 项 | 内容 |
|---|---|
| 输入 | `forwardModule.io.ctrlEntriesIn` ← PSQ `ctrlEntries`；`dataEntriesIn` ← `dataEntries`；`unalignEntriesIn` ← UQ；`unalignValidIn` ← UQ `forwardValid`（`:1632-1635`） |
| 发起 | LoadUnit 的 `io.forward(lane).s0Req`（vaddr/size/wait/strict/waitSqIdx） |
| 握手 | `s1Req_paddr` 提供翻译结果；`s1Kill` 撤销 |
| 输出 | `s2Resp`：`forwardInvalid` / `matchInvalid` / `addrInvalid_valid` / `dataInvalid_valid` / `forwardMask[16]` / `forwardData[16]` |
| 身份 | 选择用 `s1SelectOH`（最年轻重叠），依赖身份用 `dataInvalidSqIdx` |
| 不变量 | `XSError(s1SelectOH.orR && !s1SelectCtrlEntry.addrValid, "forward select a invalid entry")`（`:590`）、`XSError(s1LoadEnd < s1LoadStart && s1Valid, "ByteStart > ByteEnd")`（`:508`） |

覆盖：`covered`（字节级）— `checker.forward_byte_violations` 按不可变
生产者账本逐字节判"应前递或被阻塞"，配 `test_partial_store_coverage_must_block_or_forward_every_produced_byte`
（3 lane）与灵敏度注入。`gap`：`second_page` 的 hazard 只从 `inp.second_pages`（UQ 镜像）推出，
UQ 释放后即消失——与 B4 是同一窗口。

## 6. 边界 B6：LoadQueue ↔ 子模块

| 子模块 | 连接（`LoadQueue.scala`） | 关键语义 | 覆盖 |
|---|---|---|---|
| VirtualLoadQueue | `:255-263` 全 `io.*` 直连 | 分配、`ldWbPtr`、`lqEmpty`、`lqRedirect`、recoverStall | `covered`（`testbenches/vlq/tests/*` 23 例 + `testbenches/load_queue/tests/test_initial.py`） |
| LoadQueueRAR | `:237-241`：`release`、`ldWbPtr`、`validCount`、`rarNukeQuery` | `release` 与 `ldWbPtr` 同拍；`release2Cycle.valid := RegNext(io.release.valid)` 造成一拍错位 | `covered`（`testbenches/rar/*`，含 7 条真实 FAIL：`RAR-REL-001`） |
| LoadQueueRAW | `:246-250`：`storeIn`=STA、`stAddrReadySqPtr`、`rawNukeQuery`、`mdpTrain` | RAW 冲突依赖 SQ 地址就绪，不是数据 | `covered`（`testbenches/raw/*` 59 例） |
| LoadQueueReplay | `:292-304`：`enq`=LDU ldin、`replay`、`loadWakeup`、SQ 四个 ready 向量、`sqDeqPtr`、`ldWbPtr` | 入队按 S3 原因；bank 选择 `min(slot)` | `covered`（`testbenches/replay/tests/*` 137 例，含 3 条 post-edge 残余 FAIL） |
| LoadQueueUncache | `:268-284`、`:275-283`：`req` 逐 lane、`bypass`、`rollback` | 16 个 entry + freeList + 两级 RR 仲裁；SID 复用会覆盖未消费数据 | `covered`（`testbenches/uncache_entry/*` 400 例、`testbenches/load_uncache/*`，含 `LQU-SID-001` 29 条真实 FAIL） |

**RAW 的 `mdpTrain` 出域**：只用于 BPU 训练，LSQ 内部不消费。

## 7. 边界 B7：UncacheEntry ↔ Uncache（共享总线）

| 项 | 内容 |
|---|---|
| 发起 | entry 的 `uncache.req` |
| 仲裁 | `TwoLevelRRArbiter`（`LoadQueueUncache.scala:392`）→ 单一 `io.uncache.req` |
| 身份 | `req.bits.id`（7 位 SID）；`idResp.bits.mid/sid` 绑定 |
| 完成 | `idResp`（NC 的 ack）或 `resp`（数据/错误） |
| 故障字段 | Load 读 `nderr`/`error`（`:195-196`、`:211-221`）；**Store 读 `denied`/`corrupt`（`NewStoreQueue.scala:1087/1095`）——生产者不驱动，已在 `manifest/critical-fields.json` 记为 `absent` 缺陷** |

覆盖：Load 侧 `covered`（`test_bus.py` nc/mmio × fault、`uncache_owners.transfer(error/nderr)`）；
Store 侧 `fail`（`test_uncache_store_fault.py` 1 PASS 对照 + 2 FAIL）。

## 8. 边界 B8：LsqWrapper 内部单总线仲裁（load vs store）

```scala
val selectLq = (loadQueue.io.uncache.req.valid && !storeQueue.io.toUncacheBuffer.req.valid) ||
  (loadQueue.io.uncache.req.valid && storeQueue.io.toUncacheBuffer.req.valid &&
   loadQueue.io.uncache.req.bits.robIdx.isBeforeSlot(storeQueue.io.toUncacheBuffer.req.bits.robIdx))
```

`pendingstate`（`:276-299`）：`s_idle` 时按 `selectLq` 选一方；若 `io.uncacheOutstanding && nc`
则**留在 s_idle**（NC 可多发）；否则进 `s_load`/`s_store`，等 `io.uncache.resp.fire` 回 idle。

响应按 `io.uncache.resp.bits.is2lq` 路由到 Load 或 Store（`:324-329`），idResp 同理。

**不变量**：`when(!io.uncacheOutstanding) { assert(!((loadQueue...resp.valid || storeQueue...resp.valid) && pendingstate === s_idle)) }`（`:338-339`）。

覆盖：`covered` — `test_mixed_bus.py::test_unit_interface_load_older_or_tie_arbitration_not_normal_retirement`
（plain/wrap/former/tie 四组）、`test_normal_older_store_overtakes_held_load_and_routes_returns`
（io/nc × serial/outstanding × 三种 ROB 布局）。
`gap`：`!uncacheOutstanding` 下的"响应早到"只被构造为非法输入，没有作为协议负例显式驱动。

## 9. 交叉窗口清单（本轮新增登记）

| ID | 窗口 | Scala 依据 | 覆盖 |
|---|---|---|---|
| `IWL-VSQ-RETIRE` | 多 flow 分段 store 退休后 `retirePtr` 与 `deqPtrVec.head-1` 的等式 | `VirtualStoreQueue.scala:323` | `gap`（#6597 形态） |
| `IWL-UQ-SECOND-PAGE` | 第一页写出到 Sbuffer 后、第二页消费前 | `NewStoreQueue.scala:1299` + `:1632` | **`fail`**：3/3 探针复现（#6822 同根因），对照 3/3 PASS |
| `IWL-NC-CROSS16B` | NC store 的 vaddr 跨 16B | `NewStoreQueue.scala:1448` 防御断言；上游 `NewStoreUnit.scala:633` 已用 `am` 排除 | **`pass`**：初版探针非法，撤回；修正后 LSQ 正确拒绝 |
| `IWL-CREDIT-TYPE` | deq 窗口中可缓存/不可缓存混排时的 credit 需求 | `:1323-1325` | `gap`（`GAP-PSQ-CREDIT`） |
| `IWL-PRECOMMIT-RETIRE` | 预提交后、退休前的 `preCommitPtr` 与 `deqPtr` 关系 | `:327-329` | `partial` |

## 10. NC 跨 16B：一处**被我撤回**的假阳性（保留为教训）

`NewStoreQueue.scala:1448` 有一条防御性断言：

```scala
XSError(io.toUncacheBuffer.req.fire && io.toUncacheBuffer.req.bits.nc && headCross16B,
        "NC request should not cross 16B!")
```

我最初的判断是：请求组帧只发一个 8 字节 mask（`:1076`），所以跨 16B 时高半会丢。
后续复核推翻了它：

```scala
// NewStoreUnit.scala:632-633
val afUnalignMMIO = isMMIO && !align
val am = !align && isScalar && isNC && !pmpInaccessible
// :634
val hasException = in.hasException.get || af || am
```

**NC 标量 store 只要非对齐，上游就置 `storeAddrMisaligned`**（`am`），而跨 16B 的 8 字节 store
必然非对齐。`hasExceptionSet` → `ctrlEntries(i).hasException`（`:1823-1848`），
LSQ 的 `uncacheCanHandle` 又要求 `!headCtrlEntry.hasException`，所以这组合**根本不会发出
uncache 请求**。`:1448` 是上游已保证、永不触发的防御断言。

我第一版探针把该组合当作 `hasException=0` 干净驱动，等于喂入非法激励，把"只发 4 字节"
误判成缺陷。修正后的探针（`test_uncached_store_respects_upstream_misalign_exception`）：

| 场景 | `hasException` | 期望 | 实际 |
|---|---|---|---|
| `nc_aligned`（offset 8） | 0 | 发请求，8 字节全覆盖 | **PASS**，mask `0xff` |
| `nc_misaligned_with_upstream_exception`（offset 12） | 1 | **不发**请求 | **PASS**，确实没有请求 |

结论：**LSQ 行为正确，此条不是缺陷**。教训：判"缺保护"之前，要先确认上游是否已经
把这个组合排除在合法域之外——否则就会把防御性断言误读成失效的保护。

## 11. 验收

- 每条边界有发起/消费/握手/背压/身份/完成六项，且每项能指到 Scala 行。
- 每个 `gap` 有"缺什么 + 怎么补"，并落进 `function_points.CROSS_GAPS`。
- `structural` 必须给结构依据（如 credit underflow 的前缀单调性）。
- 不变量若在生成 RTL 中被裁剪，必须写明"本层无法靠断言兜底，只能靠激励。
