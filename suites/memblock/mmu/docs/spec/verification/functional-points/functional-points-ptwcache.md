# PtwCache 独立叶级功能点

> 本文为既有功能点清单，不代表 sampled bins 或旧 PASS 已证明所有语义。
> 当前 checker/归因限制与误报修正见 `reports/verification-soundness-20261025.md`。


DUT：`PtwCache`（`rtl/ptwcache`，13 文件真实闭包），最终 run
`ptwcache-final-02`，50 用例 PASS。功能点按微架构语义描述，不按端口/信号罗列。

| ID | 功能点 | 微架构语义与关键行为 | 对应用例 |
|---|---|---|---|
| PC-01 | 4KB sector 回填与命中 | L0 按 `VPN[37:3]` 存一个 8-PTE sector；命中时按 `VPN[2:0]` 选出 PTE lane，返回 `hit=1`、`not_super=1`、level 0、tag、way、pteidx 与 `hitway`。 | `test_l0_hit_payload`、`test_l0_sector_selection`、`test_l0_sets_ways_sweep` |
| PC-02 | sector 载荷一致性 | 每个 lane 的 PPN 高位/低位、R/W/X/U/G、A/D、PBMT、prefetch 从回填 PTE 原样返回；`ppn_low` 与 `pteidx` 对齐；noS2 的 page-fault-only 条目以 `v=0,pf=1` 命中。 | `test_l0_sector_selection`、`test_pbmt_and_perms`、`test_fault_entry_caching` |
| PC-03 | 非叶 PTE 层级缓存 | L1 缓存非叶 PTE（4 set × 2 way，sector 索引 `VPN[11:9]`）；L2/L3 为 16 项全相联；命中通过 `l1Hit/l2Hit/l3Hit` 与 `toFsm.ppn` 给出下一级页表基址，不返回最终 leaf 的 `hit`。 | `test_l1_nonleaf_hit`、`test_l2_nonleaf_hit`、`test_l3_nonleaf_hit`、`test_l1_two_ways`、`test_l2_l3_fill_and_sweep` |
| PC-04 | 超级页合并 | 2MB/1GB/512GB leaf 存入 SP 路；命中返回 `not_super=0`、对应 level、`ppn>>3` 与 `ppn_low`；SP 共 16 项，按超级页粒度比较 tag。 | `test_sp_2m_hit`、`test_sp_1g_hit`、`test_sp_512g_hit`、`test_sp_fill_and_sweep` |
| PC-05 | 64KB NAPOT | `n=1` 且 `PPN[3:0]=4'b1000` 的 level-0 leaf 不进 L0，而进 SP；其 64KB 范围内的 16 个 4KB VPN 全部命中，相邻 64KB 区间不别名。 | `test_napot_64k_hit` |
| PC-06 | 上下文过滤 | noS2 用 satp.ASID；onlyStage1 用 vsatp.ASID 且仍检查 VMID；onlyStage2 忽略 ASID、检查 VMID；allStage 以 onlyStage1 上下文查 S1 缓存；全局 PTE 的 G 位跨 ASID 命中。 | `test_asid_filtering`、`test_only_stage1_asid`、`test_only_stage2_vmid`、`test_allstage_stage1_hit` |
| PC-07 | allStage 的 S1 命中/故障语义 | allStage 查找 L0/SP 命中但 S1 有效时只报 `stage1Hit=1`、最终 `hit=0`；S1 无效的 pf-only 条目按 `stage1Pf` 返回 `hit=1,pf=1`；allStage 对无效 S1 PTE 不缓存。 | `test_allstage_stage1_hit`、`test_fault_entry_caching`、`test_invalid_per_stage` |
| PC-08 | 缺失与同拍回填旁路 | 空缓存查询返回 `hit=0`；回填完成后同一 VPN 命中；请求在途时遇到同 VPN 回填，响应置 `bypassed=1` 且不误报 hit。 | `test_miss_then_refill_hit`、`test_refill_bypass` |
| PC-09 | 预取标志 | 回填 source 为 prefetch 时，命中响应 `prefetch=1`；L0/SP/L1 三种来源都保持该语义。 | `test_prefetch_flag`、`test_prefetch_levels` |
| PC-10 | HPTW 响应路径 | `isHptwReq` 透传；HPTW 查询返回 `toHptw.id/tag/level/ppn`、L1/L2/L3 命中提示；L0/SP 命中时 `toHptw.resp.entry` 取对应条目；`gpf` 由条目 v 取反；onlyStage2 上游只从 `toHptw` 观察高层命中。 | `test_hptw_path`、`test_hptw_upper_levels`、`test_hfenceg_all_levels` |
| PC-11 | bitmap 跳转 | `BME=1,CMODE=0` 时 L0/SP 命中转成 `jmp_bitmap_check=1`，返回 8 个 PTE、cfs、hitway、SPlevel；noS2/onlyS1 置 `toLLPTW=1`；allStage 的 S1 查询不跳，HPTW 查询跳。 | `test_bitmap_jump`、`test_bitmap_allstage` |
| PC-12 | bitmap wakeup | wakeup 的 set/way/pte_index/check_success 更新对应 sector 的 cf；allStage 使用 onlyStage1 上下文过滤；全部 64×4×8 个 bitmap 位可双向写入。 | `test_bitmap_wakeup_update`、`test_bitmap_wakeup_allstage`、`test_bitmap_reg_exhaustive` |
| PC-13 | 失效语义 | 普通 sfence 支持全清、按 ASID、按地址、按地址+ASID；L0 按 set 掩码与 hash tag 精确失效；SP 按超级页范围失效；hfence.v 清 h=1 条目，hfence.g 清 h=2 条目，并支持地址/ASID/VMID 作用域；虚拟模式使用 vsatp 上下文。 | `test_full_sfence`、`test_scoped_sfence`、`test_hfence_paths`、`test_hfencev_all_levels`、`test_hfenceg_all_levels`、`test_virt_sfence_all_levels`、`test_hfence_scope_variants`、`test_flush_mask_sweep` |
| PC-14 | 容量与替换 | L0 64 set × 4 way 全部可写、可命中，第 5 个 tag 触发单路替换；L1 4×2、L2/L3/SP 16 项均能并存并在回扫时全部命中。 | `test_l0_ways_and_sets`、`test_l0_all_ways_all_sets`、`test_l1_two_ways`、`test_l2_l3_capacity`、`test_sp_capacity`、`test_l2_l3_fill_and_sweep`、`test_sp_fill_and_sweep` |
| PC-15 | 响应握手与流水 | `resp.ready=0` 时 valid/payload 保持；连续两个 outstanding 按序返回；输出长时间阻塞时回读路径改用寄存的 RAM 数据（不使用单拍旁路），数据仍正确。 | `test_resp_backpressure`、`test_pipeline_stall_ram_fallback` |
| PC-16 | 请求上下文透传与数据极值 | vpn/s2xlate/source/isFirst/isHptwReq/hptwId 原样返回；isFirst=0 保持；CSR/输入全 0/全 1 不产生异常状态；五类存储在零/全 1 字段极性下均能正确读写。 | `test_is_first_passthrough`、`test_bit_sweep`、`test_field_polarity_sweep` |

## 覆盖与缺口

- 功能覆盖：100%（44 个 sample；event 14 bins、level 0..3、stage 0..3 全满）。
- 行覆盖：13741/13748（99.949%）。剩余 7 行为 3 条 SRAM `respReg` 复位分支
  （时钟门控导致复位沿不进入宏）和 4 条 L3 优先 mux 的声明式分支，均非功能状态。
- branch：3179/3226。剩余 47 项为 L3 one-hot 优先 mux 结构、MBIST/DFT 选择、
  SRAM/时间零 initial 结构，不需要新的功能点。
- toggle：87398/110892（78.814%）。剩余项按 §5 分类，主要为 MBIST、SRAM 宏、
  Picker harness、initial 随机状态，以及全相联 way 放置/哈希向量带来的数据极性缺口；
  已用 `test_field_polarity_sweep` 对 L0/L1/L2/L3/SP 做零/全 1 极性回填与回读。
