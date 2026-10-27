# L2TLB 顶层集成功能点（真实子块）

> 本文为既有功能点清单，不代表 sampled bins 或旧 PASS 已证明所有语义。
> 当前 checker/归因限制与误报修正见 `reports/verification-soundness-20261025.md`。


本文件定义 `L2TLB` 顶层在真实 Picker DUT 中的微架构语义功能点。DUT 的
`PtwCache`、`PTW`、`HPTW`、`LLPTW`、`Bitmap`、`BitmapCache`、`PMP` 和全部
arbiter 都是生成 RTL 原样实例，不是 Python 模型。测试环境只实现外部
`auto_out_a/d` 页面表内存模型和两路 TLB 请求驱动。

## 1. 翻译结果语义

| ID | 功能点 | 关键行为 |
|---|---|---|
| L2T-01 | 1GB 大页走表 | 根级 leaf（level 2）经一次真实内存读返回；`s1_entry_v=1`、`level=2`、`entry_ppn` 为扇区 PPN（`final_ppn>>3`），`pf=af=0` |
| L2T-02 | 2MB 大页走表 | level 1 leaf 返回 `level=1`；触发 LLPTW 预取路径；PPN 低 9 位必须为 0 |
| L2T-03 | 4KB 走表 | root→middle→leaf 三级真实读；返回 `level=0`，`s1_entry_ppn=final_ppn>>3`，`ppn_low` 携带低 3 位 |
| L2T-04 | 单级翻译不改变 VPN 语义 | 请求 vpn 决定返回 entry tag（`vpn>>3`），不能用固定/伪造 tag 通过 |
| L2T-05 | 响应 payload 稳定 | `resp_ready=0` 时 `resp_valid` 和全部 payload 保持至少 20 拍，握手后 valid 清除 |

## 2. 故障与权限语义

| ID | 功能点 | 关键行为 |
|---|---|---|
| L2T-06 | 无效根 PTE 返回 fake/fault | `V=0` 时不返回可用翻译；`s1_v=0` 且 `pf=1` |
| L2T-07 | PBMT 未使能时叶子故障 | 叶子 `PBMT!=0` 且 `mPBMTE=0` 时 `pf=1` |
| L2T-08 | 保留位/非法 PTE 故障 | 保留位非 0 的叶子返回 `pf=1` |
| L2T-09 | 2MB 超级页 PPN 未对齐故障 | level 1 leaf 的 PPN 低位非 0 时返回 `pf=1` |
| L2T-10 | PMP 拒绝产生 access fault | 关闭 PMP 条目后走表被拒；`s1_af=1`、`s1_v=0` |
| L2T-11 | PMP TOR/NA4/NAPOT 允许路径 | TOR 覆盖页面表时可完成；16 个 entry 与高 16 个 entry 的 CSR 写路径都可编程 |
| L2T-12 | PMP/PMA CSR 解码扫描 | 写 `0x3A0..0x3BF` 后恢复 allow-all，仍能完成翻译 |

## 3. 两阶段与 HPTW

| ID | 功能点 | 关键行为 |
|---|---|---|
| L2T-13 | onlyStage1 使用 vsatp | 请求 `s2xlate=1` 时走 VS 页表，响应 `s1_asid=vsatp.asid` |
| L2T-14 | onlyStage2 使用 hgatp | 请求 `s2xlate=2` 时走 G-stage，返回 S2 entry（vmid、level、ppn）且 `gpf=gaf=0` |
| L2T-15 | allStage 经 HPTW 翻译 VS 页表地址 | VS 页表 GPA 经 G-stage 恒等映射；`s2xlate=3` 同时返回 S1/S2 entry，HPTW 真正发出 source 7 内存请求 |
| L2T-16 | allStage + bitmap | 两阶段走表同时开启 bitmap 检查，HPTW 的 bitmap source 被真实驱动 |

## 4. 缓存、miss 与失效语义

| ID | 功能点 | 关键行为 |
|---|---|---|
| L2T-17 | 相同 VPN 重放命中 PtwCache | 首次走表后同一请求不再产生 source 6（PTW）内存读，响应 PPN 不变 |
| L2T-18 | 有限 cache 的替换行为 | 12 条不同 4KB 翻译顺序请求全部正确；重放允许因容量/替换重新走表，不伪造“全命中” |
| L2T-19 | 小 resident 工作集重放 | 4 条相邻 VPN 的 leaf 行被缓存后重放不再产生 PTW 内存读 |
| L2T-20 | 同 64B leaf 行共享 | 两个 vpn_leaf 相邻的请求共享 leaf 行；第二请求不产生 PTW 内存读 |
| L2T-21 | sfence 全地址 | 首次翻译后 sfence（rs1=rs2=1）使后续请求重新走表 |
| L2T-22 | sfence 地址+ASID / 地址+全 ASID | rs1=1 的两种 scoped 形式都能完成对应范围的失效并重新走表 |
| L2T-23 | 走表过程中 sfence | 请求进行中插入 sfence，不产生死锁；之后的新请求仍能正确翻译 |
| L2T-24 | satp.changed + sfence | 软件更新 satp 并执行 sfence 后，使用新根页表返回新 PPN |
| L2T-25 | CSR changed 与 flush 关系观测 | 仅 satp.changed 而不执行 sfence 时，同 VPN 观察到旧 PtwCache 结果；测试按架构要求补 sfence 后再断言新结果 |

## 5. 并发、内存与顶层接口

| ID | 功能点 | 关键行为 |
|---|---|---|
| L2T-26 | 两路 TLB 端口 | 端口 0/1 都能独立完成翻译；同拍请求由 arbiter 接受并按各自响应返回 |
| L2T-27 | 内存延迟与多请求在途 | D 通道延迟 7 拍时仍能完成；两条请求可同时在途并按 tag 分别返回 |
| L2T-28 | 响应背压 | 响应 valid 在 ready=0 时保持稳定；ready 后只握手一次 |
| L2T-29 | bitmap 使能检查 | `BME=1, CMODE=0` 时真实发出 bitmap 内存请求，all-ones bitmap 允许翻译 |
| L2T-30 | bitmap cache 清除 | BCLEAR 后不同 PPN 的请求重新查 bitmap；翻译结果仍正确 |
| L2T-31 | 多条 bitmap 翻译 | 8 条不同 VPN/PPN 的 bitmap 检查走表全部正确，覆盖 Bitmap/BitmapCache 多 entry 路径 |
| L2T-32 | 内存页面表镜像 | 用稀疏字节内存按 Sv39 布局构造 root/mid/leaf，而不是只靠 per-source 脚本，验证真实地址索引 |
| L2T-33 | 根索引变化 | 不同 vpn1 访问不同根页表行，返回各自 PPN |

## 6. 未覆盖/未验收（与证据对应）

- `PtwCache` 的替换策略、set/bank 冲突、预取状态和部分 sfence 地址哈希路径仍有
  2070 行未覆盖；当前只证明命中/重走/有限容量行为。
- `LLPTW` 的多 entry wait/HPTW response 字段和完整 8 项并行路径残余 299 行，已分类为
  per-entry 情况枚举；两个并发 allStage 请求仍为 strict XFAIL。
- PMA（`0x7C0..0x7C8`）语义和 PMA/PMP 页表交互已在第二阶段闭合；PMP leaf 和
  L2TLB 顶层均有实际用例（见 §6）。
- bitmap deny 极性已建立：all-ones bitmap（cf=1）返回 `s1_af=1`，all-zero（cf=0）
  返回正常翻译；旧观察是 checker 漏查 `s1_af`。
- `PTW.full_gvpn` 的 512GB/高 VPN 与 normal allStage 路径已在独立 PTW leaf 闭合
  （`ptw-final-06` 行 530/530）。
- MBIST 端口（`MbistBitmapCache`/`MbistPipePtwL0`/`MbistPipePtwL1`）是 DFT 路径，未驱动。
- `HPTW` 已有独立叶级 DUT（`docs/reports/hptw-20261024.md`）；`PtwCache`/`PTW`/
  `LLPTW`/`Bitmap` 仍只在本文件中以 L2TLB 真实子块身份被集成验证，不能用顶层
  覆盖数字替代独立验收。
- `L2TLBWrapper` 已在 2026-10-25 建立独立组合 DUT 并验收（`l2tlbwrapper-final-01`，见
  [functional-points-l2tlbwrapper.md](functional-points-l2tlbwrapper.md)）；本文件
  只描述内部 L2TLB 顶层。


## 6. 第二阶段新增功能点

| ID | 功能点 | 微架构语义与关键行为 | 对应用例 |
|---|---|---|---|
| L2T-PMA-01 | 可缓存、可读的页表内存允许走表 | PMA TOR 条目覆盖页表区域，C=1、R=1、RWX；root/mid/leaf 三次真实读完成并返回正确 PPN。 | `test_pma_cacheable_page_tables_walk` |
| L2T-PMA-02 | 非可缓存页表内存触发访问故障 | 同一 TOR 条目 C=0 时，PW 在表读前返回 `s1_af=1`，无 `auto_out_a` 读。 | `test_pma_non_cacheable_page_tables_fault` |
| L2T-PMA-03 | 不可读页表内存触发访问故障 | C=1 但 R=0 时返回 `s1_af=1`，无表读。 | `test_pma_unreadable_page_tables_fault` |
| L2T-BITMAP-05 | bitmap deny/allow 极性 | 全 1 bitmap 的 cf=1 置 `s1_af=1` 且 `s1_v=0`；全 0 bitmap 的 cf=0 返回 `s1_v=1` 与正确 PPN。 | `test_bitmap_deny_and_allow` |
| L2T-FENCE-06 | all-address sfence 完整性（未闭合） | `rs1=0/rs2=0` 在 PTE 修改后返回旧 PPN 且无新表读；RTL PtwCache 清除条件仍使用 sfence.addr 的 set/vpn mask，strict XFAIL 记录，不主张已验收。 | `test_sfence_all_rewalks_after_pte_change` |
| L2T-FENCE-07 | 地址定向 sfence 重走 | `rs1=1/rs2=0/addr` 在 PTE 修改后返回新 PPN 并产生新表读。 | `test_sfence_scoped_rewalks_after_pte_change` |
| L2T-MULTI-04 | >2 在途请求 | 4 个不同 4KB 请求背靠背发出，在页面表内存延迟 7 拍时全部完成并返回各自 PPN；零延迟测试模型会丢失第二个 D beat，属于 harness 时序问题。 | `test_four_outstanding_translations`、`test_memory_latency_and_two_outstanding` |
| L2T-PREFETCH-05 | 零间隔共享叶子停顿的根因 | 第三个 demand 行被相邻预取行替代；插入 1 个空闲周期后 demand 正常发出并完成。 | wrapper `test_wrapper_shared_leaf_one_cycle_gap`、`test_wrapper_back_to_back_shared_leaf_miss`（XFAIL） |

最终 run `l2tlb-final-12`：40 PASS + 1 strict XFAIL，行 17081/22249=76.772%，
branch 4329/6304，toggle 96615/255430，功能 100%。
