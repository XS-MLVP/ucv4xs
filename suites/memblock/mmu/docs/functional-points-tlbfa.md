# TLBFA 功能点

> 本文为既有功能点清单，不代表 sampled bins 或旧 PASS 已证明所有语义。
> 当前 checker/归因限制与误报修正见 `reports/verification-soundness-20261025.md`。


TLBFA 是 L1 TLB 的条目存储叶子：保存翻译结果，按 VPN 与地址空间上下文做 CAM 查找，
返回物理页号与权限元数据，并接受 PTW 回填和 sfence 失效。下面的功能点用微架构行为
表述，而不是把端口信号逐条列成“某个 bit 等于 0/1”。

## 1. 复位与可见性

| ID | 功能点（人类可读） | 关键行为 |
|---|---|---|
| TLBFA-RESET-01 | 复位使所有 way 失效，翻译存储不向后续查找泄露旧条目 | 复位后任何 VPN/上下文查找都必须 miss；之前写入的条目不可再命中 |
| TLBFA-REFILL-01 | 回填把一个翻译安装到指定 way，并在下一拍开始对查找可见 | 写指针 way 的 valid 置位，VPN 与 payload 可被后续查找命中 |
| TLBFA-REFILL-02 | 回填与查找同拍时，新回填的 way 不参与本拍命中 | 本拍查找对正在写入的 way 表现为 miss；下一拍才可见 |
| TLBFA-REFILL-03 | 回填不会把同一翻译无提示地复制到多个 way | 只改变指定 way；其他 way 的 valid 与内容保持不变 |
| TLBFA-REFILL-04 | 回填数据在 sfence 同拍时，条目内容可以更新但失效动作优先 | 同拍 sfence 决定旧/新条目的可见性，回填不能绕过失效 |

## 2. 命中与上下文

| ID | 功能点（人类可读） | 关键行为 |
|---|---|---|
| TLBFA-HIT-01 | 完全相同的 VPN 与翻译阶段命中，并返回该条目的 PPN | noS2xlate→noS2xlate、onlyStage1→onlyStage1、onlyStage2→onlyStage2、allStage→allStage |
| TLBFA-HIT-04 | allStage 的合并 level 按“s1 异常/非叶优先、s2 异常、否则取较小页”规则确定 | s1 fake PTE + s2 异常时，当前生成 RTL 的条件顺序使“强制 level 3”分支不可达，实际返回 s1 level；见 known-issues |
| TLBFA-HIT-02 | VPN 不同则不命中 | 高位或低位任一被比较的 VPN 位不同，miss |
| TLBFA-HIT-03 | 翻译阶段不同不命中 | 即使同一 VPN，stage1 条目不能被 stage2 查找使用，反之亦然 |
| TLBFA-CTX-01 | 非全局 stage1 条目要求 ASID 相同 | satp/vsatp 的 ASID 与条目不同则 miss |
| TLBFA-CTX-02 | 全局 stage1 条目不受 ASID 限制 | perm.g=1 的条目在任意 ASID 下命中 |
| TLBFA-CTX-03 | 涉及 stage2 的条目要求 VMID 相同 | 当前 hgatp.vmid 不匹配则 miss |
| TLBFA-CTX-04 | onlyStage2 查找忽略 stage1 ASID | 两阶段中仅 stage2 的查找以 VMID 和 GPA VPN 为上下文 |
| TLBFA-GLOBAL-01 | 全局位只影响 ASID，不是“任何上下文都命中” | 全局条目的 VMID、VPN、阶段、页大小条件仍然生效 |

## 3. 页大小与 VPN 匹配

| ID | 功能点（人类可读） | 关键行为 |
|---|---|---|
| TLBFA-PAGE-01 | 4KB 条目要求完整 sector VPN 标签与 4KB 子页 valididx 同时命中 | 标签低位或 valididx 选中的子页无效都 miss |
| TLBFA-PAGE-02 | 2MB 条目允许 VPN 低 9 位变化，但要求中间与高位标签匹配 | 页内偏移不参与区分；越过 2MB 边界 miss |
| TLBFA-PAGE-03 | 1GB 条目允许 VPN 低 18 位变化，但要求更高位标签匹配 | 跨 1GB 边界 miss |
| TLBFA-PAGE-04 | 512GB 条目允许 VPN 低 27 位变化，只比较高 11 位标签 | 跨 512GB 边界 miss |
| TLBFA-PAGE-05 | 大页回填把 8 个 sector 都标为可用 | valididx 全 1；普通 4KB 回填保留 PTW 给出的子页位图 |
| TLBFA-PAGE-06 | 大页回填把 8 个 sector 都置为有效；普通 4KB 回填保留 PTW 子页位图 | 大页重新回填后页内所有 4KB 子页均可命中；小页的无效 valididx 仍会使对应子页 miss |
| TLBFA-NAPOT-01 | NAPOT 64KB 条目用低 4 位 VPN 作为页内选择，不按普通 4KB 标签比较 | n=1 时低 tag 只比较 5 位；PPN 低位来自 VPN |
| TLBFA-NAPOT-02 | NAPOT 不参与 stage2 低 3 位 PTE 索引门控 | n=1 时 pteidx 不阻止命中 |

## 4. Stage2 PTE 索引

| ID | 功能点（人类可读） | 关键行为 |
|---|---|---|
| TLBFA-S2IDX-01 | stage2 相关、非大页、非 NAPOT 的条目要求当前 VPN 的 PTE 索引在条目 pteidx 中有效 | 索引位不匹配则 miss |
| TLBFA-S2IDX-02 | onlyStage1 与非 stage2 查找不做 PTE 索引门控 | pteidx 不匹配不应阻止 stage1 命中 |
| TLBFA-S2IDX-03 | onlyStage2 回填从 GPA 的低 3 位生成 pteidx/valididx | 回填后只有该 4KB 子页命中 |

## 5. 返回载荷

| ID | 功能点（人类可读） | 关键行为 |
|---|---|---|
| TLBFA-PPN-01 | 4KB 且非 NAPOT 的 PPN 由条目的 PPN 高位与 vpn[2:0] 选择的 ppn_low 拼接 | 8 个 ppn_low 槽分别选择 |
| TLBFA-PPN-02 | NAPOT 的 PPN 低 4 位来自 VPN，低 3 位不来自 ppn_low | 页内偏移改变最终 PPN |
| TLBFA-PPN-03 | 2MB 的 PPN 低位来自 VPN[17:9]，1GB 的来自 VPN[26:18]，512GB 的来自 VPN[37:27] | 大页偏移改变最终 PPN |
| TLBFA-PAYLOAD-01 | 命中返回被选条目的 PBMT、权限与全局权限元数据 | s1/s2 权限和 fault 位原样返回 |
| TLBFA-PAYLOAD-02 | 未命中不产生可用翻译 | hit=0；调用方不得使用 payload |
| TLBFA-ACCESS-01 | 命中时 touch_ways 有效并给出命中 way；回填时下一拍给出写入 way | 供替换策略更新统计 |
| TLBFA-ACCESS-02 | 响应 valid 严格晚于请求 valid 一拍 | 请求 valid 撤销后响应 valid 也撤销 |

## 6. 失效

| ID | 功能点（人类可读） | 关键行为 |
|---|---|---|
| TLBFA-SFENCE-01 | 非虚拟化、全地址、全 ASID 的 sfence 只清除 no-S2 条目 | no-S2 条目全部清除（含 global）；onlyStage1/onlyStage2/allStage 条目保留，等待对应虚拟化失效 |
| TLBFA-SFENCE-02 | 非虚拟化、全地址、指定 ASID 的 sfence 清除匹配 ASID 的非全局 no-S2 条目 | 全局条目与其他 ASID 保留；onlyStage1/onlyStage2 保留 |
| TLBFA-SFENCE-03 | 指定地址、指定 ASID 的 sfence 按存储标签和 ASID 匹配，不按翻译阶段过滤 | 同一地址的 onlyStage1/allStage 非全局条目也会被清除；全局、其他 ASID、其他 VPN 保留 |
| TLBFA-SFENCE-04 | “全 ASID”地址形式与“指定 ASID”形式的全局存活规则不同 | 指定 ASID 的地址形式保留 global；地址 + 全 ASID 形式清除该地址上的 global 和其他 ASID 条目 |
| TLBFA-SFENCE-05 | hfence.vvma 清当前 VMID 的 stage2 相关条目，不按地址 | 当前 VMID 的 onlyStage1/onlyStage2/allStage 条目被清除；其他 VMID、no-S2 条目保留 |
| TLBFA-SFENCE-06 | hfence.gvma 清 stage2 相关条目；rs2 形式按 sfence.id 选择 VMID | rs2=1 清所有 stage2 类；rs2=0 按 sfence.id 选 VMID；no-S2 条目保留 |
| TLBFA-SFENCE-07 | 虚拟化模式的 sfence 走“全地址”的 stage2 选择路径 | virt=1 时忽略 addr，按当前 VMID 清除所有非 no-S2 条目（含 onlyStage1） |
| TLBFA-SFENCE-08 | MPT 的 BME/CMODE 组合可以触发全地址失效路径 | BME=1 且 CMODE=0 时按全地址处理；CMODE=1 时不隐式触发，地址参与匹配 |
| TLBFA-SFENCE-09 | 失效只改变 valid，不要求同时清除 payload；后续重新回填可覆盖 | 失效后同一 way 可被新翻译重新使用 |

## 7. 组合与时序

| ID | 功能点（人类可读） | 关键行为 |
|---|---|---|
| TLBFA-COMBO-01 | 48 个 way 都能独立安装、查找与失效 | 任意 way 的命中不依赖其他 way |
| TLBFA-COMBO-02 | 同拍请求与 sfence 的可见性按周期边界确定 | 查找采样旧状态，失效在边沿后生效 |
| TLBFA-COMBO-03 | 同一条目在不同上下文/阶段查找得到不同命中结论 | 同一 VPN 的 stage1 与 stage2 条目可以共存且互不串扰 |
| TLBFA-COMBO-04 | 连续查找保持单周期响应节拍且不产生自发状态改变 | 无请求时 valid 撤销，条目不自行变化 |

## 8. 覆盖闭环记录方式

每个功能点至少对应一个测试用例；用例在功能检查通过后才采样功能覆盖。运行完成后，
`tools/coverage_audit.py` 把 RTL 未覆盖的行、分支和 toggle 按文件/行号列出，再归入：

- 已有功能点的情况枚举缺失（例如某个页大小或某个失效形式未构造）。
- 整体功能点缺失（例如完全没有检查回填与查找同拍、或没有检查 NAPOT）。
- 结构不可达/工具插桩产物（需具体证据，不默认豁免）。

补测后重新运行，报告里保留补测前后覆盖率和未覆盖项数量的对比。


## 9. 本轮实际闭合证据

运行 `results/tlbfa-full-06/`，30+1 个用例全部通过（`31 passed`）。覆盖统计来自
`tools/coverage_audit.py` 对该运行原生覆盖数据库的分析：

| 指标 | 结果 |
|---|---:|
| 功能覆盖 | 8 个组全部 100% |
| DUT 行覆盖（`TlbfaDut.v`） | 3419 / 3419 = 100% |
| toggle | 17766 / 17766 = 100% |
| branch | 1016 / 1018 = 99.80% |

两个未取到的分支：

1. `TlbfaDut.v:7151` 的 `s2_exception & allStage_fake ? 3` 分支不可达。fake PTE 要求
   `s1_v=0`，而 s1 leaf 要求 `s1_v=1`，因此前一条件
   `s2_exception && !s1_leaf` 已经成立；该分支永远选不到。测试用
   `test_all_stage_fake_pte_with_stage2_exception_uses_s1_level` 记录了实际行为
   （返回 s1 level）。这与 `MMUBundle.scala` 注释中“fake PTE + s2 异常时写回 3”的
   意图不一致，作为候选 RTL 缺陷保留，不删除、不改写 RTL。
2. `TlbfaDut.v:12532` 的 `initial` 复位初始化隐式 else 分支：该块在时间零执行，
   运行时用例无法再次触发；属于初始化/工具插桩分支，不作为功能覆盖目标。

第一轮 `tlbfa-initial-01` 的 DUT 行覆盖已经是 100%，但 toggle 仅 54.0%、
`refill_timing` 66.7%、`reject_reason` 88.9%。逐项定位后确认是：

- toggle 缺口集中在 48 个 way 的存储位只写入过单一模式，属于“已有功能点的情况枚举
  不足”，补充 `test_all_storage_bits_toggle_in_every_way`（每 way all-ones 回填、
  复位、all-zeros 回填）和输入位/上下文/失效地址扫描用例后闭合。
- `refill_timing` 缺 `same_cycle_sfence`，补充 sfence 同拍回填用例并显式采样。
- `reject_reason` 缺 `invalid_way`，补充失效后仍保留 payload 的 way 查找并修正拒绝
  原因分类。
- 原来 `level_x_outcome`、`page_x_low_slot` 两个 cross 把带 `ignore` 的 NA 组合计入
  分母，形成不可达的 50%/20%；这不是 RTL 缺口。已删除这两个不具语义意义的 cross，
  保留 context×outcome 与 kind×page 的有效 cross。
