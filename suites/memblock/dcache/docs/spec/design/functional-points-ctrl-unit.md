# CtrlUnit 功能点

DUT：`CtrlUnit`（`soc-split/rtl/CtrlUnit.sv`），层次：DCache 控制叶块。它是
`TLRegisterNode` 背后的伪错误注入控制器：一个 64-bit 控制寄存器、一个 64-bit 延迟
寄存器、一个 40-bit tag mask 寄存器、8 组 × 4 bank 的 16-bit data mask 寄存器，以及
两条单级流水（tag 组件、data 组件）。

寄存器映射（A 通道地址低 4 位 → 内部 index，基址由 DCache 的 cacheCtrl 地址集决定）：

| 偏移 | 内容 |
|---|---|
| 0x00 | ctrl：bit0 ese、bit1 persist、bit2 ede、bit3 comp、bit[35:4] bank |
| 0x08 | delay（同时加载 counter） |
| 0x10 | tag mask（只保留 40 bit，输出取低 36 bit） |
| 0x18 + 8×g | data mask 组 g，4 × 16-bit，依次对应 bank 4g..4g+3 |

## CU-FP-001 复位后的确定状态

复位清空 ctrl/delay/tagMask/dataMask/counter；两条注入流水无有效请求；读任意寄存器
偏移返回 0。复位释放后寄存器保持 0，直到软件写入。

## CU-FP-002 TileLink 寄存器访问协议

寄存器节点一次只接收一个事务：`a_ready = ~maybe_full`。A 通道握手后下一拍 `d_valid=1`，
写响应 opcode=AccessAck(0)，读响应 opcode=AccessAckData(1)，`d_bits_source`/`size`
回显请求值。写操作只在 D 通道握手时提交；D 未就绪时 A 通道不再接收新事务，寄存器
保持旧值。读数据在 `d_valid` 拍有效。

- 情形：立即 D 握手、D 反压后释放、反压期间再次发 A（被拒绝）。

## CU-FP-003 写掩码语义

ctrl/delay/tagMask 只有 8 个字节全部置位时才更新；data mask 组的每个 16-bit 半部要求
对应 2 个字节掩码同时置位，否则该半部保持旧值。部分掩码的写仍完成 TL 握手，但不改变
寄存器。

## CU-FP-004 控制位域与读回

`ese/persist/ede/comp/bank` 五个位域独立可写；读回 ctrl 得到当前值。tagMask 写入
40 bit、读回 40 bit；data mask 8 组 × 4 bank 的 16-bit 值可独立读回，互不串扰。

- 情形：单 bit 位域、全 1、全 0、随机的 bank 位图。

## CU-FP-005 tag 组件伪错误注入

`comp=0` 选择 tag 组件。**通道 valid 只由 `ese`、`comp` 与延迟条件决定，不看 bank
位图**；bank 只决定 payload 中 `bank[0].valid`（该组件只把 bank0 引出到 DCache）。
有效时 `mask = tagMask[35:0]`。流水寄存一拍后出现在 `io_pseudoError_0`。非 persist
模式在请求被流水捕获的那一拍清除 `ese`，因此只注入一次；之后即使消费者未接收，也不再
产生新请求。

因此 `bank[0]=0` 时仍会产生一次“通道 valid、payload 无效”的伪请求并消费掉 ese；
只有 `bank[0]=1` 才会真正打开该 bank 的错误注入。

- 情形：bank0=1、bank0=0（通道有效但 payload 无效）、mask 全 0/单 bit/全 1。

## CU-FP-006 data 组件伪错误注入

`comp=1` 选择 data 组件。32 个 bank 各自 `valid = bank[i]`，`mask = dataMask[i]`
零扩展到 36 bit。多 bank 置位时同拍呈现多个有效请求；未置位 bank 的 valid=0。通道
valid 同样只由 `ese`/`comp`/延迟决定，因此 bank=0 时会产生一次通道有效、全部 bank
payload 无效的请求并消费 ese。

- 情形：单 bank、两个 bank、多个 bank、32 bank 全选。

## CU-FP-007 持续注入

`persist=1` 时捕获请求后不清除 `ese`。每当流水被消费且组件仍被选中，下一拍产生新的
注入请求；无延迟时每拍一次，有延迟时按 `delay+1` 的周期重复。

## CU-FP-008 延迟注入

`ede=1` 时 counter 在编程（或上一次 fire）时加载 `delay`，每拍递减；counter 为 0 时
才允许注入。`delay=0` 立即注入；`delay>0` 的首次请求出现在编程后第 `delay+1` 个
时钟沿（含流水寄存一拍）。delay 寄存器写入同时加载 counter。

## CU-FP-009 消费者背压

`io_pseudoError_*_ready=0` 时请求在流水输出保持有效，mask 不变；消费者恢复 ready 后
该请求被消费。单次模式的 `ese` 已在捕获时清除，因此消费后不再有后续请求；persist
模式则在消费后按规则重发。

## 覆盖组

- `cu.access`：读写 opcode、11 个寄存器偏移、全/部分写掩码、D 通道立即/反压握手。
- `cu.regs`：寄存器类别与读回一致性。
- `cu.inject`：组件（tag/data）、bank 选择类别（none/single/multi/all）、延迟类别
  （0/1/small/large）、persist、消费者 ready、mask 形态。
- cross：组件 × bank 类别；延迟类别 × persist。
