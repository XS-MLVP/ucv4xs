# `StoreUnitS0`：store 地址第 0 级

## 1. 模块职责

`NewStoreUnit` 的 S0 是 store 地址流水线的入口。它做四件事：

1. **请求源仲裁**：把 S1 回注的非对齐尾段（`unalignTail`）与 IQ 发射的标量
   store（`stin`）合并成一条流水线入口；硬件预取源在生成 RTL 中已被整源消除。
2. **组合发起 TLB 请求**：它不过流水线寄存器，直接由仲裁结果驱动，因此与
   仲裁同拍发出，且**不被 redirect kill 屏蔽**。
3. **地址/掩码合成本地判定**：标量 store 的 `vaddr/fullva/size/mask` 由
   `src_0 + sext(imm)` 与 `fuOpType` 合成；`align/unalignHead/cross4KPage`
   来自页内字节偏移算术。
4. **固定延迟一级流水**：`pipeOut` 只有一个寄存器，且没有 ready。

## 2. 固定延迟与无背压（本节是实际边界，不是简化）

生成 RTL 中：

```systemverilog
assign io_stin_ready = ~io_in_0_valid;          // 尾段优先，标量源被反压
pipeOutValid <= ~kill & arb_out_valid;          // 没有 ready 项
```

`StoreUnitS0.sv` 没有 `io_pipeOut_ready` 端口，`StoreUnitS1.sv` 也没有
`io_pipeIn_ready`；`NewStoreUnit.sv` 中 S0→S1 的连接同样不带 ready。结论：

- S0 **每拍都能接收**一个请求（只要不是尾段占用），不接受反压；
- 一个 beat 在 `pipeOut` 上只出现**一拍**，下一拍即被消费；
- `unalignTail` 是 S1 回注的、不能丢的请求，所以它没有 ready 输入；
- 整条 store 地址流水线是**固定延迟**的，背压在更上游（IQ 调度）处理。

## 3. 语义功能点

| ID | 语义 | 可观察结果 |
|---|---|---|
| **S0-ARB** | 尾段（优先级 0）压过标量（优先级 1）；标量源在尾段占用时被反压 | `stin.ready = !tail.valid`；两者同拍有效时 `entrance=0x1` 且 tail 字段胜出 |
| **S0-PIPE** | 仲裁结果在下一个时钟沿进入 `pipeOut`，一拍后可见，随后消失 | 驱动一拍 → `pipeOut.valid=1`；再一拍 → 0 |
| **S0-FIELDS** | 标量字段合成：`vaddr = src_0 + sext(imm[11:0])`（截断 50 位）、`fullva` 同式取 64 位、`size = fuOpType[3:1]` | 逐字段与独立参考比较 |
| **S0-MASK** | `mask = CBO ? 16'hFFFF : genVWmask128(vaddr, size)`；基值 B=0x1/H=0x3/W=0xF/D=0xFF/Q=0xFFFF，再左移 `vaddr[3:0]` | 各 size 与 16 个字节偏移 |
| **S0-QSIZE** | `size` 为 3 bit，因此 4..7 都是 `MemorySize.Q`（`b1??`）：偏移 15、掩码 0xFFFF、要求 `vaddr[3:0]==0` | size 4..7 的行为与 size 组合一致 |
| **S0-TLB-REQ** | TLB 请求由仲裁结果组合驱动，**不经流水寄存器、不被 kill 屏蔽** | 被 redirect 杀掉的那一拍 `tlbReq.valid=1`，而 `pipeOut.valid=0` |
| **S0-TLB-FIELDS** | `checkfullva = instrType[1] \| instrType[0]`；`cmd = {2'b0, ~isCboNoZero}`（普通 store 与 CBO.zero 为 write=1，其它 CBO 为 read=0）；`hyperinst = fuOpType[6] & ~fuOpType[0]`；`isPrefetch = instrType[2]` | 逐字段 |
| **S0-KILL** | `pipeOut.valid = arb.valid && !needFlush(robIdx)`，沿用 `RobPtr.needFlush` 的 flush/flushAfter、former、绕回语义 | kill 矩阵 6 种情形 |
| **S0-ILLEGAL** | `illegalIssue = !sqIdx.withInPhysicalQueue(sqDeqPtr)`，窗口为 `[deq, deq+64)`，指针由 `{sqIdx_first, sqIdx_second, sqIdx_value}` 与 deq 的对应字段比较 | 窗口首/尾、绕回、first 代际不匹配 |
| **S0-ALIGN** | CBO 与预取强制 `align=1`；尾段强制 `align=0`；标量按 size 对齐要求 | 4 种 size × 对齐/不对齐 |
| **S0-UNALIGNHEAD** | 标量：`(vaddr[11:0]+ByteOffset(size))[4] != vaddr[4]` 表示跨 16B；CBO/预取/尾段强制 0 | 跨与不跨各例 |
| **S0-CROSS4K** | 标量看 `(vaddr[11:0]+ByteOffset(size))[12]`；尾段**继承输入** `unalignTail.cross4KPage`；CBO/预取强制 0 | 标量跨页、尾段注入 0/1 |
| **S0-ADDRREADY** | `isAddrReadyHead` 是 8 位 SqPtr 全等比较（含两个 flag） | 值相同/不同、second_flag 不同 |

`ByteOffset`：B=0、H=1、W=3、D=7、Q=15（`MemorySize.ByteOffset`）。

## 4. 输入合法域

- `stin`：IQ 发射的标量 store。`fuOpType` 的 `[0]` 是 CBO 标志、`[3:1]` 是 size、
  `[6]` 是 hyper 指示；其余位对本级无意义但属于端口，会被透传。
- `unalignTail`：S1 检测到跨 16B 后回注的尾段，字段由 S1 生成；其
  `cross4KPage` 是唯一被 S0 直接使用的该源派生位。
- `sqDeqPtr` / `sqAddrReadyPtr`：SQ 指针，`{first_flag, second_flag, value}`，
  物理大小 64、multiple 2，`operation_value = {second_flag, value}`（7 bit）。
- `redirect`：可任意时刻有效，字段在 `valid=0` 时为 don't-care。
- 无 reset 之外的初始化要求；`pipeOut` 在 reset 时清零。

## 5. Don't-care

- 无请求时 `tlbReq.bits` 仍有确定值（来自仲裁 bubble 常量），但架构上是
  don't-care；测试仍逐字段核对，以固定生成 RTL 的可观测行为为准。
- `pipeOut.bits` 在 `valid=0` 时保持上一次的寄存器值，不比较。
- `unalignTail` 源没有 `ssid`/`storeSetHit`/`exceptionVec[19]` 端口，因此这些
  字段在尾段拍恒为 0（这不是 don't-care，而是结构常量）。

## 6. 依据

- `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewStoreUnit.scala:40-200`（S0 源、字段合成、对齐检查、流水寄存）
- `NewStoreUnit.scala:82-96`（`arbiter` = `chisel3.util.Arbiter`，固定优先级）
- `XiangShan/src/main/scala/xiangshan/mem/vector/VecCommon.scala:133-142`（`genVWmask128`）
- `XiangShan/src/main/scala/xiangshan/mem/MemCommon.scala:130-175`（`MemorySize.ByteOffset`）
- `XiangShan/src/main/scala/xiangshan/backend/rob/RobBundles.scala:294-358`（`RobPtr` 关系）
- `XiangShan/XSCache/utility/src/main/scala/utility/MultiFlagCircualQueuePtr.scala:127-180`（`withInPhysicalQueue`）
- `soc-split/rtl/StoreUnitS0.sv`（本 DUT）、`soc-split/rtl/StoreUnitS1.sv`（无 pipeIn ready 的旁证）
