# BankedDataArray 功能点

DUT：`BankedDataArray`（`soc-split/rtl/BankedDataArray.sv`，源码
`xiangshan/cache/dcache/data/BankedDataArray.scala`），层次：DCache 数据阵列中层。
生成配置：32 bank × 4 way × 16-bit 行，2 个 16B vword / 64B line，单写端口 + 32 个
per-bank 复制写端口，3 个 load 读端口 + 1 个整线读端口，data ECC 开启。

地址函数（modeId=1，来自 `DCacheWrapper.scala` 的
`DCacheBankOffset=log2Up(DCacheSRAMRowBytes)=1`、`DCacheSetOffset=6`）：

- bank = `addr[5:1]`（32 个 2B 行，**不是** `addr[10:6]`）
- div = 0（`DCacheSetDiv=1`）
- set = hash(addr[47:12]) 与 `addr[11:6]` 拼接后取 8 bit
- 读端口的 8 个返回 bank 从 `bankBase = bank(addr) & ~7` 开始连续 8 个；
  `bankMask` 按**绝对 bank 号**索引，不是窗口内偏移
- bank 0..15 的读地址取自 `addr_dup`（duplicated query），16..31 取自 `addr`

## BDA-FP-001 读端口 bank 选择与返回窗口

每个 read 端口的 `bankMask[31:0]` 逐 bank 选择是否读该 bank；返回的
`read_resp_i[j]` 是 `bankBase + j`（j=0..7）这 8 个连续 bank 在 `way_en` 选中 way 上的
16-bit 原始数据。未在 bankMask 中置位的 bank 保持上一次读出的值。3 个读端口相互独立。

## BDA-FP-002 32 bank × 4 way 独立存储

写入的 32 个 16-bit 行分别落到 32 个 bank；每个 bank 内 4 个 way 独立。任意
(bank, way) 组合的写入不影响其它 bank/way，读回值与写入值逐位一致。

## BDA-FP-003 写掩码与 per-bank 复制写端口

一次写请求由 `wmask[31:0]` 选择 bank，且每个 bank 还需要其 `write_dup_i_valid=1` 才
真正写入；`write_dup_i_bits_way_en` 选择 way，`write_dup_i_bits_addr` 给出该 bank 的
set 地址。wmask=0 或 dup valid=0 的 bank 保持原值。

## BDA-FP-004 写后读可见性

写请求在下一时钟沿提交；提交前的读看到旧值，提交后的读看到新值。写请求与读同拍时
读端口按单端口 SRAM 约束处理（ready/冲突信号）。

## BDA-FP-005 整线读（readline）与输出保持

`readline` 读 32 个 bank 的同一 way（`way_en` 单 hot），`rmask` 逐 bank 选择；
`readline` fire 后一拍，在 `can_go=1` 且 `can_resp=1` 时把 32 个 bank 的数据打入
`readline_resp`；`can_go=0` 且 `stall=1` 时保持上次结果。`readline_error_delayed`
在整线数据 ECC 正确时为 0。

## BDA-FP-006 读-读 bank 冲突

两个读端口同拍、同一 div、bankMask 有交集、set 不同且 lqIdx 不同的请求构成 rr bank
conflict。按 lqIdx 最老（数值最小）的端口获胜；失败端口在下一拍
`rr_bank_conflict_slow=1` 且 `bank_conflict_slow=1`，供 LoadPipe replay。ready 不受影响。

## BDA-FP-007 读-线 / 写-读冲突

读与 readline 在相同 div、rmask 与 bankMask 有交集且 set 不同时，读端口下一拍
`bank_conflict_slow=1`。`readline` 与已寄存的写请求在相同 div 且 wmask 与 rmask 有
交集时 `readline.ready=0`。写请求有效后的下一拍，重叠的读端口 `ready=0`。

## BDA-FP-008 data ECC：码字生成、伪错误注入与错误标志观测

功能写入时硬件对每个 16-bit bank 行生成 SECDED 码。本功能点验证三件事：

1. **功能数据往返**：任意 bank/way 写入后读回的 16-bit 原始数据逐位一致
   （ECC 编解码不破坏数据通路）。
2. **伪错误注入**：`io_pseudo_error_0_mask/valid` 按 bank 异或被测数据，读出的
   `read_resp` 等于 `原值 XOR mask`；注入断言到所有 32 bank 与多种 mask 形态。
3. **错误标志的可观测性**：`read_error_delayed_<port>_<j>` 与
   `readline_error_delayed` 在两拍后反映所选 bank 的 SECDED 解码结果。对**经编码
   写路径写入**的行，解码必须无错（`error_delayed=0`），读结束后保持 0。

未写过的 SRAM 行内容是随机的（数据与 ECC 无对应关系），读出时 `error_delayed=1`
是 ECC 的正常检测结果，不是缺陷。因此任何读之前必须先用编码写路径初始化目标
set/way（用例统一 `prime`）。原 `BDA-ECC-DELAYED-FLAG` 告警即由此产生，已关闭。

- 情形：单 bank/全 bank 注入、mask=0xFFFF/0xA5A5/0、写零后读回无错、读结束后标
  志回 0。

## 覆盖组

- `bda.read`：端口 0..2、bankMask 形态、way、bankBase 区间、bank 槽位。
- `bda.write`：wmask 形态、dup valid 掩码、way、bank 槽位。
- `bda.line`：整线读 way、rmask 形态、can_go/stall 保持。
- `bda.conflict`：rr 冲突胜者/败者、读线冲突、写读冲突。
- `bda.ecc`：功能数据往返、伪错误注入按位生效、已写行无错、读结束后标志回 0。
