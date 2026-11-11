# InstrUncache 合同

本文件把期望来源分成三层：**规格/ISA/TileLink 义务**、**Scala 设计意图**、
**生成闭包的端口面**。参考模型只从第一层写答案；第二层解释状态机与寄存器；
第三层只说明哪些字段在 DUT 上可驱动/可观测。三层不一致时以残登记，不把 RTL
赋值抄成期望。

## 1. 模块边界

`InstrUncache` 是 `FrontendInlined` 的子模块，负责单条 MMIO 取指：

```text
FrontendInlinedImp
  └─ instrUncache: InstrUncache
       ├─ entries_0: InstrUncacheEntry
       └─ respArbiter: Arbiter1_InstrUncacheResp   // nMmioEntry = 1
```

依据：

- `Frontend.scala:125` 单独 `LazyModule(new InstrUncache)`；
- `Frontend.scala:264-266` 连接 `ifu.toUncache/fromUncache`，并把
  `instrUncache.io.flush := false.B`；
- `InstrUncacheImp.scala:61-85` 生成 `nMmioEntry` 个 Entry，D 通道按
  `mmioGrant.bits.source === i` 分发；`nMmioEntry=1` 时只有一个 Entry；
- `InstrUncacheImp.scala:43,77,93` 的 `Arbiter(new InstrUncacheResp, nMmioEntry)`
  在 1 输入时退化为 1:1 线，生成名 `Arbiter1_InstrUncacheResp`。

`nMmioEntry = 1`、`MmioBusWidth = 64`（8B）来自
`frontend/instruncache/Parameters.scala:21-25`。DefaultConfig 的 `PAddrBits = 48`
（`system/SoC.scala:57`），但 `PrunedAddr` 只保存 `addr[47:1]`（`PrunedAddr.scala:25-35`）。

## 2. 端口与 pruned 常量

### 2.1 顶层 `InstrUncache`

| 方向 | 生成端口 | 合同 |
|---|---|---|
| 输入 | `clock`, `reset` | reset 为异步高有效；回到四状态机 Invalid |
| A | `auto_client_out_a_ready`, `a_valid`, `a_bits_address[47:0]`, `a_bits_user_memPageType_NC`, `a_bits_user_memBackType_MM` | 一次 8B `Get`；地址 8B 对齐；user 位来自请求寄存器 |
| D | `d_valid`, `d_bits_source[0:0]`, `d_bits_denied`, `d_bits_data[63:0]`, `d_bits_corrupt` | 只有 source=0 的响应可见；D ready 恒 1（端口被裁剪） |
| IFU | `io_fromIfu_req_valid`, `io_fromIfu_req_bits_addr_addr[46:0]`, `io_fromIfu_req_bits_memBackTypeMM`, `io_fromIfu_req_bits_memPageTypeNC`, `io_fromIfu_req_ready` | `addr_addr` 是 `addr[47:1]`，即 2B 对齐字节地址；req 只在 Invalid 接受 |
| IFU 响应 | `io_toIfu_resp_valid`, `resp_bits_data[31:0]`, `corrupt`, `denied`, `needResend` | 响应 ready 恒 1；`valid` 只在一个 SendResp 拍有效 |
| WFI | `io_wfi_wfiReq`, `io_wfi_wfiSafe` | `wfiReq` 阻止新 A 请求；`wfiSafe=1` 当且仅当无待收 D 响应 |

生成闭包中不存在的端口及理由：

| 缺失端口 | Scala/接口依据 |
|---|---|
| `io_flush` | `Frontend.scala:266` 恒接 `false.B`；唯一实例来自 FrontendInlined；Entry 的 `needFlush` 寄存器随之被裁剪 |
| `auto_client_out_d_ready` | `InstrUncacheImp.scala:88` 覆盖 `mmioGrant.ready := true.B` |
| `io_toIfu_resp_ready` | `IfuUncacheUnit.scala:133` 固定 `fromUncache.ready := true.B` |
| A 的 `opcode/param/size/source/mask/data/corrupt/echo` | `InstrUncacheEntry.scala:81-85` 的 `edge.Get(fromSource=io.id, lgSize=3)` 与 8B 对齐固定 |
| `io_id`（Entry） | `nMmioEntry=1`，`entry.io.id := 0.U`（`InstrUncacheImp.scala:64`） |

这些不是“未接线”或“未知常量”：绑定层在构造时逐项断言其缺失，端口一旦重新出现
会失败并要求显式迁移。对应残余 `R-FLUSH`、`R-READY-PRUNED`、`R-A-CONST`。

### 2.2 `InstrUncacheEntry`

输入：

```text
clock, reset,
io_req_valid, io_req_bits_addr_addr[46:0],
io_req_bits_memBackTypeMM, io_req_bits_memPageTypeNC,
io_mmioAcquire_ready,
io_mmioGrant_valid, io_mmioGrant_bits_denied,
io_mmioGrant_bits_data[63:0], io_mmioGrant_bits_corrupt,
io_wfi_wfiReq
```

输出：

```text
io_req_ready,
io_resp_valid, io_resp_bits_data[31:0], io_resp_bits_corrupt,
io_resp_bits_denied, io_resp_bits_needResend,
io_mmioAcquire_valid, io_mmioAcquire_bits_address[47:0],
io_mmioAcquire_bits_user_memPageType_NC, io_mmioAcquire_bits_user_memBackType_MM,
io_wfi_wfiSafe
```

`io_mmioGrant_ready` 和 `io_resp_ready` 不在端口上：消费者分别把它们固定为 1。
因此 Entry 的 D 接收和响应消费都按“valid 即 fire”建模；这是闭包合同，不是遗漏。

### 2.3 `Arbiter1_InstrUncacheResp`

5 个输入、5 个输出，无时钟。`io_out_* = io_in_0_*` 逐字段恒等。`valid=0` 时
payload 不具功能含义，但设计是纯线；checker 对整组字段比较，并在功能用例中显式
覆盖三个错误/重发位的独立性。

## 3. 四状态机

`InstrUncacheEntry.scala:47-53` 定义：

| 状态 | 值 | `req_ready` | `resp_valid` | `acquire_valid` | `wfi_safe` |
|---|---:|---:|---:|---:|---:|
| Invalid | 0 | 1 | 0 | 0 | 1 |
| RefillReq | 1 | 0 | 0 | `!wfiReq` | 1 |
| RefillResp | 2 | 0 | 0 | 0 | **0** |
| SendResp | 3 | 0 | 1 | 0 | 1 |

转移（`InstrUncacheEntry.scala:109-166`）：

```text
Invalid    --req.fire--> RefillReq
RefillReq  --A.fire----> RefillResp
RefillResp --D.fire----> RefillReq   if needResend
                        -> SendResp   otherwise
SendResp   --resp.fire-> Invalid     (resp.ready 恒 1)
```

`req.ready := state === Invalid`（`:66`），所以一个未完成请求期间不会接受第二笔；
`resp.valid := state === SendResp`（`:100`）。reset 异步清空状态与所有数据寄存器
（生成 RTL 的 `always @(posedge clock or posedge reset)`）。

## 4. 地址、窗口与 resend

输入 `addr` 是 2B 对齐字节地址。记：

```text
aligned      = addr & ~7
addr(2,1)    = (addr >> 1) & 3
crossBus     = addr(2,1) == 0b11
crossPage    = addr(11,1) == 0x7FF   (即 addr[11:1] 全 1)
```

- A 地址 = `aligned`；`resending=1` 时 = `aligned + 8`（`:76,83-84`）。
- 8B 拍按 `addr(2,1)` 抽取 4B 窗口：

| `addr(2,1)` | 窗口 |
|---:|---|
| 0 | `beat[31:0]` |
| 1 | `beat[47:16]` |
| 2 | `beat[63:32]` |
| 3 | `{16'h0, beat[63:48]}` |

`addr(2,1)=3` 时 4B 取指跨 8B 边界，需要第二拍；第一拍只保存
`beat[63:48]` 作为低 16 位，第二拍 `beat[15:0]` 作为高 16 位，拼成完整 4B。
`resending` 只允许一次：第二次 refill 不会再次 resend（`:145-153`）。

resend 的第二拍地址是 `aligned + 8`；只有 `crossBus && !crossPage && !corrupt &&
!RVC && !resending` 才自动 resend（`:145`）。`isRVC(inst)` 是 `inst(1,0) =/= 3`
（`ifu/Helpers.scala:28`）。

## 5. 跨页 needResend

`crossPage` 只在 `addr[11:1]` 全 1（即 4B 窗口位于页末 2B）时成立。响应输出：

```text
resp.needResend = crossPage && !respCorruptReg && !isRVC(respDataReg[15:0])
```

（`:106`）。语义是：**干净、非 RVC 的跨页取指**需要 IFU 重新检查 iTLB/PMP；
RVC 只需要 2B，不重新取指；corrupt/denied 已经产生异常，不再要求 resend。

`denied` 的 TileLink 前置条件是 `denied => corrupt`（`:105` 的注释和协议），
模型/输入构造在 D 通道拒绝 `denied=1, corrupt=0` 的非法激励（`INC-ENV-003`）。

## 6. WFI 与响应丢失

- `io.mmioAcquire.valid = state === RefillReq && !wfi.wfiReq`（`:80`）：wfi 请求期间
  不向 L2 发新 Get，但已接受的请求保持。
- `io.wfi.wfiSafe := state =/= RefillResp`（`:93`）：只有仍可能收到 D 响应的
  RefillResp 不安全；顶层单 Entry 时 `reduce(_ && _)` 退化为自身。
- 如果 D 响应丢失，Entry 停在 RefillResp：不发假响应、`req_ready=0`、
  `wfiSafe=0`；只有 reset 能清除。该行为由定向用例和随机模型共同检查。
- 响应 ready 恒 1，因此正常响应只持续一个 SendResp 拍；不存在“合法反压”场景
  （`R-READY-PRUNED`）。

## 7. 异常映射

本模块输出 `corrupt`/`denied` 原始标志，不输出 3 位异常码。异常码映射在
`IfuUncacheUnit.scala:110-115`（`denied→AF`、`corrupt→HWE`），属于 IFU 的
out-of-domain 行为，不在本工程伪称已验证。本工程验证：

- `corrupt` 在干净 D 响应后为 0，`corrupt=1` 时置位；
- `denied=1` 时 `denied` 与 `corrupt` 同时为 1（合法 TileLink 响应）；
- 两者都抑制自动 resend 与 `needResend`。

## 8. D source 过滤

`InstrUncacheImp.scala:81-84` 只把 `mmioGrant.bits.source === i` 的 D 响应接到
entry i。`nMmioEntry=1` 时生成 RTL 是：

```text
entry.io.mmioGrant_valid = ~d_bits_source & d_valid
```

source 端口 1 位；合法 client source 只有 0。source=1 的响应是超出唯一 source
范围的鲁棒性对照（`R-SRC-OUT-OF-RANGE`），不能写响应寄存器或提前结束请求。

## 9. flush/取消：DefaultConfig 下恒 0，取消路径不可达

**结论（2026-11-08 复核）：在 `public-a0c2a26cb` / DefaultConfig 中，
`instrUncache.io.flush` 恒为 `false.B`，Entry 的 flush/needFlush 取消路径不可达。**
这不是缺陷，也不是“已验证 flush 行为”；它是本单元范围之外的结构事实。机器证据
保存在 [`docs/spec/verification/evidence/flush-closure.json`](../verification/evidence/flush-closure.json)，可用
`tools/audit_flush_closure.py` 复核。

Scala 依据：

| 位置 | 文本 | 作用 |
|---|---|---|
| `frontend/Frontend.scala:125` | `val instrUncache: InstrUncache = LazyModule(new InstrUncache)` | 全仓库唯一 `InstrUncache` 实例 |
| `frontend/Frontend.scala:266` | `instrUncache.io.flush := false.B` | 把 flush 输入固定为 0 |
| `frontend/instruncache/InstrUncacheImp.scala:65` | `entry.io.flush := io.flush` | 顶层透传到 Entry |
| `frontend/instruncache/InstrUncacheEntry.scala:41` | `val flush: Bool = Input(Bool())` | Entry 的 flush 端口 |
| `frontend/instruncache/InstrUncacheEntry.scala:58-63` | `needFlush` 的置位/清除 | 只有 flush 高电平时才可能进入 |
| `frontend/instruncache/InstrUncacheEntry.scala:100` | `resp.valid := SendResp && !needFlush` | 取消路径对响应的唯一影响 |
| `frontend/instruncache/InstrUncacheEntry.scala:162` | `when(io.resp.fire \|\| needFlush)` | 取消路径离开 SendResp 的唯一分支 |

第二条实例化路径也不会置 1：`EnableSimFrontend` 默认 `false`
（`Parameters.scala:632`），且 `SimFrontendInlinedImp` 把整个
`instrUncache.io` 接 `WireDefault(0.U.asTypeOf(instrUncache.io))`
（`SimFrontend.scala:195`）。DefaultConfig 未覆盖该默认值。

生成闭包依据（与整芯片缓存 `d7c6bc4d…` 逐字节一致）：

| 文件 | sha256 | 端口数 | `flush`/`needFlush` |
|---|---|---:|---|
| `InstrUncache.sv` | `a91b3c2cd2744a91a14ae1a952cc6f65de236c85877687aab2da5ff2377ceb14` | 24 | 均不存在 |
| `InstrUncacheEntry.sv` | `7c1fec63a64b9619ffea39e1a4d0711628f235c8e56676fca6550fc89185d7b6` | 23 | 均不存在 |
| `Arbiter1_InstrUncacheResp.sv` | `35a2b18d15340af9f07908943cf87497b2fa49ebd592017b6d494d70712f36f3` | 10 | 不适用 |
| `Frontend.sv`（整芯片生成） | `fd988931577758db9fe6f1bbdf66d46433ae1f5e17fce0bd5b9100a5bcf83126` | — | `inner_instrUncache` 实例（L2763）无 `.io_flush` 连接 |

因此：

- `R-FLUSH` 在本单元登记为 **out-of-domain / accepted-limited**（只描述结构事实，
  不声称验证 flush）；
- 设计决定本身仍开放：`FRONTEND-FLUSH-CONNECT`（blocking/open，owner
  `frontend/design`）要求设计 owner 确认 `false.B` 是永久意图并入合同，或补上
  真实 flush 连接/删除端口；确认前整体 `hardware_verdict=INCOMPLETE`；
- `INC-FLUSH-012` 是**验证环境分区**内的结构检查点，只证明上述裁剪与哈希一致，
  不是硬件功能点，也**不**写成 flush 行为 PASS；
- 本工程不声称验证 flush 语义；若其他配置或后续 RTL 把 flush 接实，重新生成后
  必须重跑并单独标注（见第 10 节）。

reset 是闭包内唯一可用的取消机制，定向覆盖“RefillResp 中 reset”和
“SendResp 响应已消费后 idle reset”两个场景。`test_flush_closure_recorded_evidence_matches_active_design`
与 `test_generated_closure_has_no_flush_port_or_register` 会在上述任一事实变化时
失败，强制重新审查分类。

## 10. 跨配置边界

本文件的全部结论只对 **`public-a0c2a26cb` / DefaultConfig** 成立：

- flush 恒 0 来自 `FrontendInlinedImp` 的固定连接，不是 `HasInstrUncacheParameters`
  的常数；其他配置若改变该连接（或启用不同的 Frontend 实现），`io_flush` 可能
  重新出现，当前 `INC-FLUSH-012` 证据会失配；
- `nMmioEntry` 在 `HasInstrUncacheConst` 中固定为 1；改成多 entry 会改变
  `Arbiter1_InstrUncacheResp` 的退化性质和 source 宽度；
- `MmioBusWidth = 64`、`PAddrBits = 48`、PMA 上限 2^43 都参与地址/resend 合同；
- 其他基线可能有不同的上游源码或生成缓存，RTL 哈希和 Scala 行号都必须重新核对。

修改上述任一项后，不能用本工程的旧结果外推；需要重新 prepare/build、重跑双 seed、
更新 `docs/spec/verification/evidence/flush-closure.json`，并在文档中单独标注新的配置边界。

## 11. 时钟与采样

- 输入由 `SyncSingleCycleDriver` 单周期槽驱动，idle 帧在每个槽结束后恢复。
- 每个时钟 DUT 用 `DriveStable(clock)` 采边沿前组合值、`RisingEdge(clock)` 采边沿
  后值；模型分别给出 `outputs(state_t, inputs_t)` 与
  `outputs(state_{t+1}, inputs_t)`。
- 组合 Arbiter 没有 RTL clock，使用 Picker 的 `GetXClock()` 与单相
  `RisingEdge` 采样；每次评估前进一个 xclock 槽。
- 复位期间只比较边沿后的空闲输出；异步 reset 的边沿前值不作为合同。
