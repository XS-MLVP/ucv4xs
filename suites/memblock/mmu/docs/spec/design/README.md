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
