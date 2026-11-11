# DCache 顶层功能点

DUT：`DCache`（`soc-split/rtl/DCache.sv`），64KB、256 set × 4 way、2 个 L2 通道、
3 条 load 流水、store/atomic 主流水、MissQueue/ProbeQueue/WritebackQueue 与
tag/meta/data 阵列全部内联。

## DC-FP-001 复位与 SRAM 清扫

复位释放后 tag/meta SRAM 以 256 拍逐 set 清零；在清扫完成前不得发起功能事务。
验证流程固定等待 300 拍后再发请求。

## DC-FP-002 load 命中与响应

load 在 S0 接收（`req_ready`），S2 给出 `data/miss/handled/mshr_id`；命中时
`data` 为 16B 对齐窗口的原始数据，miss=0。3 条 load 流水可独立、也可同拍访问同一行。

**响应窗口的掩码契约**（决定用例怎么比对数据）：数据阵列只刷新 `bankMask` 选中的
bank，`bankMask = byteMaskToBankMask(vaddr, mask)`，即 8-bit 字节掩码每 2 bit 对应一
个 2 字节 bank。响应是 **16B 对齐窗口**，被刷新的字节保持其在窗口内的**原始偏移**，
未被选中的 bank 保留上一次读锁存的值。

因此一条 64-bit load 的 128-bit 响应里，只有 `addr & 0xF` 起始的 8 个字节是本次读
出的；同窗口另 8 字节是陈旧值，不属于合同。128-bit load（`is128Req`）才读满 16B。

用例一律用 `window_bytes()` 只比对被覆盖的字节，不假设整个窗口新鲜。这里踩过两个坑：
(a) 全 128-bit 比较只有在“上一次读恰好是同一窗口”时才偶然通过；
(b) 曾把“掩码只影响 LSU 消费、响应总是整窗新鲜”写进注释，与 RTL 相反。

## DC-FP-003 冷 miss 与 refill

冷 load 产生 `miss=1, handled=1`，DCache 在对应 L2 通道发出
`AcquireBlock`（opcode 6，size 6，地址为 64B 对齐 paddr，grow=NtoB）。
整行覆盖的 store miss 则发 `AcquirePerm`（opcode 7，grow=NtoT）；部分掩码
store miss 仍走 `AcquireBlock`。L2 用 2 个 `GrantData`（opcode 5，size 6）beat
回应；refill 完成后同一行重放 load 命中，数据与 refill beat 拼接一致。

## DC-FP-004 硬件预取装入与 prefetch 标记清除

DCache 有独立的预取请求端口 `io_prefetch_req`（paddr/vaddr/pf_source，MainPipe 的
`convertPrefetchReq` 把它转成 MainPipe 请求并参与 S0 仲裁）。`pf_source` 编码来自
`L1PrefetchInterface`：0 = NULL、1 = CLEAR、2 = STRIDE、3 = STREAM、4 = STORE、
5 = BERTI；`isFromL1Prefetch(v) = v > 1`。

- 预取请求走与 load 相同的 miss/refill 路径，装入的行在 `L1PrefetchSourceArray` 中
  记录该 `pf_source`。
- **标记清除**：一笔非预取的 demand load 命中带预取标记的行时，LoadPipe 触发
  `prefetch_flag_write`（`s3_clear_pf_flag_en = s3_valid && s3_hit && !s3_is_prefetch
  && !s3_kill && isFromL1Prefetch(s3_hit_prefetch)`，且 `counter_filter_query.resp=0`），
  在 `L1PrefetchSourceArray` 写入 `L1_HW_PREFETCH_CLEAR`。

**三个容易写错的期望（实测契约）**：

1. 清除后的值是 **`L1_HW_PREFETCH_CLEAR = 1`，不是 0**。编码为
   0=NULL、1=CLEAR、2=STRIDE、3=STREAM、4=STORE、5=BERTI；
   `isDemand(v) = v <= 1`，所以 1 表示"曾是预取、已被 demand 清过"。
2. **执行清除的那一次命中仍然观察到旧值**（响应在 S1/S2 采样，清除写发生在 S3）；
   下一次命中才看到 1。
3. 清 **受 CounterFilter 抑制**：同一 line 在 4 拍过滤窗内的重复 demand 访问不会重复
   清除（`counter_filter_query.resp=1` 时 `prefetch_flag_write.valid=0`）。因此用例
   在两次 demand 访问之间留出窗口，否则会观察到仍是 2。

观测点：`io_lsu_load_*_resp_bits_meta_prefetch` 直接回显命中行的预取来源，因此
这一功能点是**端口直接可观察**的，不依赖覆盖率推断。
- `L1RefillLatencyArray` 记录预取行首次被 demand 访问的延迟，由
  `MainPipe.io.refill_info.refill_latency` 提供，仅在 `isFromL1Prefetch(s2_req.pf_source)`
  时写入。

**为什么它曾经是覆盖率缺口**：load 端口不带 `pf_source`（LSU 侧折叠掉），只有
`io_prefetch_req` 能装入带标记的行。验证时对 256 set × 4 way 各做一次
"`io_prefetch_req`(pf_source=2) → refill → demand load 命中 → 清标记"，
即覆盖两张表全部 (set, way) 的写/读/清臂。

## DC-FP-005 替换与写回阻塞契约

一个 set 的 4 个 way 被占满后，访问同 set 的新 block 会替换其中一个 victim：victim
的 C 通道响应（脏行 `ReleaseData(7)`、干净行 `Release(6)`，均带原 param 与数据）在
该 block 所在通道发出。响应只在 `c_ready` 有效时推进。

**写回阻塞契约**：Release 未被接受（`c_ready=0`）时 WritebackQueue 仍占用该 block，
MissQueue 通过 `io_block_miss_req` 拒绝为同一 block 分配新 MSHR：load 返回
`miss=1, handled=0`，store 返回 `replay=1`，由 LSU 重试。C 通道放行并收到
`ReleaseAck`（D 通道 opcode 6，source 为该 release 的 source）后，同一 block 的 miss
立即恢复 `handled=1`。阻塞是 block 级、暂时的，不是永久拒绝。

## DC-FP-006 双通道选择

Acquire 通道由 `paddr[6]` 选择；两个通道都能独立完成 Acquire/Grant 并回填。

## DC-FP-007 store 主流水

store 在 `io_lsu_store_req` 接收，主流水返回 hit 或 replay；命中后数据写入 data
array 并更新 tag。load 读回看到按 64-bit 字节掩码合并后的数据。store miss 时：
整行覆盖（`full_overwrite`）用 `AcquirePerm`，refill 行由 store 数据构成；
部分掩码沿 `AcquireBlock` 路径，由 MissQueue 把 L2 整行与 store 掩码字节合并后
安装。

**已知缺陷（`MQ-STORE-MERGE-DATA-PENDING`）**：同一行连续两笔部分 store 时，第二笔
虽然被受理（`store_main_pipe_hit_resp.valid=1`、无第二次 Acquire），其字节不会进入
refill 行。实测 store1 写 byte0=0xAA、store2 写 byte1=0xBB 后，安装行是 0x00AA
而不是 0xBBAA（byte1 被 0x00 覆盖，L2 原来的 0x01 也丢失）。用例
`test_two_partial_stores_same_missing_line_merge_data` 以严格 expected-failure
固化该行为；修复后会自动提示重新打开。

## DC-FP-008 miss 池耗尽

MSHR 共 16 项。连续发起不同行的 load miss 直到占满后，后续 load miss 返回
`handled=0`（需要 replay），不再产生新的 miss 请求；被占满期间 store 走
`store_replay_resp`。用例按“一直发到第一次 `handled=0`”判定，不假定具体条数。

## DC-FP-009 refill 错误

`GrantData` 的 denied/corrupt 通过 refill 路径上报 `io_error`。错误地址字段的语义是
`Cat(s2_tag, get_untag(vaddr))`（MainPipe.scala:682）：对冷行 tag 仍为 0，因此
`io_error.paddr == vaddr[11:0]`；页对齐地址会退化为 0。`report_to_beu` 只对
tag/data ECC 错误置 1，L2 denied/corrupt 时为 0，BEU 不消费该 paddr。用例
`test_denied_refill_error_paddr_is_vaddr_low_bits` 固化该契约。

## DC-FP-010 probe

B 通道 probe 在缓存行上得到 C 通道 `ProbeAck`（opcode 4）或 `ProbeAckData`（5），
地址回显。

## DC-FP-011 dirty/clean victim 的 C 通道写回

同一个 set 的 4 个 way 被填满后，第 5 个同 set 行的 miss 触发替换：被替换的
victim 若为 Dirty，DCache 必须在 refill 期间发出 C 通道 `ReleaseData`
（opcode 7，param TtoN，地址为 victim 块地址，数据为整行）；若为干净行则发
`Release`（opcode 6，param TtoN，无数据）。替换完成后被逐出的块不再命中。

## DC-FP-012 AMO 读-改-写

`io_lsu_atomics_req` 的 swap/add 在命中时返回目标字所在 16B 窗口的旧数据，
并把结果写回 data array；随后 load 读到新值。AMO miss 先进入 MissQueue，refill
完成后由 MainPipe 完成 ALU 写回并返回旧值，LSU 只看到一次 `resp_valid`。

## DC-FP-013 CMO

`io_cmoOpReq` 的 clean/flush/inval（0/1/2）映射为 A 通道 opcode 12/13/14，
按块地址 bit6 选 L2 通道；D 通道 `CBOAck` 的 denied/corrupt 在 `io_cmoOpResp`
回传，之后可继续接受下一个 CMO。

## 覆盖组

- `dcache.load`：命中 / miss-handled / miss-unhandled × 3 lane × 掩码形态。
- `dcache.miss`：通道 × refill 结果（clean/denied/corrupt）与 refill 后结果。
- `dcache.store`：hit/replay/none × 掩码形态。
- `dcache.control`：reset sweep、lqEmpty、denied error。
- `dcache.eviction`：dirty/clean victim × C 通道 Release（带/不带数据）。
- `dcache.atomic`：swap/add × 命中/miss-完成。
- `dcache.cmo`：clean/flush/inval × 响应状态。
