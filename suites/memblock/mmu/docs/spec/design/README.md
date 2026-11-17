# MMU Design Spec

状态：验证侧整理，依据生成 RTL 的真实实例化关系和固定源码；**未声明设计 owner 批准**。基线、RTL 哈希与参数见 [`manifest/baseline.json`](../../../manifest/baseline.json)。

## 1. 范围与真实层次

本工程验证 XiangShan `kunminghu-v3` 的地址翻译路径，使用 Picker 生成最小 DUT；不覆盖整颗 MMU、SoC 或 ISA 签核。

```text
TLBFA (48-way, 1 set, 8-sector storage leaf)
└── TlbStorageWrapper
    └── TLB (Frontend ITLB)

TlbStorageWrapper_1 + TLBFA_1
└── TLBNonBlock (MemBlock DTLB load path)

Frontend/MemBlock leaves
├── PTWFilter
└── PTWRepeaterNB

L2TLBWrapper → L2TLB
├── L2TlbMissQueue
├── PtwCache
├── PTW / HPTW / LLPTW
├── Bitmap / BitmapCache / PMP
├── L2TlbPrefetch
└── arbiters
```

`TLBFA` 是 `TlbStorageWrapper` 的真实叶子，不是 Python 模型替代品；`TLBNonBlock` 使用独立的 `TLBFA_1`/`TlbStorageWrapper_1`，不能以 `TLB` 结论替代。

## 2. 接口与配置

- TLBFA 固定参数：1 读端口、48 way、单 set 全相联；38 位 VPN、36 位 PPN、8 个 4KB sector；Sv48（Level=3）、16 位 ASID、14 位 VMID；支持 4KB/2MB/1GB/512GB 与 64KB NAPOT。
- 支持 noS2xlate / onlyStage1 / onlyStage2 / allStage；访问权限、A/D、PBMT/PMA/PMP 和 sfence/hfence 作用域按功能点与报告逐项检查。
- PTW 完成/取消/异常边界见 [ptw-completion-contract.md](contracts/ptw-completion-contract.md)；更细的微架构行为在 [functional-points](../verification/functional-points) 中按层记录。
- 隐式 VS 页表 G-stage 读取的权限（必须 R=1，MXR 只作用于 explicit access）及当前 a0c2 裁剪 `io_csr_priv_mxr` 的适配边界见 [implicit-gstage-mxr-contract.md](contracts/implicit-gstage-mxr-contract.md)。该文件是当前基线合同；`ptw-completion-contract.md` 仍是 893e 历史身份，不能互相冒充。

## 3. 设计确认状态

- 生成 RTL 只使用公开端口（memory-direct；无 VPI/internal signal config）。内部条目的观察通过响应、way 选择和覆盖推断，不能直接读内部状态。
- **待设计确认/开放**：`TLBFA-LEVEL3-FAKE-PTE-UNREACHABLE` 的 fake-PTE level 3 分支；`WRAPPER-PLRU-NO-INVALID-PRIORITY` 的冷启动替换顺序（性能/老化，不是 ISA 功能失败）；`L2TLB-SATP-NO-SFENCE-STALE` 的 satp/sfence 合法激励定性。
- **已撤回的旧设计根因**：共享叶表零间隔停顿、多 outstanding 停顿、LLPTW 多 allStage、Bitmap back-to-back 等旧 RTL 归因已被修正后的全边沿监视/harness 反证；不得重新当作当前设计结论。
- **范围边界**：MBIST/DFT、物理 way 放置、A/D/privilege 交叉、fake-PTE 架构 fault/GPA、条件化 no-fence liveness、HFENCE.GVMA 定点 GPA 等仍未闭合；详见 [residuals.md](../verification/residuals.md)。
- ISA 对照见 [isa-confirmation-20261026.md](../verification/evidence/reports/isa-confirmation-20261026.md)；ISA 允许 over-fence，也允许 satp inactive 后某些在途翻译不终止，不能把邻页保留或所有 no-fence 完成当作普遍要求。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

沿用既有工程功能合同；本表补充当前源码、生成名与实际放置位置。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `tlbfa` | `TLBFA` | `src/main/scala/xiangshan/cache/mmu/TLBStorage.scala:26` | `XSTop.core_with_l2.core.frontend.inner_itlb.entries.page_itlb_storage_fa` | 已有实现；新基线未验收 |
| `wrapper` | `TlbStorageWrapper` | `src/main/scala/xiangshan/cache/mmu/TLBStorage.scala:339` | `XSTop.core_with_l2.core.frontend.inner_itlb.entries` | 已有实现；新基线未验收 |
| `tlb` | `TLB` | `src/main/scala/xiangshan/cache/mmu/TLB.scala:44` | `XSTop.core_with_l2.core.frontend.inner_itlb` | 已有实现；新基线未验收 |
| `l2mq` | `L2TlbMissQueue` | `src/main/scala/xiangshan/cache/mmu/L2TLBMissQueue.scala:40` | `XSTop.core_with_l2.core.memBlock.inner_ptw.ptw.missQueue` | 已有实现；新基线未验收 |
| `l2pf` | `L2TlbPrefetch` | `src/main/scala/xiangshan/cache/mmu/L2TlbPrefetch.scala:32` | `XSTop.core_with_l2.core.memBlock.inner_ptw.ptw.prefetch` | 已有实现；新基线未验收 |
| `ptwrepeater` | `PTWRepeaterNB` | `src/main/scala/xiangshan/cache/mmu/Repeater.scala:90` | `XSTop.core_with_l2.core.frontend.inner_itlbRepeater2` | 已有实现；新基线未验收 |
| `ptwfilter` | `PTWFilter` | `src/main/scala/xiangshan/cache/mmu/Repeater.scala:465` | `XSTop.core_with_l2.core.frontend.inner_itlbRepeater1` | 已有实现；新基线未验收 |
| `ptw` | `PTW` | `src/main/scala/xiangshan/cache/mmu/PageTableWalker.scala:104` | `XSTop.core_with_l2.core.memBlock.inner_ptw.ptw.ptw` | 已有实现；新基线未验收 |
| `pmp` | `PMP` | `src/main/scala/xiangshan/backend/fu/PMP.scala:345` | `XSTop.core_with_l2.core.frontend.inner_pmp` | 已有实现；新基线未验收 |
| `bitmap` | `Bitmap` | `src/main/scala/xiangshan/cache/mmu/BitmapCheck.scala:104` | `XSTop.core_with_l2.core.memBlock.inner_ptw.ptw.bitmap` | 已有实现；新基线未验收 |
| `bitmapcache` | `BitmapCache` | `src/main/scala/xiangshan/cache/mmu/BitmapCheck.scala:401` | `XSTop.core_with_l2.core.memBlock.inner_ptw.ptw.bitmapcache` | 已有实现；新基线未验收 |
| `ptwcache` | `PtwCache` | `src/main/scala/xiangshan/cache/mmu/PageTableCache.scala:204` | `XSTop.core_with_l2.core.memBlock.inner_ptw.ptw.cache` | 已有实现；新基线未验收 |
| `llptw` | `LLPTW` | `src/main/scala/xiangshan/cache/mmu/PageTableWalker.scala:800` | `XSTop.core_with_l2.core.memBlock.inner_ptw.ptw.llptw` | 已有实现；新基线未验收 |
| `tlbn` | `TLBNonBlock` | 历史接口；参见本页基线边界 | — | 当前 top 缺失；保留历史实现 |
| `l2tlbwrapper` | `L2TLBWrapper` | `src/main/scala/xiangshan/cache/mmu/L2TLB.scala:1260` | `XSTop.core_with_l2.core.memBlock.inner_ptw` | 已有实现；新基线未验收 |
| `l2tlb` | `L2TLB` | `src/main/scala/xiangshan/cache/mmu/L2TLB.scala:48` | `XSTop.core_with_l2.core.memBlock.inner_ptw.ptw` | 已有实现；新基线未验收 |
| `hptw` | `HPTW` | `src/main/scala/xiangshan/cache/mmu/PageTableWalker.scala:1387` | `XSTop.core_with_l2.core.memBlock.inner_ptw.ptw.hptw` | 已有实现；新基线未验收 |
| `ptwfilter_entry` | `PTWFilterEntry` | `src/main/scala/xiangshan/cache/mmu/Repeater.scala:169` | `XSTop.core_with_l2.core.memBlock.inner_dtlbRepeater.load_filter_load_entry` | 骨架；待实现 |
| `pmp_checker` | `PMPChecker` | `src/main/scala/xiangshan/backend/fu/PMP.scala:562` | `XSTop.nocMisc.pma.PMPChecker` | 骨架；待实现 |
| `dtlb_load` | `TLB_1` | `src/main/scala/xiangshan/cache/mmu/TLB.scala:44` | `XSTop.core_with_l2.core.memBlock.inner_dtlb_ld_tlb_ld` | 骨架；待实现 |
| `dtlb_store` | `TLB_2` | `src/main/scala/xiangshan/cache/mmu/TLB.scala:44` | `XSTop.core_with_l2.core.memBlock.inner_dtlb_st_tlb_st` | 骨架；待实现 |
| `dtlb_prefetch` | `TLB_3` | `src/main/scala/xiangshan/cache/mmu/TLB.scala:44` | `XSTop.core_with_l2.core.memBlock.inner_dtlb_prefetch_tlb_prefetch` | 骨架；待实现 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。

**TLBNonBlock 边界：** 当前源码及 RTL 无 TLBNonBlock；load/store/prefetch 使用 TLB 的三个具体变体。旧 tlbn 的多端口合同和实现保留，不能重命名后当作已适配。新 dtlb_load/store/prefetch分别建骨架；原 tlb 键在当前基线对应 Frontend 的 ITLB。
