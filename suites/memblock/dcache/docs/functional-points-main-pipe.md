# MainPipe 功能点（本轮 UT 范围）

DUT：`MainPipe`（`soc-split/rtl/MainPipe.sv`），层次：DCache store/atomic 主流水 +
refill 安装 + probe 降级。端口包括 Sbuffer store 请求、LSU atomic 请求、probe 请求、
MissQueue refill 请求、tag/meta/bank-data 访问、store/atomic/probe 响应、C 通道
writeback 和错误标记。

MainPipe 是 4 级流水：S0 接收请求并发出 tag/meta 读；S1 比较 tag、读取行数据；
S2 对 miss 产生 miss 请求（或对 store 产生 replay），S3 完成 tag/meta/data 写和响应。
本 UT 直接驱动公开端口，用 64B 行模型核对 store 合并、refill 安装和 AMO 结果；
LR/SC 保留集、ECC 伪错误注入、`tl_error` 的错误来源细分不纳入本轮。

## MP-FP-001 store 命中写回

store 请求在 S0 接收，tag/meta 读 index 等于 `get_dcache_idx(vaddr)`。命中时
（tag 匹配且该 way 的 coh 有写权限）S3 产生 `data_write`：`wmask` 标出被掩码覆盖的
bank，bank 内数据按字节与 SRAM 原数据合并；`store_hit_resp.valid=1` 并带回 `id`。
命中不写 tag；`meta_write` 只在 coh 变化时产生（Trunk→Dirty）。

## MP-FP-002 store 字节掩码形态

mask 按行内字节编码，每 bank 对应 2 bit。S1 是否需要读行的判据是
`bank_write & ~bank_full_write`：**每个被写的 bank 都整体覆盖时不读行**
（例如低 8 字节、任意对齐的整 8B 字、或整行 64B 全 1）；只要有一个被写 bank
是部分覆盖（如单字节写），S1 就发起 `data_readline`，`rmask` 只覆盖这些未整
bank 覆盖的 bank，S3 用读回的旧行数据保留未掩码字节。

## MP-FP-003 store miss 与 MSHR 接收

tag 不匹配或 coh 无权限时，S2 产生 `miss_req`：`addr` 为 64B 对齐物理地址、
`vaddr` 保留虚拟地址、`store_data`/`store_mask` 透传、`source=STORE_SOURCE`、
`cmd=M_XWR`、`id` 透传。整行 store mask 全 1 时 `full_overwrite=1`。
miss 被 MissQueue 接收后，S3 仍给 Sbuffer 一个 `store_hit_resp`，其 `miss=1`
表示该 store 由 MSHR 接管。

## MP-FP-004 store replay

MissQueue 未 ready（或 WBQ 阻塞 miss 请求）时，S2 产生 `store_replay_resp`
（`replay=1`、`miss=1`、带回 `id`），请求留在 Sbuffer 重试；此时不产生
`store_hit_resp`。

## MP-FP-005 AMO 读-改-写

atomic 请求在 S1 读行，S2 用该 8 字节字的 SRAM 原值送到 AMOALU，S3 返回
`atomic_resp`：`data` 是包含目标字的 16B 窗口（word_idx 对应的 8 个 bank），
同时 `data_write` 写回 ALU 结果。写回按 bank 掩码进行：整字操作写 4 个 bank，
部分字节操作仍覆盖该字所在 bank，未掩码字节保留原值。AMO 命中时的响应
`miss=0`、`replay=0`。

## MP-FP-006 AMO miss 与反压

AMO miss 时 `miss_req` 携带 `amo_data`/`amo_mask`/`amo_cmp`/`word_idx` 以及
addr/vaddr，由 MissQueue 发起原子操作。**被接收的 AMO miss 当拍不返回
`atomic_resp`**：LSU 只在 miss 完成（refill 数据回到 MainPipe、S3 执行 ALU 并写回）
后收到唯一一次响应，此时 `miss=0`、`data` 为操作前的 16B 窗口。

MissQueue 反压（`io_miss_req_ready=0` 或 WBQ 阻塞）时走 replay 路径：
`atomic_resp.valid=1`、`miss=1`、`replay=1`、`data=0`，由上层重试。
在本 RTL 中 `atomic_resp.miss` 与 `atomic_resp.replay` 同源（都等于
`atomic_replay_resp_valid`），因此“miss=1 且 replay=0 的 AMO 响应”不会出现。

## MP-FP-007 probe 权限降级

probe 命中时按 `probe_param`（toT/toB/toN）把 coh 降到 Trunk/Branch/Nothing，
并在 S3 产生 C 通道 `wb`：`param` 为 TtoT/TtoB/TtoN，`addr` 为块地址，
`voluntary=0`。脏行降级时 `hasData=1`，`data` 是整行 512-bit 数据；
`probe_need_data=1` 时即使干净也带数据。`meta_write` 只在 coh 实际变化时产生，
并把 `way_en` 指向命中 way。

## MP-FP-008 probe miss

probe 的 tag 不匹配时，缓存中没有任何行需要降级：不产生 `meta_write`，
`wb` 以 NtoN 报告返回且 `hasData=0`。

## MP-FP-009 refill 安装

MissQueue 的 refill 请求在 S0 接收，S2 采样 `refill_info`（整行数据 + 全 1 掩码 +
grant param），S3 同时写 tag/data/meta：`tag_write` 的 tag 为 `paddr[47:12]`、
`way_en` 来自 replacer 选中的 way、`idx` 为 set；`data_write.wmask` 覆盖全部 bank，
数据为 MissQueue 提供的整行；`meta_write` 的新 coh 由 cmd/grant 决定（load refill
安装为 Trunk，store refill 安装为 Dirty）。S3 同时输出 `mainpipe_info.s3_refill_resp=1`
供 MissQueue 释放 MSHR，并写 access/prefetch/latency flag。

## MP-FP-010 refill 错误标记

`refill_info.error.tl_denied` / `tl_corrupt` 置位时，S3 在写 meta 的同时写
`error_flag_write`（denied/corrupt 原样传递），并向 BEU 方向产生一拍
`io_error.valid`（`report_to_beu=0`，因为不是 tag/data ECC 错误）。refill 即使
无错误也会写 error flag（错误位为 0），用于清除该 way 的历史错误标记。

## MP-FP-011 prefetch 路径

prefetch 命中时只更新 access flag，不写 tag/data。prefetch miss 以
`source=PREFETCH_SOURCE`、`cmd=M_PFR`、`pf_source=来源编号` 进入 MissQueue；
对应的 refill 安装时把来源编号写入 `prefetch_flag_write`，`access` 字段写入
access flag。

## MP-FP-012 地址分解与 way 选择

tag/meta 读 index 使用 `get_dcache_idx(vaddr)`（hash(vaddr[47:12]) 与
vaddr[11:6] 拼接）。refill 时向 replacer 发出 `replace_access`（set 为读 index、
way 为候选 way），并用 `replace_way` 作为最终 `way_en`；store/AMO 命中时
`way_en` 为命中 way 的 one-hot。地址覆盖 set 0/低位/高位/255 与 way 0..3。

## MP-FP-013 LR/SC 保留集

`M_XLR` 命中时返回该字的 16B 窗口数据、不写数据，并在 S3 后把块地址写入
`lrsc_locked_block`（`valid=1`），随后 `block_lr=1` 阻止 probe；`M_XSC` 只有在该块
地址仍与保留集匹配时才写回（4 bank 字、按 `amo_mask` 合并未掩码字节），写成功后
保留集清除。保留集不匹配或经 `invalid_resv_set` 清除后，SC 仍返回响应但不写数据。

## MP-FP-014 AMO compare-and-swap

`M_XA_CASB/H/W/D/Q` 在 S1 读取目标宽度（1/2/4/8/16 字节）的原值，与 `amo_cmp`
比较：相等时把 `amo_data` 写入对应 bank（B/H/W/D 仍按 bank 对齐写该字所在的
4 bank，未覆盖字节保留原值；Q 覆盖 16B 窗口），不相等时不产生 `data_write`。
`atomic_resp.data` 始终返回比较前的窗口数据，因此调用方可据此判断成功与否。

## MP-FP-015 Branch→Trunk 权限增长与 BtoT 占满阻塞

store 命中 Branch 行时权限不足，按 BtoT 增长处理：`miss_req.isBtoT=1`，并把
`mainpipe_info.s2_next_evict_way` 指向该 set 中最低的空闲（非 BtoT）way 供 refill
使用。若该 set 已有 3 个及以上 BtoT way，增长被拒绝：`miss_req.cancel=1`，
同时产生 `store_replay_resp`，由 Sbuffer 重试而不是把请求交给 MSHR。

## MP-FP-016 extra meta（flag）错误上报

tag 命中 way 的 `extra_meta.error`（prefetch/access 标志区的 denied/corrupt）
在 S2 汇入 `s2_error`，S3 产生一拍 `io_error.valid`；`report_to_beu=0`（不是
tag/data ECC 错误），probe 仍完成降级/写回。

## MP-FP-017 tag/data ECC 错误上报

tag 读回码字 ECC 错误时不视为命中：probe 按 miss 返回 NtoN、`wb.corrupt=1`；
bank data 的 `readline_error_delayed` 使写回行带 `corrupt=1`。两种错误都产生
`io_error.valid` 且 `report_to_beu=1`（BEU 路径），paddr 为块地址。

## MP-FP-018 同 set 连续请求与 skid buffer

同一 set 的连续 store 在 S0/S1/S2/S3 存在 set 冲突时，`store_req_ready` 会被拉低，
第二个请求停留在 skid buffer，待流水空出后按序接受；两次写回的 `id`、tag/meta
索引都对应各自请求。

## 未纳入本轮范围

- tag/data ECC 伪错误注入寄存器（`pseudo_*`）的注入时序；
- `tl_error` 在 refill 后对 `atomic_resp`/`store_hit_resp` 的注入时序；
- `sms`/`bloom_filter` 预取请求、`replace_block` 专用替换路径；
- 与 WBQ/MissQueue 的真实跨模块握手（由 DCache 顶层用例覆盖）。
