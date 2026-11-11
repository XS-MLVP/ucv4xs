# LoadPipe 功能点（本轮 UT 范围）

DUT：`LoadPipe`（`soc-split/rtl/LoadPipe.sv`），层次：DCache 3 级 load 流水。
端口包括 LSU 请求、tag/meta/bank-data 读接口、S2 响应、miss 请求、冲突与 speculative
miss 接口。本 UT 先覆盖“请求—tag/meta/data—S2 结果—miss 请求”的主数据通路与握手；
WPU 预测、prefetch 标记、ECC 错误注入等旁路在报告中明确列出未纳入本轮范围。

## LP-FP-001 请求接收与三级流水时序

`io_lsu_req` 在 S0 接收（`req_ready` 有效时），同一拍发出 tag/meta 读和 bank data 读；
响应在 S1 采样；S2 输出 data/miss/handled。S0→S2 固定两拍，`req_ready` 在 S1 占用时
反压。

## LP-FP-002 地址分解

tag/meta 读 index 等于 `get_dcache_idx(vaddr)`（modeId=1：hash(vaddr[47:12]) 与
vaddr[11:6] 拼接）。miss 请求的 `addr` 是 64B 对齐的物理地址，`vaddr` 保留虚拟地址。

## LP-FP-003 命中与响应数据

S1 用 `tag_resp` 与 paddr tag 比较、并要求对应 way 的 coh_state 有效。S2 的
`resp.miss = !real_way_en`，即没有任何 tag 匹配就报 miss；命中时 `resp.data` 是
8 个 16-bit bank 原始数据按 bank0→bank7 拼接的 128-bit 值。`banked_data_read.way_en`
是命中 way 的 one-hot。

## LP-FP-004 miss 请求与抑制/确认

miss 时 `io_miss_req.valid=1`，携带 source/cmd/block addr/vaddr/vaddrSet/vaddrAlias/
coh/occupy_way/cancel/isSpecMiss。`mshr_full` 只抑制 speculative 预留，不抑制普通
miss 请求；`wbq_block_miss_req` 不抑制请求本身，但会让 `handled=0`；
`miss_resp.handled=1` 且请求被 miss queue 接收时 `resp.handled=1`，否则上层需 replay。
`resp.mshr_id` 直接来自 `io_miss_resp_id`。

## LP-FP-005 kill

`s1_kill` 在 S1 丢弃请求（不进入 S2），`s2_kill` 取消 S2 的 miss 请求。S2 响应字段
没有 valid 端口，因此验证以“kill 后不产生新的 miss 请求/不更新 mtrack”为准；
本 UT 只覆盖 S1 kill 下不出现错误 miss 的形态。

## LP-FP-006 bank 冲突

`bank_conflict_slow` 在 S2 反映为 `io_lsu_s2_bank_conflict=1`，
`rr_bank_conflict_slow` 反映为 `io_lsu_s2_rr_bank_conflict=1`，用于上层 replay。

## LP-FP-007 掩码与 load128

普通 load 的 `bankMask` 由 `vaddr` 与字节 mask 决定；`load128Req=1` 时强制覆盖整个
16B vword（bank 掩码扩大）。`lqIdx` 透传到 bank data 读请求。

## LP-FP-008 speculative miss

`specmiss.valid && candidate` 在 S1 申请预留；只有 `spec_query_grant_valid` 到达后
S2 才把 `miss_req.isSpecMiss` 置 1。未获得预留的 speculative 候选不会产生带
`isSpecMiss` 的 miss 请求。

## 未纳入本轮范围

- WPU（`io.dwpu`）预测/回写、`wpu_pred_fail` replay；
- prefetch（`instrtype=DCACHE_PREFETCH_SOURCE`）的 flag/access/latency 更新；
- tag/data ECC 伪错误注入与 `io_pseudo_error_*`；
- 3 条 LoadPipe 之间的 bank 仲裁（属于 BankedDataArray/DCache 顶层）。
