# HPTW 独立叶级功能点

> 本文为既有功能点清单，不代表 sampled bins 或旧 PASS 已证明所有语义。
> 当前 checker/归因限制与误报修正见 `reports/verification-soundness-20261025.md`。


`HPTW` 是两阶段翻译中负责 G-stage（hgatp）走表的独立块，真实文件
`rtl/hptw/HPTW.sv`（474 行），在 L2TLB 中同时服务 PTW 的 allStage 路径和
LLPTW 的 G-stage 预取。本工程使用最小依赖闭包（HPTW + ClockGate）建立独立 DUT。

## 1. 走表结果

| ID | 功能点 | 关键行为 |
|---|---|---|
| HPTW-01 | 4KB G-stage 翻译 | root→middle→leaf 三次真实 `io_mem` 读；响应 `level=0`、`entry_ppn=final_ppn`、`tag=gvpn`、`vmid=hgatp.vmid` |
| HPTW-02 | 2MB 大页 | level 1 leaf 两次读；返回 `level=1`，PPN 低 9 位必须为 0 |
| HPTW-03 | 1GB 大页 | level 2 root leaf 一次读；返回 `level=2`，PPN 低 18 位必须为 0 |
| HPTW-04 | 响应 payload 语义 | `perm_d/a/x/w/r`、`n`、`pbmt` 来自 PTE；`tag` 为完整 gvpn（不是 vpn>>3） |
| HPTW-05 | NAPOT/PBMT 字段 | 使能 PBMTE 后合法 NAPOT/PBMT 叶子在响应中保留 `n/pbmt` |
| HPTW-06 | 高物理地址 | hgatp.ppn 取 36 位高位时，pmp/mem 请求地址高位真实翻转并完成翻译 |

## 2. 故障

| ID | 功能点 | 关键行为 |
|---|---|---|
| HPTW-07 | 无效 PTE | V=0 的根 PTE 返回 `gpf=1`、`gaf=0` |
| HPTW-08 | 超级页未对齐 | level 1 leaf 的 PPN 低 9 位非 0 返回 `gpf=1` |
| HPTW-09 | PMP 访问故障 | `pmp_resp_ld=1` 表示拒绝；返回 `gaf=1` 且不发出 `io_mem` 请求 |
| HPTW-10 | PMP MMIO 故障 | `pmp_resp_mmio=1` 同样返回 `gaf=1`、无内存读 |
| HPTW-11 | 页表保留位/PBMT 非法 | 由 HPTW 的 `pageFault` 组合判定；合法边界与非法边界均有用例 |

## 3. 控制与并发

| ID | 功能点 | 关键行为 |
|---|---|---|
| HPTW-12 | `io_mem_mask` 阻塞 | mask=1 时没有 `io_mem_req`；释放后需 flush 并重新发请求才能继续 |
| HPTW-13 | 走表中 sfence | 第一次内存读后插入 sfence，不产生挂死；后续请求可正确完成 |
| HPTW-14 | hgatp.changed flush | CSR changed 清状态；相同 gvpn 重新走表并返回新 PPN |
| HPTW-15 | satp/vsatp/virt changed | 其它 flush 源也都能清状态并允许下一次翻译 |
| HPTW-16 | 响应背压 | `resp_ready=0` 时 `resp_valid` 和全部 payload 保持稳定，握手后 valid 清除 |
| HPTW-17 | l1/l2/l3 hit 提示 | 对应 level 的 PTE 已缓存时，用 `req.ppn` 作为下一级表基址，跳过该级内存读 |

## 4. bitmap 与缓存旁路

| ID | 功能点 | 关键行为 |
|---|---|---|
| HPTW-18 | bitmap 缓存叶子（fromSP） | `jmp_bitmap_check=1, fromSP=1` 时使用 `bitmapCheck.pte`，发出 bitmap 请求并在 `cf=0` 后完成翻译 |
| HPTW-19 | bitmap 缓存叶子（ptes 向量） | `fromSP=0` 时从 `ptes[gvpn[2:0]]` 取 PTE，覆盖 bitmap 请求级别 0 的路径 |
| HPTW-20 | bitmap 反压与超时 | bitmap 请求/响应按 ready/valid 握手；响应只在 `resp_ready` 有效后驱动 |

## 5. 覆盖与未验收

- 最终 run `results/hptw-final-02`：21 用例 PASS，行 **133/133 = 100%**，
  branch **97/98**，toggle **5069/5270 = 96.19%**，功能 **100%**（32 samples）。
- 唯一 branch 缺口是时间零 `initial if (reset)` 的隐式 else（HPTW.sv:420）。
- 残余 201 点 toggle 主要是 `cache_pte_ppn`/`req_ppn`/`gpaddr` 的未枚举高位组合、
  `cache_pte_reserved` 常量位、bitmap 握手控制位和顶层地址高位；已逐项分类，
  不用不可达激励伪造。HPTW 的 `fromSP`/`l3Hit` 等结构分支已实际驱动。
- 本叶级 DUT 不包含 L2TLB 中的 PtwCache/LLPTW 组合；HPTW 在 L2TLB 内的集成结果
  另见 `docs/reports/l2tlb-20261024.md`。`L2TLBWrapper` 仍未验证。


## 6. 第二阶段新增：复位与 accessFault 观察

| ID | 功能点 | 关键行为 | 对应用例 |
|---|---|---|---|
| HPTW-21 | 复位后首次走表与 accessFault 状态 | `accessFault` 不在同步复位块内（结构事实）。固定 seed=1（以及 2..8）下，复位后未执行 sfence 的首次合法走表仍返回 `gaf=0` 并完成 root/mid/leaf 三次读；PMP 拒绝走表返回 `gaf=1` 且无读；再次复位后合法走表仍成功。未复现功能性 spurious fault，保留为 RTL hygiene observation。 | `test_hptw_reset_without_flush_observation` |

最终 run `hptw-final-02` 已包含该用例；锁定的 known-issue 为
`HPTW-ACCESSFAULT-NOT-RESET`（accepted, rtl-hygiene-observation）。
