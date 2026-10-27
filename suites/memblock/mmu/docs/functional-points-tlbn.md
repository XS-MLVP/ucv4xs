# TLBNonBlock（MemBlock DTLB）独立功能点

> 本文为既有功能点清单，不代表 sampled bins 或旧 PASS 已证明所有语义。
> 当前 checker/归因限制与误报修正见 `reports/verification-soundness-20261025.md`。


DUT：`TLBNonBlock`（`rtl/tlbn`，5 文件真实闭包：`TLBNonBlock.sv`、
`TlbStorageWrapper_1.sv`、`TLBFA_1.sv`、`DelayN_3.sv`、`DelayN_5.sv`）。
最终 run `tlbn-tests-13`，30 用例 PASS。该 DUT 使用独立的 `TLBFA_1` /
`TlbStorageWrapper_1`，不是 ITLB 的 `TLBFA`/`TlbStorageWrapper` 复用。

| ID | 功能点 | 微架构语义与关键行为 | 对应用例 |
|---|---|---|---|
| DT-01 | 复位与 Bare 直通 | 复位后四端口 idle；`satp.mode=0` 时返回 sign-extend 后的虚拟地址，不请求 PTW，无权限/故障位。 | `test_reset_and_bare_mode` |
| DT-02 | no_translate 与 PMP 地址 | `no_translate=1` 时地址直接取 `pmp_addr`，PBMT/异常清零，但 PMP 请求仍以该地址和命令有效发出。 | `test_no_translate_uses_pmp_addr` |
| DT-03 | 缺失与 PTW 请求 | 未命中返回 `miss=1`，PTW 端口给出 VPN、s2xlate、getGpa；page offset 保持原地址低 12 位，PMP 地址为页内偏移。 | `test_miss_and_refill_hit` |
| DT-04 | PTW 回填与 4KB 命中 | PTW 响应安装 sector 条目；后续命中返回 `ppn_low` 与 PPN 组合的物理地址、PBMT 和权限；不同页内偏移复用同一翻译。 | `test_miss_and_refill_hit` |
| DT-05 | 超级页 PPN 合并 | 2MB/1GB leaf 的 PPN 低位由请求 VPN 低位替换；页内偏移保持，PBMT/权限按叶子检查。 | `test_superpage_ppn_merge` |
| DT-06 | 上下文与失效 | noS2 用 satp.ASID；ASID 改变使旧条目失效；全地址 sfence 清空存储。 | `test_asid_and_sfence` |
| DT-07 | 加载权限 | load 需要 R，或 `MXR && X`；U/S 模式与 SUM 规则；权限失败返回 pf_ld。 | `test_load_permissions` |
| DT-08 | 存储权限 | store/AMO 需要 W，且 D=1；W=0 或 D=0 返回 pf_st；AMO write 按写处理。 | `test_store_permissions` |
| DT-09 | A/D 更新与异常优先级 | A=0 的 load、A/D=0 的 store 触发 page fault；访问故障 af 优先于权限/页故障，置 af_ld/af_st 且清 pf。 | `test_ad_and_access_fault_priority` |
| DT-10 | PBMT 组合 | noS2/onlyS1 取 S1 PBMT；onlyS2 取 G PBMT；allStage 在 S1 PBMT 非零时优先 S1，否则取 G。 | `test_pbmt_composition` |
| DT-11 | onlyStage1 | 使用 vsatp ASID，返回 S1 PPN；不检查 G 阶段。 | `test_only_stage1` |
| DT-12 | onlyStage2 | 使用 hgatp VMID，返回 G 阶段 PPN，gpaddr 为原 VA；VMID 改变导致缺失。 | `test_only_stage2`、`test_only_stage2_vmid_filtering` |
| DT-13 | allStage 正常翻译 | 两阶段命中返回 G 阶段 PPN；S1/G 权限分别检查；G 阶段 load 权限失败返回 gpf_ld。 | `test_all_stage_clean` |
| DT-14 | GPA 回放 | allStage 的 G 阶段故障先产生 `getGpa` PTW 请求；GPA 响应后重放同一请求返回 `gpf`、`gpaddr`（S1 PPN 高位 + 页内偏移），且不再发起走表。 | `test_all_stage_gpa_replay`、`test_gpa_replay_port_two` |
| DT-15 | fake/非叶标记 | 条目不是叶或 fake PTE 时置 `isForVSnonLeafPTE`，不产生叶级 pf；有效叶权限失败仍报 pf。 | `test_fake_and_nonleaf_marker` |
| DT-16 | 四端口并发 | 四个请求端口同一拍独立返回各自 miss/hit、PTW 请求和 PMP 输出，互不干扰；不同 sector 的翻译可并存。 | `test_four_port_concurrency`、`test_ports_two_and_three` |
| DT-17 | 响应复制 | 端口 0/1 的 `paddr_1` 复制 `paddr_0`（nRespDups=2）。 | `test_response_duplicates` |
| DT-18 | PMP 输出 | 每个端口的 PMP valid/addr 与响应同步；有 cmd 的端口输出原始命令。 | `test_pmp_outputs`、`test_no_translate_uses_pmp_addr` |
| DT-19 | 请求 kill | `req.bits.kill=1` 抑制响应和 PTW 请求。 | `test_killed_request_is_dropped` |
| DT-20 | sector lane 有效性 | refill 的 `valididx`/`pteidx` 按 lane 生效：只允许一个 lane 时其余 lane 缺失。 | `test_sector_valididx_lane` |
| DT-21 | sector 全 lane | 8 个 lane 各自使用自己的 `ppn_low`，同一 sector 的 8 个 4KB 页返回不同 PPN。 | `test_sector_all_lanes` |
| DT-22 | 失效形式 | 地址+ASID、ASID-only、全清；hfence.v/hfence.g 不清 noS2；ASID/VMID 定向 hfence.v/g 清除对应 stage 类。 | `test_sfence_forms`、`test_hfence_asid_vmid_scoped` |
| DT-23 | 存储容量/替换 | 48-way 存储可容纳大量不同 sector；纯 PLRU 冷启动下 48 次 refill 至少 40 个驻留，96 次 refill 至少 46 个驻留，第 97 个 refill 可完成；这是 RTL 的替换策略行为，未修改。 | `test_storage_capacity`、`test_sfence_after_fill` |
| DT-24 | 性能事件 | `perf_0/1` 是经两级寄存的 access/miss 单拍脉冲。 | `test_perf_events` |
| DT-25 | need_gpa 的 redirect 清除 | need_gpa 记录 robIdx；匹配的 redirect 清除该状态，后续同 VPN 请求重新缺失/走表而不是复用 GPA 回放。 | `test_redirect_clears_need_gpa` |

## 覆盖与缺口

- 功能覆盖 100%（580 samples；event/port/stage/result 全满）。
- DUT-only 行 4839/4956 = 97.639%；branch 1424/1568；toggle 20486/37422。
- 子文件：`TlbNonBlockDut.v` 774/843，`TLBFA_1.sv` 3932/3980，
  `TlbStorageWrapper_1.sv` 65/65，两个 DelayN 100%。
- 残余 117 行分类：
  - `TLBFA_1.sv` 48 行是 sfence/hfence 每个 way 的一个未选 ternary arm
    （结构分支；同组其他 arm 已覆盖，属于情况枚举，不是缺失功能点）。
  - `TlbNonBlockDut.v` 59 行是 `need_gpa` 的 robIdx 维护和 GPA 响应
    `resp_s1_level/isLeaf/isFakePte` 在端口 1/3 上的分支；端口 0/2 的 GPA
    回放已实际验证。属于情况枚举（其余端口组合），未发现新的整体功能点。
