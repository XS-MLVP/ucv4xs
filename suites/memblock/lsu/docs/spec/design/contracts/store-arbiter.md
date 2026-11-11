# `Arbiter3_StoreStageIO`：S0 store 请求源仲裁

## 1. 模块职责

`NewStoreUnit` 的 S0 需要把多个 store 请求源合并成一条流水线入口。源码
（`NewStoreUnit.scala:81-126`）用 `chisel3.util.Arbiter` 对三个 `StoreStageIO`
源做固定优先级仲裁：

| 优先级 | 源码名 | `StoreEntrance` | 说明 |
|---:|---|---|---|
| 0 | `unalignTail` | `unalignTail`（one-hot `0x1`） | S1 检测到跨 16B 后回注的尾段请求 |
| 1 | `scalarIssue` | `scalarIssue`（one-hot `0x8`） | IQ 发射的标量 store，来自 `stin` |
| 2 | `prefetchReq` | `prefetch`（one-hot `0x2`） | 硬件 store 预取 |

仲裁结果进入 S0 流水线寄存器（`pipeIn`/`sink`）。本 DUT 只覆盖仲裁器本身，
不包含 S0 的 kill、TLB、trigger、对齐检查和流水寄存。

## 2. 生成 RTL 的实际边界

固定生成 RTL（`rtl/store_arbiter/Arbiter3_StoreStageIO.sv`）与源码意图有两处
必须按**实际端口**描述的差异，不能凭 Scala 想象：

1. **第 2 源（prefetch）已整源消除**：生成的 `StoreUnitS0` 没有 `io_prefetchReq`
   端口（`StoreUnitS0.sv` 中 `prefetch` 字样出现 0 次），因此
   `prefetchReq.valid` 被常量折叠为 0，`io_in_2_*` 整组端口消失。它的常量载荷
   只剩在**无请求时的 bubble 输出**里：
   - `entrance = 0x2`（prefetch one-hot）
   - `accessType.instrType = 3'h4`
   - `size = 3'h4`（`MemorySize.QB`）
   - `mask = 16'hFFFF`（整行）
   - 其余字段为 0
2. **第 0 源没有 ready**：`io_in_0` 只有 `valid`/`bits`，没有 `ready` 输出。
   `unalignTail` 是 S1 回注的、不能丢的请求，仲裁器必须无条件接收它。
   只有 `io_in_1_ready`（标量源）存在。

因此本 DUT 的有效输入是两路，输出一路；三种 `entrance` 编码中 `0x2` 只在
`out.valid=0` 的 bubble 中出现。

## 3. 语义功能点

| ID | 语义 | 可观察结果 |
|---|---|---|
| **ARB3-IDLE** | 两路都无请求时输出无效，标量源始终可接收 | `out.valid=0`；`in_1.ready=1`；bubble 载荷等于上文 prefetch 常量（`entrance=0x2`、`instrType=4`、`size=4`、`mask=0xFFFF`、其余 0） |
| **ARB3-TAIL-ONLY** | 只有 unalign tail 请求时，它被无条件接收且逐字段透传 | `out.valid=1`；`entrance=0x1`；`in_1.ready=0`；输出 `bits` 与 `in_0` 输入的每个已实现字段逐位相等 |
| **ARB3-SCALAR-ONLY** | 只有标量请求时被接收并逐字段透传，包括只存在于该源的 `ssid`/`storeSetHit` | `out.valid=1`；`entrance=0x8`；`in_1.ready=1`；输出 `bits` 与 `in_1` 逐字段相等 |
| **ARB3-PRIORITY** | 两路同时有效时固定选 unalign tail，标量源被反压 | `out.valid=1`；`entrance=0x1`；`in_1.ready=0`；输出全部来自 `in_0`，不含任何 `in_1` 字段 |
| **ARB3-NO-DROP** | 第 0 源没有反压通路，任何 `in_1` 状态下都不能被丢弃或阻塞 | `in_0.valid=1` ⇒ `out.valid=1` 且 `entrance=0x1`，与 `in_1.valid` 无关 |
| **ARB3-SELECT-ISOLATION** | 输出每个字段都是"被选中源"的纯函数，未被选中的源不能泄漏 | 未选中源的任意比特翻转都不改变 `out.valid`/`entrance` 和选中源字段 |
| **ARB3-EXCV19** | `uop.exceptionVec[19]` 只来自 unalign tail 源 | `out.bits.uop.exceptionVec_19 == in_0.valid & in_0.uop.exceptionVec_19`；标量被选中时恒 0 |
| **ARB3-VALID-GATED** | 若字段在 RTL 中以 `源valid & 源bits` 形式实现，则该字段在源未被选中时为 0，被选中时等于源值 | `isCbo`、`isCboNoZero`、`isRVC`、`ftqPtr.flag`、`robIdx.flag`、`robIdx.isFormer`、`sqIdx.first/second_flag`、`storeSetHit` 在各自源被选中时透传，否则为 0 |

`in_0` 没有 `ssid`/`storeSetHit`/`accessType.instrType` 之外的 `instrType` 语义差异：
`in_0` 的 `accessType.instrType` 是真实输入端口并透传；`in_1` 的 `instrType`
在父块里被固定为 `InstrType.scalar`，在本 DUT 中是常量 `3'h1`（见
`StoreUnitS0.sv` 中 `io_in_1_bits_accessType_instrType` 恒为 `3'h1`）。

## 4. 输入合法域

- `in_0`（unalign tail）：`valid` 可任意；`bits` 在 `valid=0` 时为 don't-care，
  但测试仍驱动确定值以便检查"未选中不泄漏"。
- `in_1`（标量）：`valid` 可任意；`bits` 在 `valid=0` 时为 don't-care。
- 纯组合模块：无时钟、无 reset，单次求值即反映当前输入。
- 不存在"同时多 lane 有效必须互斥"的约束：优先级语义明确允许两路同拍有效。

## 5. 合法域外的边界（只记录，不作为正常功能）

- `in_0` 在 `valid=1` 且父块流水寄存器无法接收时仍会被"接收"，因为本层没有
  ready。这个不可反压的性质是 S1→S0 回注协议的既有设计，不是缺陷；它的后果
  （尾段是否会被覆盖）在 `StoreUnitS0` 父块 UT 中检查，不在本叶子重复推断。

## 6. 检查方式

参考模型是一个**独立的两路优先级选择器 + 显式默认载荷表**，不复用 RTL 的
三元表达式。每次求值后逐字段比较：

1. `out.valid`、`in_1.ready`；
2. `entrance` 编码；
3. 22 个已实现 payload 字段（含 `ssid`/`storeSetHit`）。

`bubble` 情况的 payload 也逐字段检查：它虽然架构上是 don't-care，但它是生成
RTL 的确定可观测量，必须与"prefetch 常量"一致，否则说明源消除方式与合同不符。

## 7. 覆盖要求

- 两路 valid 的 4 种组合。
- 每路单向透传时的字段级保真（全部字段），以及未被选中源的随机载荷不泄漏。
- `entrance` 三种编码中可达的两种（`0x1`、`0x8`）与 bubble（`0x2`）。
- 合法随机：两路独立 Bernoull 激励下的连续求值。

## 8. 依据

- `XiangShan/src/main/scala/xiangshan/mem/pipeline/NewStoreUnit.scala:76-126`（仲裁源与优先级注释）
- `XiangShan/src/main/scala/xiangshan/mem/MemBlock.scala:85-96`（`arbiter` 封装 = `chisel3.util.Arbiter`）
- `XiangShan/src/main/scala/xiangshan/mem/pipeline/package.scala:190-210`（`StoreEntrance` one-hot 编码）
- `soc-split/rtl/Arbiter3_StoreStageIO.sv`（固定生成 RTL，本 DUT）
- `soc-split/rtl/StoreUnitS0.sv:348-440`（父块实际连线与常量折叠）
