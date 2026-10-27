# TLB（ITLB）功能点

> 本文为既有功能点清单，不代表 sampled bins 或旧 PASS 已证明所有语义。
> 当前 checker/归因限制与误报修正见 `reports/verification-soundness-20261025.md`。


本阶段验证 `TLB` 生成的 ITLB 顶层：它包含真实 `TlbStorageWrapper` 与 `TLBFA`
子块，并接收 PTW 响应完成 miss 回填。功能点按可观察的翻译行为表述；不把内部
流水寄存器的每个信号当作功能点。

## 1. 复位、Bare 与特权模式

| ID | 功能点 | 关键行为 |
|---|---|---|
| TLB-BARE-01 | Bare 模式不查 TLB，物理地址等于请求虚拟地址 | miss=0、无 PTW 请求、无异常 |
| TLB-BARE-02 | M 模式即使 satp 非零也关闭翻译 | 请求地址直通，不发起 PTW |
| TLB-RESET-01 | 复位清空有效翻译；复位后同一请求重新 miss | 旧翻译不可命中，PTW 请求重新出现 |

## 2. 未命中与 PTW

| ID | 功能点 | 关键行为 |
|---|---|---|
| TLB-MISS-01 | Sv39/Sv48 模式下未命中时向 PTW 发出当前 VPN | miss=1，PTW valid、vpn 和 s2xlate 正确 |
| TLB-PTW-01 | 命中的请求不得发出 PTW 请求 | hit 响应 PTW valid=0 |
| TLB-CTX-01 | 两阶段上下文请求报告 allStage 编码 | virt+vsatp+hgatp 时 s2xlate=3 |
| TLB-CTX-02 | onlyStage1/onlyStage2 请求分别报告 1/2 | 不把两个单阶段上下文混为 allStage |
| TLB-REFILL-01 | 匹配的 PTW 响应安装翻译；后续请求命中并返回 PPN+offset | paddr 由真实 TLBFA 合成 |
| TLB-REFILL-02 | PTW 响应可在同拍完成当前 outstanding miss | 不要求先回填再重新发请求 |
| TLB-REFILL-03 | 非匹配 PTW 响应不解决当前 miss | 后续请求仍 miss/请求 PTW |
| TLB-REFILL-04 | onlyStage2 以 GPA 为 tag 回填 G-stage-only 翻译 | 后续虚拟化请求命中 G-stage PPN |

## 3. 异常与权限

| ID | 功能点 | 关键行为 |
|---|---|---|
| TLB-EXCP-01 | 指令页要求 x 权限；缺 x 产生 pf | pf_instr=1 |
| TLB-EXCP-02 | U/S 模式与 PTE u 位匹配规则产生 pf | U 模式要求 u=1，S 模式要求 u=0 |
| TLB-EXCP-03 | A 位为 0 产生 page fault | pf=1 |
| TLB-EXCP-04 | AF 位优先于 page fault | af=1 时 pf=0 |
| TLB-EXCP-05 | fake PTE 作为 non-leaf-like 报告，不产生 leaf pf | isForVSnonLeafPTE=1 |
| TLB-EXCP-06 | non-leaf PTE 不产生 leaf page fault | isForVSnonLeafPTE=1 |

## 4. 失效

| ID | 功能点 | 关键行为 |
|---|---|---|
| TLB-FENCE-01 | 全地址/全 ASID、全地址/指定 ASID、指定地址形式透传 TLBFA | 目标清除、非目标保留 |
| TLB-FENCE-02 | 地址+全 ASID 形式按地址清除所有 ASID | 与指定 ASID 形式区分 |
| TLB-FENCE-03 | hfence.vvma/gvma 不作用 no-S2 条目 | no-S2 翻译保留 |
| TLB-FENCE-04 | 失效后同一请求重新 miss 并请求 PTW | 不保留旧命中 |

## 5. 范围边界

- 已验证：noStage2、onlyStage1/onlyStage2 的 **PTW 请求分类**、allStage/onlyStage2
  的干净回填与命中、指令权限异常、sfence/hfence 透传，以及 allStage G-stage
  fault 的 `getGpa`/`need_gpa`/GPA 重放（`TLB-GPA-01`，run `tlb-gpa-tests-06`）。
- 未验证：复杂的 allStage 两级异常合并、TLB 的 flushPipe 取消路径与部分 stage2 分支。
  这些不因本阶段通过而视为已验收。
- `TLBNonBlock` 使用独立的 `TLBFA_1`/`TlbStorageWrapper_1`，未在本阶段验证。


## 6. 第二阶段新增：GPA/getGpa 重放

| ID | 功能点 | 关键行为 | 对应用例 |
|---|---|---|---|
| TLB-GPA-01 | allStage 的 G-stage fault 先取 GPA 再报告 guest page fault | S1 leaf 命中但 G-stage gpf/gaf 时，首拍 `miss=1` 并发出 `ptw.req.getGpa=1`；GPA 响应后同一请求返回 `gpf=1`，`gpaddr = ((s1_ppn<<3)|ppn_low)<<12 | offset`，不再走普通页表读。 | `test_gpa_replay_for_all_stage_gpf` |

最终 run `tlb-gpa-tests-06`：25 PASS，行 3655/3657=99.945%，branch 1094/1104，
toggle 18785/23074；残余 2 行为时间零 initial 复位块。GPA 相关 13 行已覆盖。
