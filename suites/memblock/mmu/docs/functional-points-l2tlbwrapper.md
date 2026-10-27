# L2TLBWrapper 组合层功能点

> 本文为既有功能点清单，不代表 sampled bins 或旧 PASS 已证明所有语义。
> 当前 checker/归因限制与误报修正见 `reports/verification-soundness-20261025.md`。


DUT：`L2TLBWrapper`（`rtl/l2tlbwrapper`，48 个 L2TLB 闭包文件 + wrapper 本体，
共 49 个真实 RTL 文件）。最终 run `l2tlbwrapper-final-05`，46 用例 PASS +
1 个 strict XFAIL。功能点描述的是“包装层把请求、响应、失效和性能事件
如何组织成对内部 L2TLB 的组合语义”，不是端口枚举。

| ID | 功能点 | 微架构语义与关键行为 | 对应用例 |
|---|---|---|---|
| W-01 | 透明翻译通路 | 包装层把两路 TLB 请求、四类 `s2xlate`、页表内存 A/D 通道和响应原样接到真实 L2TLB；1GB/2MB/4KB 结果与子块独立走表一致。 | `test_1g_leaf_through_real_walk`、`test_4k_page_through_level0_walk`、`test_2m_page_through_level1_walk`、`test_memory_image_4k_walk`、`test_only_stage1_uses_vsatp`、`test_only_stage2_uses_hgatp`、`test_all_stage_identity_gstage` |
| W-02 | 故障透明性 | 无效根 PTE、PBMT 未使能、保留位、2MB 未对齐、PMP 拒绝都经包装层返回与子块相同的 `pf/af/gpf/gaf`，不吞掉也不伪造故障。 | `test_invalid_root_pte_reports_fault`、`test_pbmt_without_enable_faults`、`test_misaligned_2m_leaf_faults`、`test_reserved_bits_fault`、`test_pmp_denied_access_fault`、`test_wrapper_pmp_denied` |
| W-03 | 页表缓存组合 | 包装层不改变 PtwCache 的命中/替换：相同 VPN 重放不再读内存；64 个 4KB 页覆盖全部 L0 set/lane 后可全部驻留并零内存读回放。 | `test_repeat_request_hits_pwt_cache`、`test_cache_resident_replays`、`test_shared_leaf_line_hits`、`test_many_translations`、`test_wrapper_64_page_working_set` |
| W-04 | 失效组合 | sfence 的全地址/按 ASID/按地址形式、走表中失效、`satp.changed + sfence` 均经包装层到达 L2TLB，并使后续请求重新走表。 | `test_sfence_forces_walk`、`test_sfence_during_walk`、`test_satp_change_with_sfence_rewalks`、`test_sfence_scoped_variants` |
| W-05 | 双端口与并发 | 端口 0/1 都能独立完成翻译；同一拍发起的两个端口请求都能被接收并分别返回。 | `test_second_port_translation`、`test_two_ports_same_cycle`、`test_two_4k_translations` |
| W-06 | 响应背压 | `resp.ready=0` 时 valid 与全部 payload 保持不变；释放后完成握手，包装层不引入组合毛刺。 | `test_response_backpressure`、`test_wrapper_backpressure_event_pipeline` |
| W-07 | 内存通道时序 | `auto_out_a` 请求由包装层原样送到页表内存，`auto_out_d` 的双 beat 数据、source、size 原样回到 L2TLB；内存延迟和两个在途请求可完成。 | `test_memory_latency_and_two_outstanding`、`test_wrapper_64_page_working_set` |
| W-08 | WFI 握手 | `wfiReq` 原样送到 L2TLB；空闲时 `wfiSafe` 在延迟后脉冲；有未完成响应时保持低，响应完成后拉高；`wfiReq` 有效时新 A 通道请求被阻塞。 | `test_wrapper_wfi_idle_and_outstanding`、`test_wrapper_wfi_blocks_memory_request` |
| W-09 | 分布式 CSR 通路 | `distribute_csr` 写端口穿过包装层到达真实 PMP/CSR：写 deny 配置后故障，写 allow 配置后成功翻译。 | `test_wrapper_distributed_csr_pmp`、`test_csr_decode_sweep`、`test_pmp_configuration_sweep`、`test_pmp_tor_allow`、`test_pmp_high_entries` |
| W-10 | bitmap 组合 | BME/CMODE/BMA 经包装层送达 Bitmap/BitmapCache；bitmap 读请求在 A 通道出现，翻译仍返回正确的 S1 PPN；BCLEAR 后重新检查。 | `test_bitmap_enabled_walk`、`test_bitmap_clear`、`test_bitmap_many_walks`、`test_all_stage_with_bitmap`、`test_wrapper_bitmap_enabled_walk` |
| W-11 | 性能事件总线 | 19 个 `perf` 输出是内部 L2TLB 事件的**单拍脉冲**（不是计数器）：LLPTW 输入/内存、PtwCache access/l1/l2/l0/sp/pte hit、PTW fsm/mem 事件都有对应的脉冲；包装层再增加 2 级 `RegNext`。 | `test_wrapper_reset_and_idle_pipeline`、`test_wrapper_perf_event_semantics`、`test_wrapper_perf_llptw_and_cache_hit_events`、`test_wrapper_backpressure_event_pipeline` |
| W-12 | 复位/空闲与 DFT 边界 | 复位后功能通路空闲；perf 流水线无同步复位，随机初值在 4 拍内被真实事件冲刷；MBIST/DFT 端口保持静态时不影响翻译。 | `test_wrapper_reset_and_idle_pipeline`、全部翻译用例（BIST 输入由 env 置 0） |

## 覆盖与缺口

- 包装层本体 `L2TlbWrapperDut.v`：40/40 行 = 100%，0 未覆盖行；其 19×2 个
  perf 延迟寄存器和 19 个输出赋值均已执行。
- 组合 DUT 总计：行 17697/22289 = 79.398%，branch 4444/6304，
  toggle 102301/260640；功能覆盖 100%（235 samples，event/page/port/stage 全满）。
- 未覆盖行集中在真实子块内部（PtwCache/PMP/LLPTW/Bitmap/L2TLB 顶层状态），
  不属于包装层新功能点；逐项分类见
  [组合层报告](../reports/l2tlbwrapper-20261025.md) §5。
- **已闭合**：多于 2 个在途请求（`test_wrapper_four_outstanding`，mem_latency=7
  下全部完成）。
- **未闭合/边界**：零间隔共享叶子 back-to-back miss（strict XFAIL；根因已隔离为
  第三个 demand 被相邻预取行替代，插入 1 个空闲周期即通过
  `test_wrapper_shared_leaf_one_cycle_gap`）、以及子块内部已由独立叶级 DUT
  承担的残余路径。


## 第二阶段新增（2026-10-25）

| ID | 功能点 | 微架构语义与关键行为 | 对应用例 |
|---|---|---|---|
| W-13 | 零间隔共享叶子停顿的单周期边界 | 同一 leaf 表的 3 个 4KB miss 在零间隔时第三个 demand 行 0x800A2080 被预取行 0x800A20C0 取代而停顿；在请求间插入 1 个 service 周期后 demand 行 0x800A2080 由 LLPTW(source 1) 发出，三个页面全部完成。 | `test_wrapper_shared_leaf_one_cycle_gap`、`test_wrapper_back_to_back_shared_leaf_miss`（XFAIL） |
| W-14 | >2 在途请求 | 4 个不同 4KB 翻译在 mem_latency=7 时全部完成；零延迟模型会丢失第二个 D beat，已确认是 harness 时序问题。 | `test_wrapper_four_outstanding`（PASS） |

最终 run `l2tlbwrapper-final-05`：46 PASS + 1 XFAIL，行 17697/22289，
branch 4444/6304，toggle 102301/260640，功能 100%。
