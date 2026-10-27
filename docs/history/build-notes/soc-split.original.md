# soc-split — XiangShan kunminghu-v3 拆分 RTL

本目录存放 XiangShan `kunminghu-v3` 分支生成的**块级拆分 RTL**（不含仿真 top），
以及前端模块稳定性分析报告。

## 1. 来源

| 项 | 值 |
|---|---|
| 仓库 | `https://github.com/OpenXiangShan/XiangShan`（开源版） |
| 分支 | `kunminghu-v3` |
| 提交 | `893e1580b705d81f113c30c7a05734e09a08050e` |
| 提交时间 | 2026-10-16 11:47:07 +0800 |
| 提交标题 | `perf(param): enlarge ROB size to 160 (#6730)` |
| 生成入口 | `top.TopMain`（纯 XSTop，不含 `SimTop` / testbench） |
| 配置 | `DefaultConfig`，`NUM_CORES=1` |
| 工具 | mill + Chisel 7.13.0 + firtool 1.149.0 |
| 生成命令 | `NOOP_HOME=$(pwd) make verilog CONFIG=DefaultConfig NUM_CORES=1` |
| 原始产物目录 | `XiangShan/build/rtl/`（已整体移入本目录） |

## 2. 目录结构

```
soc-split/
├── README.md            # 本文件
├── MANIFEST.tsv         # 全部 RTL 文件清单（文件名 + 字节数）
├── rtl/                 # 1978 个 .sv + 22 个 .v + filelist.f
├── fir/                 # XSTop.fir（FIRRTL，约 1.4 GB）
├── reports/             # 前端稳定性分析
│   ├── frontend_block_stability.md       # 块级结论（主报告）
│   └── frontend_file_stability_appendix.md  # 逐文件统计（附录）
└── meta/                # 生成元数据
    ├── XSTop.dts
    ├── XSTop.json
    ├── XSTop.plusArgs
    ├── XSTop.MbistFrontend.csv
    ├── XSTop.MbistL2.csv
    ├── XSTop.MbistMemBlk.csv
    └── time.log
```

| 项 | 值 |
|---|---|
| `.sv` 文件数 | 1,978 |
| `.v` 文件数（difftest 生成） | 22 |
| 空文件 | 0 |
| `rtl/` 体积 | 约 0.1 GB |
| 全目录体积 | 约 1.5 GB（含 `fir/`） |
| difftest 端口 | 无（纯净 RTL） |

`rtl/filelist.f` 共 2,000 条，覆盖全部 RTL 文件；其中 23 条使用 `./` 前缀
（`ClockGate.sv`、21 个 `DiffExt*.v`、`PrintCommitIDModule.v`），编译时按相对路径解析。

## 3. 主要模块入口文件

| 模块 | 文件 | 字节 |
|---|---|---|
| SoC 顶层 | `rtl/XSTop.sv` | 184,671 |
| 前端顶层 | `rtl/Frontend.sv` | 814,389 |
| BPU | `rtl/Bpu.sv` | 1,047,773 |
| FTQ | `rtl/Ftq.sv` | 7,094,199 |
| IFU | `rtl/Ifu.sv` | 904,697 |
| IBuffer | `rtl/IBuffer.sv` | 770,689 |
| ICache | `rtl/ICache.sv` | 131,483 |
| InstrUncache | `rtl/InstrUncache.sv` | 3,738 |
| MemBlock | `rtl/MemBlock.sv` | 1,401,785 |

`Bpu.sv` 内实例化 `Tage`、`Sc`、`Ras`、`Phr`、`MicroTage`、`MicroRas`、`MicroBtb`、
`MainBtb`、`Ittage`、`FallThroughPredictor`、`CommonHR`、`AheadBtb`；
`Ftq.sv` 内实例化 `ResolveQueue`、`CommitQueue`；
`Ifu.sv` 内实例化 `PredChecker`、`InstrBoundary`、`IfuUncacheUnit`、`FrontendTrigger` 和 37 个 `RvcExpander`。

各子块均为独立 `.sv`，可直接作为 UT 的 DUT 边界：

- **BPU**：`Tage.sv`、`TageTable`、`Sc.sv`、`ScTable`、`MainBtb.sv`、`MainBtbAlignBank`、
  `MainBtbInternalBank`、`MicroBtb.sv`、`Ittage.sv`、`IttageTable`、`MicroTage.sv`、
  `MicroTageTable`、`Ras.sv`、`RasStack`、`MicroRas.sv`、`Phr.sv`、`CommonHR.sv`、
  `AheadBtb.sv`、`FallThroughPredictor.sv`、`WriteBuffer`、`CompareMatrix`
- **FTQ**：`Ftq.sv`、`ResolveQueue.sv`、`CommitQueue.sv`
- **IFU**：`Ifu.sv`、`IfuUncacheUnit.sv`、`IfuPerfAnalysis.sv`、`InstrUncacheEntry.sv`
- **ICache**：`ICacheMainPipe.sv`、`ICacheWayLookup.sv`、`ICacheMissUnit.sv`、
  `ICacheMshr.sv`（及 13 个实例）、`ICachePrefetchPipe.sv`、`ICacheDataArray.sv`、
  `ICacheDataBank.sv`（及 7 个实例）、`ICacheMetaArray.sv`、`ICacheMetaInterleavedBank.sv`、
  `ICacheReplacer.sv`、`ICacheCtrlUnit.sv`
- **MemBlock**：`MemBlock.sv`、`DCacheWrapper.sv`、`LsqWrapper.sv`、`Sbuffer.sv`、
  `NewLoadUnit.sv`、`NewStoreUnit.sv`、`PTWNewFilter`、`L2TLBWrapper` 等

## 4. 使用注意

1. **无仿真 top**：本目录只包含 `XSTop` 及其子模块，不含 `SimTop`、`TestHarness`
   或 difftest DPI 顶层。单独仿真需自备 testbench。
2. **断言宏**：`make verilog` 会对所有 `.sv` 执行
   `sed 's/$fatal/xs_assert_v2(`__FILE__, `__LINE__)/g'`，
   因此产物依赖 `` `xs_assert_v2 `` 宏。单独编译某个 block 时，需引入
   `XiangShan/src/main/resources` 下的宏定义，或把该替换改回 `$fatal`。
3. **difftest `.v`**：22 个 `DiffExt*.v` 与 `PrintCommitIDModule.v` 由 difftest 导出，
   仅在带 difftest 的仿真中使用；纯 DUT 单测可忽略，但 `filelist.f` 已包含它们。
4. **可综合性**：`--lowering-options=explicitBitcast,disallowLocalVariables,disallowPortDeclSharing`
   与 `-O=release` 为默认发布选项，SRAM 已保持为独立模块（未做工艺映射）。
5. **重建**：`XiangShan/build/rtl/` 已被移走，如需重跑 `make verilog` 会重新生成。

## 5. 前端稳定性结论（摘要）

详细数据见 `reports/frontend_block_stability.md`。

| 块 | 近6月提交 | fix6 | 近1月 | 最近改动 | 结论 |
|---|---|---|---|---|---|
| InstrUncache | 2 | 1 | 0 | 2026-05-25 | **稳定，首选 UT 目标** |
| FTQ | 30 | 14 | 0 | 2026-09-16 | 大改完成、冷却窗口，可做 |
| ICache | 19 | 8 | 2 | 2026-10-14 | 半稳定，建议拆子块 |
| IFU | 24 | 17 | 2 | 2026-10-10 | 不稳定，暂缓 |
| IBuffer | 17 | 9 | 2 | 2026-10-10 | 不稳定，暂缓 |
| BPU | 55 | 26 | 3 | 2026-10-12 | 仍活跃，暂缓 |
| *MemBlock（参照）* | *124* | *55* | *10* | *2026-10-14* | *高度活跃，暂缓* |
