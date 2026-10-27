> 迁移前历史说明。当前命令与基线见仓库根 README；以下记录不代表重建版本验收。

# MMU/TLB 分层 UT 验证工程

> **当前入口：验证可信度复核** — 见 `docs/reports/verification-soundness-20261025.md`。
> 原 376 PASS + 5 XFAIL 是历史基线；5 个 XFAIL 均发现验证侧问题，旧 RTL 根因结论
> 已撤回。当前最终重跑与残余义务以该复核报告及 soundness evidence 为准。


本工程验证 XiangShan `kunminghu-v3` 的地址翻译路径，使用 Picker 生成最小 DUT，
toffee main 分支 runner 执行 pytest。验证顺序遵循生成 RTL 的真实实例化层次，
自底向上推进；每个模块先写人类可读的微架构语义功能点，再开发测试、运行功能检查，
最后用行/toggle/branch 覆盖率逐项定位缺口并补测复跑。

## 1. 基线与范围

| 项 | 值 |
|---|---|
| 源码 | `../../XiangShan/`，提交 `893e1580b705d81f113c30c7a05734e09a08050e` |
| RTL | `../../soc-split/rtl/` 的原样副本，不修改字节 |
| 工具 | Picker `2.0.0-HEAD-4dd442c`、Verilator `5.052`、toffee `2.0.0.dev12+g3017293a7` |
| 运行入口 | `/home/xyl/xreactor/output/toffee-migration/venv/bin/toffee run` |
| 波形 | 正常运行不保留波形；覆盖数据库按 run 提交，不用逐周期 dump 替代检查 |

真实层次（由生成 RTL 实例化关系确认，不是按 Scala 文件划分）：

```text
TLBFA (48-way fully-associative sector storage leaf)
  └─ 被 TlbStorageWrapper 实例化（ITLB 路径）
       └─ 被 TLB 实例化（Frontend ITLB）
TlbStorageWrapper_1 + TLBFA_1
  └─ 被 TLBNonBlock 实例化（MemBlock DTLB load 等）
Frontend/MemBlock
  ├─ PTWFilter（Frontend 8 项 ITLB 待处理过滤器）
  └─ PTWRepeaterNB（Frontend/MemBlock 的单 outstanding 重复器）
L2TLBWrapper → L2TLB
  ├─ L2TlbMissQueue
  ├─ PtwCache
  ├─ PTW / HPTW / LLPTW
  ├─ Bitmap / BitmapCache / PMP
  ├─ L2TlbPrefetch
  └─ arbiters
```

`TLBFA` 是 `TlbStorageWrapper` 的真实叶子，不是 Python 模型替代品。`TLBFA`
的参数在生成 RTL 中已经固定：

- 1 个读端口、48 个 way、单 set 全相联。
- 38 位 VPN、36 位物理页号、8 个 4KB 子页（sector）。
- Sv48（Level=3），支持 4KB/2MB/1GB/512GB 与 NAPOT 64KB。
- 16 位 ASID、14 位 VMID，支持 noS2xlate / onlyStage1 / onlyStage2 / allStage。

## 2. 目录

```text
mmu/
├── README.md
├── docs/
│   ├── functional-points-*.md       # 各层语义功能点
│   └── reports/                     # 覆盖闭环报告与轮次证据
├── manifest/                        # baseline / toolchain / RTL 哈希 / known issues
├── rtl/<dut>/                       # 原样 RTL 的最小依赖闭包
├── dut/<dut>/                       # Picker 生成 DUT
├── mmuverify/
│   ├── common/                      # DUT 加载、执行辅助
│   ├── tlbfa/ wrapper/ tlb/         # L1 路径独立模型/env/覆盖
│   └── l2/                          # L2 叶子、PTWFilter/Repeater、L2TLB env
├── tests/
│   ├── tlbfa/ wrapper/ tlb/
│   └── l2/
├── tools/                           # build / run / coverage audit / delivery check
└── results/                         # 只保留最终 run、构建报告和 baseline replay
```

## 3. 运行

```sh
python3 tools/build_dut.py tlbfa --jobs 8
python3 tools/build_dut.py wrapper --jobs 8
python3 tools/build_dut.py tlb --jobs 8
python3 tools/build_dut.py l2mq --jobs 8
python3 tools/build_dut.py l2pf --jobs 8
python3 tools/build_dut.py ptwrepeater --jobs 8
python3 tools/build_dut.py ptwfilter --jobs 8
python3 tools/build_dut.py ptwcache --jobs 8
python3 tools/build_dut.py tlbn --jobs 8
python3 tools/build_dut.py hptw --jobs 8
python3 tools/build_dut.py ptw --jobs 8
python3 tools/build_dut.py pmp --jobs 8
python3 tools/build_dut.py bitmap --jobs 8
python3 tools/build_dut.py bitmapcache --jobs 8
python3 tools/build_dut.py llptw --jobs 8
python3 tools/build_dut.py l2tlb --jobs 8
python3 tools/build_dut.py l2tlbwrapper --jobs 8

python3 tools/run.py --name tlbfa-final --workers 1 tests/tlbfa
python3 tools/run.py --name l2tlb-new-unique-run --workers 1 tests/l2/test_l2tlb.py
python3 tools/coverage_audit.py l2tlb-new-unique-run
python3 tools/verify_delivery.py
```

覆盖审计保留行/toggle/branch 分母，按源文件分离 Picker harness 与真实 RTL；
未覆盖点不会被删除或按分母重算。

## 4. 当前状态（2026-10-26）

17 个真实 RTL DUT suite 共 **395 PASS**，另有 **13 checker/model 自检 PASS**，
合计 **408 PASS，0 FAIL/XFAIL/SKIP**。按 collection 分类：390 functional、
2 characterization、3 structural-stress、13 checker-selftest。实现刻画和压力
不充当功能要求闭合；sampled bins 100% 不代表 ISA/交叉覆盖完整。

| 模块/组合 | PASS | 行 covered/total | toggle covered/total | branch covered/total | 最终 run |
|---|---:|---:|---:|---:|---|
| TLBFA | 31 | 3419/3419 | 17766/17766 | 1016/1018 | `soundness-final-tlbfa-01` |
| TlbStorageWrapper | 8 | 3431/3431 | 18798/18798 | 1019/1022 | `soundness-final-wrapper-01` |
| TLB | 25 | 3655/3657 | 18785/23074 | 1094/1104 | `soundness-final-tlb-01` |
| TLBNonBlock | 30 | 4839/4956 | 20486/37422 | 1424/1568 | `soundness-final-tlbn-01` |
| L2TlbMissQueue | 5 | 24/24 | 829/854 | 17/18 | `soundness-final-l2mq-01` |
| L2TlbPrefetch | 6 | 39/39 | 657/784 | 22/23 | `soundness-final-l2pf-01` |
| PTWRepeaterNB | 7 | 72/72 | 3114/3114 | 7/8 | `soundness-final-ptwrepeater-01` |
| PTWFilter | 14 | 206/206 | 4412/4414 | 91/92 | `soundness-final-ptwfilter-01` |
| HPTW | 21 | 133/133 | 5069/5270 | 97/98 | `soundness-final-hptw-01` |
| PTW | 30 | 530/530 | 12213/15344 | 418/420 | `soundness-final-ptw-01` |
| PMP | 12 | 2117/2117 | 47680/51404 | 437/470 | `soundness-final-pmp-01` |
| BitmapCache | 12 | 314/323 | 6953/14174 | 124/148 | `soundness-final-bitmapcache-01` |
| Bitmap | 19 | 994/1415 | 2138/6636 | 290/398 | `soundness-final-bitmap-01` |
| PtwCache | 50 | 13744/13748 | 95616/110892 | 3182/3226 | `soundness-final-ptwcache-01` |
| LLPTW | 27 | 1660/1955 | 4330/20770 | 359/407 | `soundness-final-llptw-01` |
| L2TLB | 46 | 17079/22249 | 96980/255430 | 4330/6304 | `soundness-final-l2tlb-02` |
| L2TLBWrapper | 52 | 17460/22289 | 96604/260640 | 4430/6304 | `soundness-final-l2tlbwrapper-02` |

- 五个历史 XFAIL 被验证侧有效激励/全通道握手反证推翻，不再视为 RTL 缺陷。
- 最终索引：`docs/reports/evidence/soundness-20261025/final-runs.json`；
  残余和源码差异见同目录 `final-residuals.json`、`source-drift-review.json`。
- wrapper -01 的未对齐大页用例失败及旧归因保留，当前基线采用 -02。
- ISA 对照：`docs/reports/isa-confirmation-20261026.md`。SFENCE 允许 over-fence，
  satp inactive 时旧在途翻译存在例外；不能把邻页保留或所有 no-fence 完成
  当成普遍 ISA 要求。
- **仍开放**：fake-PTE 架构 fault/GPA、条件化 no-fence liveness、HFENCE 定点 GPA、
  A/D/privilege 交叉覆盖，以及残余合法功能状态/数据序列；MBIST/DFT 排除。
- **不是整颗 MMU/SoC 或 ISA 签核**。详细发现见可信度复核报告。
- 最终自检：`python3 tools/verify_delivery.py` → `results/delivery-audit.json`。
  检查 RTL/build/coverage/source 哈希、seed、无未处置 XFAIL、collection、固定
  PMA oracle 和残余披露；16 项新交付判定正/负向检查不加到 408 总数。
- committed 不是 git 提交。本轮未提交或推送，也未修改 DUT RTL。

## 5. 历史报告

旧模块/交付报告仅为历史证据，由可信度复核取代：
`docs/reports/final-delivery-20261025.md`、
`docs/reports/final-delivery-phase2-20261025.md`。
原 baseline 与交付配置保留在 soundness evidence 的 before 快照。
