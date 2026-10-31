# 第一阶段交付报告（历史快照）

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


> **可信度复核更正（2026-10-25）**：本报告保留旧 run 的历史指标；当前归因以
> `verification-soundness-20261025.md` 为准。原 5 个 strict XFAIL 的 DUT 缺陷归因
> 已被验证侧反证推翻；“100% sampled bins”不等于功能验收或不可达证明。


> 第二阶段更新（2026-10-25）：TLBNonBlock、TLB GPA 重放、Bitmap deny、L2TLB
> PMA/PMP、PTW full_gvpn、HPTW accessFault 观察等已补齐；部分第一阶段指标已被
> 新的最终 run 取代。最新闭合项、残余边界和证据见
> [第二阶段交付报告](final-delivery-phase2-20261025.md)。
> 资源说明：第一阶段的旧完整 run 目录已在本阶段按资源策略裁剪；本报告中的
> 指标来自当时已审计的 run，compact 历史审计保留在 `docs/reports/evidence/`，
> 最新可复现的最终 run 以第二阶段报告为准。


## 1. 结论与范围声明

本工程在 `memblock-hash/mmu` 下，用 Picker + toffee main 对 XiangShan
`kunminghu-v3` 的 TLB/MMU 路径按真实生成 RTL 层次自底向上开展 UT。所有 DUT
均由 `soc-split/rtl` 的字节级副本构建，不使用 Python 模型替代任何 RTL 子块；
页表内存、PMP/PMA 配置和 HPTW 响应仅作为测试侧激励/参考模型。

最终交付包含 **16 个独立 DUT/组合 run**、**331 个 PASS 用例 + 2 个 strict
XFAIL**。每个 run 的 `manifest.json` 均为 `state=committed`、
`coverage_complete=true`、`pytest_exitstatus=0`。

**不声称整个 MMU 已验收。** 明确未验证范围见 §5。

## 2. 真实层次与验证状态

```text
TLBFA (48-way fully-associative sector storage leaf)        [closed]
  └─ TlbStorageWrapper                                        [closed]
       └─ TLB (Frontend ITLB)                                 [closed main; GPA replay open]
TLBFA_1 / TlbStorageWrapper_1
  └─ TLBNonBlock (MemBlock DTLB)                              [NOT VERIFIED]

Frontend/MemBlock
  ├─ PTWFilter                                                [closed]
  └─ PTWRepeaterNB                                            [closed]

L2TLBWrapper                                                  [closed combination]
  └─ L2TLB                                                    [closed main]
       ├─ L2TlbMissQueue                                      [closed]
       ├─ L2TlbPrefetch                                       [closed]
       ├─ PtwCache                                            [closed]
       ├─ PTW / HPTW / LLPTW                                  [PTW/HPTW closed; LLPTW main closed]
       ├─ Bitmap / BitmapCache / PMP                          [Bitmap partial; others closed]
       └─ arbiters / SRAM                                      [structural]
```

## 3. 最终 run 汇总

| 层次/模块 | 用例 | 行覆盖 | branch | toggle | 功能 | 最终 run |
|---|---:|---:|---:|---:|---:|---|
| `TLBFA` | 31 | 3419/3419 = 100% | 1016/1018 | 17766/17766 = 100% | 100% | `tlbfa-full-06` |
| `TlbStorageWrapper` | 8 | 3431/3431 = 100% | 1019/1022 | 18798/18798 = 100% | 100% | `wrapper-full-06` |
| `TLB` (ITLB) | 24 | 3644/3657 = 99.6% | 1089/1104 | 18716/23074 = 81.1% | 100% | `tlb-sweep-12` |
| `L2TlbMissQueue` | 5 | 24/24 = 100% | 17/18 | 829/854 | 100% | `l2mq-03` |
| `L2TlbPrefetch` | 6 | 39/39 = 100% | 22/23 | 657/784 | 100% | `l2pf-05` |
| `PTWRepeaterNB` | 7 | 72/72 = 100% | 7/8 | 3114/3114 = 100% | 100% | `ptwrepeater-06` |
| `PTWFilter` | 12 | 206/206 = 100% | 91/92 | 4380/4414 | 100% | `ptwfilter-14` |
| `HPTW` | 20 | 133/133 = 100% | 97/98 | 5065/5270 = 96.1% | 100% | `hptw-final-01` |
| `PTW` | 28 | 519/530 = 97.9% | 413/420 | 12118/15344 = 79.0% | 100% | `ptw-final-02` |
| `PMP` | 11 | 2117/2117 = 100% | 437/470 | 47680/51404 = 92.8% | 100% | `pmp-final-02` |
| `BitmapCache` | 12 | 314/323 = 97.2% | 124/148 | 6953/14174 = 49.0% | 100% | `bitmapcache-final-06` |
| `Bitmap` | 16 + 1 XFAIL | 955/1415 = 67.5% | 266/398 | 2104/6636 = 31.7% | 100% | `bitmap-final-06` |
| `PtwCache` | 50 | 13741/13748 = 99.949% | 3179/3226 | 87398/110892 = 78.8% | 100% | `ptwcache-final-02` |
| `LLPTW` | 23 | 1656/1955 = 84.706% | 359/407 | 4302/20770 = 20.7% | 100% | `llptw-final-03` |
| `L2TLB` 顶层 | 34 | 16976/22249 = 76.30% | 4297/6304 | 95703/255430 = 37.5% | 100% | `l2tlb-final-04` |
| `L2TLBWrapper` | 44 + 1 XFAIL | 17689/22289 = 79.362% | 4442/6304 | 101986/260640 = 39.1% | 100% | `l2tlbwrapper-final-01` |

说明：

- `L2TLB` 顶层和 `L2TLBWrapper` 的数字包含真实子块，不能与子块行数相加；
  `L2TLBWrapper` 本体自己的 40 行可执行代码为 40/40 = 100%。
- `Bitmap` 的 1 个 XFAIL 是 back-to-back PMP 检查别名
  `BITMAP-PMP-BACKTOBACK-LOST`，strict marker。
- `L2TLBWrapper` 的 1 个 XFAIL 是共享叶子表 back-to-back miss 停顿
  `L2TLB-PREFETCH-SHARED-LEAF-STALL`，strict marker。

## 4. 本轮新增交付（2026-10-25）

### 4.1 PtwCache 独立叶级闭环

- 50 PASS，功能 100%，行 13741/13748 = 99.949%，branch 3179/3226，
  toggle 87398/110892 = 78.8%，最终 `ptwcache-final-02`。
- 覆盖 L0/L1/L2/L3/SP 全 set/way、64KB NAPOT、sfence/hfence 全作用域、
  bitmap jump/wakeup 全 64×4×8 位、深背压 RAM 回读、零/全 1 极性。
- 残余 7 行为 3 条 SRAM 复位 + 4 条 L3 one-hot 声明式分支；branch/toggle
  残余已分类为 MBIST/DFT、SRAM 宏、initial 随机、Picker harness 和物理 way
  放置/数据极性，不是缺失功能点。

### 4.2 LLPTW 独立叶级闭环

- 23 PASS，功能 100%，行 1656/1955 = 84.706%，branch 359/407，
  toggle 4302/20770，最终 `llptw-final-03`。
- 从上一版 11 PASS / 功能 91.67% / 行 65.2% 提升；补齐 allStage 两阶段、
  第一次/第二次 HPTW gpf/gaf、stage2 权限与 MXR、onlyStage2、cache retry、
  slot 1..5 放置。
- 关键环境修复：`io_hptw_req_valid` 是 `ready & arb_valid` 的组合信号，
  `service()` 每拍 `RefreshComb()` 后才能捕获单拍 HPTW 请求。
- 残余 299 行分类为重复等待/最后 HPTW 的 per-entry 情况枚举；多个 allStage
  并发请求仍未验证（`LLPTW-MULTI-STAGE2-UNVERIFIED`）。

### 4.3 L2TLBWrapper 组合闭环

- 44 PASS + 1 strict XFAIL，功能 100%（235 samples），包装层本体 40/40 行，
  组合行 17689/22289 = 79.362%，branch 4442/6304，最终
  `l2tlbwrapper-final-01`。
- 64 页 4KB working set 覆盖全部 PtwCache L0 set/lane，回放零内存读；
  PtwCache 单独 +399 行。
- 逐拍 trace 证明功能字段与 L2TLB 完全一致、19 路 perf 全部满足
  `wrapper[t] == l2tlb[t-2]`，比较结果 PASS 0 failures。

## 5. 明确未验证/未闭合范围

1. **TLBNonBlock（MemBlock DTLB）**：使用独立 TLBFA_1/TlbStorageWrapper_1，
   未建立 DUT，未验收。
2. **TLB GPA/getGpa 重放**：ITLB 的 13 行 guest-page-fault GPA 路径未验证。
3. **多个 allStage LLPTW 请求并发**：2 个 allStage 并发探针在 4 次 HPTW 请求后
   停顿，原因未隔离；单 allStage 在 slot 1..5 已验证。
4. **L2TLB 多于 2 个在途请求**：8 个 back-to-back 请求探针未完成，原因未隔离。
5. **共享叶子表 back-to-back miss**：strict XFAIL；加 8 拍间隔后 64 页全部成功。
6. **Bitmap deny/多 miss 并发**：独立叶级只验证 allow-all；back-to-back PMP
   检查有 strict XFAIL。
7. **PMA 配置、bitmap deny、PTW 高 VPN/512GB、MBIST/DFT**：未验收或不在 UT 范围。
8. **PtwCache/LLPTW 残余 branch/toggle**：已逐项分类，未用伪造激励填充。
9. **HPTW accessFault 复位行为**：记录为候选 RTL 缺陷，独立测试在 reset 后补
   sfence；需设计确认。
10. **satp.changed 不执行 sfence、sfence rs1=0/rs2=0 重走**：行为观察，未定性。

## 6. 证据索引

| 内容 | 路径 |
|---|---|
| 基线/层次/参数 | `manifest/baseline.json` |
| 工具版本/seed | `manifest/toolchain.json`、`mmuverify/common/dut.py`（seed=1） |
| RTL 哈希 | `manifest/*-rtl.sha256` |
| 已知问题/候选缺陷 | `manifest/known-issues.json` |
| 功能点文档 | `docs/functional-points-*.md` |
| 各层报告 | `docs/reports/*.md` |
| 轮次/前后覆盖证据 | `docs/reports/evidence/cycle-*/` |
| 交付自检 | `results/delivery-audit.json`、`tools/verify_delivery.py` |
| 最终覆盖数据库 | `results/<final-run>/coverage-audit.json` 等 |

## 7. 资源占用

- 结果目录：约 **268 MB**，包含 16 个最终 run 的 coverage dat/lcov/html、
  3 个 baseline replay 和 16 个构建报告；中间 probe/dbg run 已裁剪。
- compact 证据目录：约 **5.6 MB**。
- 默认不保存波形/逐周期事务；所有功能检查只保留最终 trace JSON 和覆盖审计。
- 每个 DUT 构建报告记录 Picker/Verilator 版本、命令、RTL 哈希和 smoke 结果。

## 8. 复现

```sh
cd memblock-hash/mmu
for dut in tlbfa wrapper tlb l2mq l2pf ptwrepeater ptwfilter hptw ptw pmp \
           bitmap bitmapcache ptwcache llptw l2tlb l2tlbwrapper; do
  python3 tools/build_dut.py "$dut" --jobs 8
done
python3 tools/run.py --name tlbfa-full-06 --workers 1 tests/tlbfa
# ... 其余最终 run 的命令见各层报告
python3 tools/verify_delivery.py
```

`tools/verify_delivery.py` 逐项校验 RTL 哈希、构建报告、最终 run 的
manifest/功能/行/toggle/branch 数字、XFAIL 数量和必需报告，当前
**PASS 0 failures**。
