# L2 中层块功能点：PTW / PMP / Bitmap(Cache) / LLPTW

> 本文为既有功能点清单，不代表 sampled bins 或旧 PASS 已证明所有语义。
> 当前 checker/归因限制与误报修正见 `reports/verification-soundness-20261025.md`。


本文件补充 `L2TLB` 内部中层块的独立叶级语义功能点。所有 DUT 均由
`soc-split/rtl` 原样文件构建，不修改 RTL。

## 1. PTW 独立走表

DUT：`PTW`（`rtl/ptw`），最终 run `ptw-final-06`，30 用例 PASS，行 530/530。

| ID | 功能点 | 关键行为 |
|---|---|---|
| PTW-01 | Sv39 1GB leaf | root 读一次，返回 `level=2`、`entry_ppn=final_ppn>>3`、`tag=vpn>>3`、pteidx 对应 vpn 低 3 位 |
| PTW-02 | Sv39 2MB leaf | root nonleaf → mid leaf，两次读，返回 `level=1` |
| PTW-03 | 4KB 移交 LLPTW | root/mid 两次读后发出 `llptw.valid`，携带 vpn/source/s2xlate；PTW 本身不返回 4KB 结果 |
| PTW-04 | Sv48 512GB leaf | root leaf 返回 `level=3`，PPN 低 27 位为 0 |
| PTW-05 | 方向键命中提示 | `l2Hit` 用请求 ppn 作为 level-1 表基址、只读一次；Sv48 `l3Hit` 从 level-2 起走 |
| PTW-06 | 无效/保留/PBMT 故障 | V=0、保留位、PBMT 未使能、2MB 未对齐分别返回 pf |
| PTW-07 | PPN 高位访问故障 | leaf PPN 超出 S1 物理宽度时 `af=1` |
| PTW-08 | PMP 拒绝 | `pmp.ld/mmio=1` 时 `af=1` 且不产生内存读 |
| PTW-09 | bitmap 检查 | `BME=1,CMODE=0` 的正常 leaf 发出 bitmap 请求并在响应后返回；`cf` 反映检查结果 |
| PTW-10 | bitmap 缓存 PTE | `jmp_bitmap_check=1` 使用缓存 PTE，跳过页表内存读，仍做 bitmap 检查 |
| PTW-11 | onlyStage2 与 HPTW | `s2xlate=2` 发 HPTW 请求，返回 `h_resp`（tag/vmid/ppn/level/gpf/gaf） |
| PTW-12 | allStage 高 GPA 故障 | GPA 超出 Sv39x4 范围时 `h_gpf=1`，不读页表 |
| PTW-13 | stage1 合并响应 | `stage1Hit=1` 时在最后一次 HPTW 翻译后直接返回 stage1 merge payload |
| PTW-14 | 失效/背压/掩码 | sfence 中途、sfence 后重走、CSR changed、响应背压、mem.mask 均有覆盖 |
| PTW-15 | 请求忙碌语义 | 走表进行中 `req.ready=0`，完成后恢复 |
| PTW-16 | 位扫描 | stage1/hptw payload/CSR 全 0/全 1 位翻转 |

未闭合：PTW 的 allStage 正常多级 VS 走表（HPTW 与 PTW 交替）在独立 PTW DUT 中
只验证到“高 GPA 故障”和 stage1 merge；完整 allStage 走表由 L2TLB 顶层测试覆盖。
`full_gvpn` 高 VPN 有 11 行未覆盖。

## 2. PMP / PMA 配置

DUT：`PMP`（`rtl/pmp`），最终 run `pmp-final-02`，11 用例 PASS。

| ID | 功能点 | 关键行为 |
|---|---|---|
| PMP-01 | 复位默认 | PMP 全部 0；PMA 默认表来自生成 RTL 的 `PMAConfigs`（部分条目非零），未被覆盖的默认条目记为初始状态 |
| PMP-02 | cfg 打包/粗化 | 一次写 8 个 entry；A=2（NA4）在 PlatformGrain=4KB 下粗化为 NAPOT；W 仅在 R=1 时保留 |
| PMP-03 | addr/mask 语义 | OFF/TOR/NAPOT 的 addr 与 mask 由参考模型 `match_mask` 逐项核对 |
| PMP-04 | cfg 锁 | L=1 后同 entry cfg 写入被忽略 |
| PMP-05 | addr 锁 | 自身 L=1 或下一 entry L+TOR 时 addr/mask 写入被忽略 |
| PMP-06 | 全 32 entry | PMP/PMA 所有 cfg/addr/mask 输出与模型一致 |
| PMP-07 | PMA 属性 | PMA cfg 的 c/atomic/a/x/w/r 与 addr/mask 全量比较 |
| PMP-08 | 非法 CSR | 未实现地址写入不改变任何输出 |
| PMP-09 | mask 参考扫描 | 0/1/边界/高位 paddr 的 mask 与参考模型一致 |
| PMP-10 | 位扫描 | 全 0/全 1 配置与地址，最后锁 entry |

## 3. BitmapCache

DUT：`BitmapCache`（`rtl/bitmapcache`），最终 run `bitmapcache-final-06`，12 用例 PASS。

| ID | 功能点 | 关键行为 |
|---|---|---|
| BC-01 | refill/hit | 按 tag 回填 64 位字；同 tag 命中返回 cfs 字节 |
| BC-02 | 字节选择 | cfs 字节由 PPN[5:3] 选择，8 个 lane 与数据字节一致 |
| BC-03 | 组/路 | 32 组 × 4 路全部可写；第 5 次回填发生替换，命中数 3/4 |
| BC-04 | miss | 未回填 tag 命中=0，order 仍原样返回 |
| BC-05 | BCLEAR | BCLEAR 清 valid；sfence/CSR changed 只清在途，不清数据 |
| BC-06 | 顺序/背压 | order 原样返回；resp.valid/payload 在 ready=0 时保持 |
| BC-07 | 数据极值 | 全 0/全 1/交替数据回填后 cfs 正确 |

未闭合：MBIST 端口未驱动；`stageDelay_valid_1cycle` 的 SRAM 回读旁路和 split SRAM
结构分支未覆盖（9 行 + 24 branch），已分类为 DFT/SRAM 结构。

## 4. Bitmap

DUT：`Bitmap`（`rtl/bitmap`），最终 run `bitmap-final-06`，16 PASS + 1 XFAIL。
功能覆盖 100%（cache_hit/cache_miss/pmp_fail/refill/wakeup/flush/multi + level 0..3）。

| ID | 功能点 | 关键行为 |
|---|---|---|
| BM-01 | cache 命中 | cf = cfs[ppn[2:0]]，cfs 原样返回，id 正确 |
| BM-02 | cache 缺失/回填 | 发出 64 位 bitmap 字内存读，抽取 cf/cfs，发出 refill（tag=ppn，data=word） |
| BM-03 | PMP 拒绝 | cf/cfs 全 1，不发 cache/mem |
| BM-04 | level/NAPOT 合并 | level 1/2/3 将 VPN 低位合并进有效 PPN；NAPOT level 0 合并 VPN[3:0] |
| BM-05 | 多请求/重复 | 多 outstanding 各自返回 id；重复 PPN 都完成（去重为 best-effort） |
| BM-06 | flush | sfence 清空 pending，之后可重新接收 |
| BM-07 | wakeup | level 0/n=0/非 bypass 时产生 wakeup，携带 set/tag/way/pteidx/s2xlate/check_success；backpressure 阻塞 resp |
| BM-08 | 数据极值 | 全 0/全 1 bitmap 字分别得到 cf=0/1、cfs 全 0/全 1 |
| BM-09 | back-to-back 缺陷 | 两个请求连续 req.fire 时，单入口 PMP check 流水线把第二个检查写到第一个 entry，第二个 entry 停在 addr_check；strict XFAIL 记录 |

## 5. LLPTW

DUT：`LLPTW`（`rtl/llptw`），最终 run `llptw-final-03`，23 用例 PASS；功能覆盖
100%（38 samples），行 1656/1955 = 84.706%，branch 359/407，toggle 4302/20770。

| ID | 功能点 | 关键行为 |
|---|---|---|
| LL-01 | 4KB 并行块读 | 一个请求发出 64 字节 PTE 块读，8 个子页 PTE 参与检查，af=0 |
| LL-02 | vpn_low 偏移 | vpn 低 9 位决定起始 PTE 地址 |
| LL-03 | PMP 拒绝 | af=1，无内存读 |
| LL-04 | 顺序请求/容量 | 顺序请求可完成；6 个 entry 同时活跃时 in.ready=0，消费后恢复 |
| LL-05 | 重复请求 | 相同 VPN 的在途请求合并为一次内存读，一个输出 |
| LL-06 | 背压/flush/mask | out 背压保持；sfence 中途取消；mem.req.mask 阻塞（清除后需 flush 重试） |
| LL-07 | bitmap jump | 输入 ptes/cfs 走 bitmap 路径，不读页表；输出 ptes/cfs，af=cf；bitmap 请求字段正确 |
| LL-08 | lane 扫描 | vpn_low 0..7 全部覆盖 |
| LL-09 | allStage 两阶段 | 先 HPTW 翻译叶子表 GPA，按 HPA 读 64B PTE 块；再 HPTW 翻译最终叶子 PPN，输出最终 stage2 条目 |
| LL-10 | stage2 故障 | 第一次 HPTW gpf/gaf 在 PTE 读取前终止并置 first_s2xlate_fault；第二次 HPTW gpf/gaf 在读取后置 gpf/gaf、不置 first |
| LL-11 | stage2 权限 | 第一次 HPTW `r=0,x=0` 不能作页表；MXR=1、x=1、r=0 允许 execute-only 页表继续 |
| LL-12 | onlyStage2 | s2xlate=2 直接读 PTE 块，不发 HPTW，stage2 故障字段为 0 |
| LL-13 | 页面缓存回写 | 结果仍在 mem_out 时到达的重复请求发出 io.cache 更新，不重读内存、不产生第二输出 |
| LL-14 | 每个 entry slot | slot 1..5 均可承载 allStage/bitmap/cache-retry，输出 id 与 per-entry 字段正确 |

残余 299 行已分类为“已有功能点的情况枚举缺失”：重复请求在 mem_waiting/
last_hptw 状态的 wait_id fan-in、enqueue 时 to_last_hptw_req 的 per-entry 字段、
部分 last_hptw/cache/bitmap 状态转移；没有“整体功能点缺失”。

未闭合范围：多个 allStage 请求同时在不同 entry 在途（2 个 allStage 并发在 3 次
HPTW 请求、1 次 PTE 读后停顿；strict XFAIL `test_two_concurrent_all_stage`）；
prefetch source 的重复请求按设计丢弃，不作为 cache 回写功能点；连续 input fire
仍需 ≥3 拍间隔（`LLPTW-PMP-BACKTOBACK-GAP`）。


## 6. 第二阶段更新（2026-10-25）

| ID | 功能点 | 微架构语义与关键行为 | 对应用例 |
|---|---|---|---|
| PTW-30 | stage1Hit allStage 的 full_gvpn 重建 | S1 leaf level 0..3 与 G leaf level 0..3 所有组合都重建完整 GPA；level0 NAPOT（n=1）走独立 arm；stage1Hit G-stage gpf 记录 hptw_resp_gpf。 | `test_stage1_hit_full_gvpn_levels` |
| PTW-31 | normal allStage 的 HPTW 交织 | VS root/mid 访问和 final GPA 都由 HPTW identity 翻译；PTW 读 root/mid，HPTW 顺序请求 0x80010/0x80011/0x40000，返回 G-stage 结果。 | `test_normal_all_stage_identity_hptw` |
| PMP-13 | PMA cfg 字节语义 | 0x7C0..0x7C6 四组 32 个 entry 的 C/ATOMIC/A/X/W/R 字段按粗化规则写入；PMA addr 重算 mask；0x7C8.. 地址写入生效。 | `test_pma_cfg_byte_semantics`、`test_all_pma_entries` |
| BMP-18 | 多 miss 边界（未闭合） | 两个并发 bitmap cache miss 在首次内存读后停顿；strict XFAIL，单 miss/deny/allow 已闭合。 | `test_multi_miss`（XFAIL） |
| LL-15 | 多 allStage 并发（未闭合） | 两个 entry 的 allStage 请求在零间隔/单请求 stagger/不同 slot 顺序下均只有一个 entry 完成，另一个在 first-stage HPTW 响应后不再发 PTE 读；strict XFAIL；单 allStage 在 slot 1..5 全通过。 | `test_two_concurrent_all_stage`（XFAIL） |

最终 run：`ptw-final-06`（30 PASS，行 530/530=100%，branch 418/420，
toggle 12213/15344）、`pmp-final-04`（12 PASS，行 2117/2117）、
`bitmap-final-07`（16 PASS + 2 XFAIL，行 974/1415）、
`llptw-final-04`（23 PASS + 1 XFAIL，行 1656/1955）。
