# DCache 验证基线与真实层次

## 1. 来源与工具锁

| 项 | 值 |
|---|---|
| 源码 | `../../../XiangShan`，分支 `kunminghu-v3`，提交 `893e1580b705d81f113c30c7a05734e09a08050e`（2026-10-16） |
| RTL | `../../../soc-split/rtl`（firtool-1.149.0 split-verilog），逐文件哈希见 `manifest/rtl-sha256.json` |
| Picker | `2.0.0-HEAD-4dd442c-2026-10-12` |
| Verilator | `/opt/verilator-5.052` |
| toffee | `2.0.0.dev12+g3017293a7`，`migration/toffee` 分支，入口 `toffee run` |
| 构建选项 | `--rw mem_direct -w memory-direct.fst -c --vflag=--no-coverage-expr --no-coverage-fsm` |
| 运行选项 | `toffee run --workers N --output results/<fresh> --export-coverage-json --native-coverage-tool /opt/verilator-5.052/bin/verilator_coverage` |
| 随机性 | Verilator 固定 seed `1` |

不使用 VPI、不配置内部信号：所有检查都在公开端口上完成。正常运行不打开波形，不产生逐周期 dump；Picker 默认 `$dumpfile` 落在临时 cwd。

## 2. 生成 RTL 的实际参数（DefaultConfig）

`meta/XSTop.json` 与 `DCacheWrapper.scala` 交叉确认：

| 参数 | 值 | 证据 |
|---|---|---|
| DCache 容量 | 64 KiB | `d-cache-size:65536`，`d-cache-sets:256` |
| sets / ways / block | 256 / 4 / 64B | `XSTop.json`，`WithNKBL1D(64, ways=4, numMemChannels=2)` |
| L2 通道 | 2（`auto_client_nodes_out_0/1_*`） | `DCache.sv` 端口 |
| banks / SRAM 行宽 | 32 / 16 bit | `DCacheWrapper.scala` `DCacheBanks=32`，`DCacheSRAMRowBits=16` |
| miss / probe / release 条目 | 16 / 8 / 18 | `Parameters.scala` |
| tag/data ECC | SECDED，均启用 | `Parameters.scala` |
| cacheCtrl | 存在（0x38022000） | `CtrlUnit cacheCtrlOpt` 实例 |
| 预取 | `nMaxPrefetchEntry=6`，CounterFilter 存在 | `DCache.sv` 实例 |

## 3. 真实内部层次（来自 `DCache.sv` 实例化）

```text
DCache
├── CtrlUnit                      # TL 寄存器：pseudo tag/data error 注入
├── BankedDataArray               # 32 bank × 4 way × 16B 行，line read + 复制写端口
├── L1CohMetaArray                # 一致性状态（SRAM 叶块）
├── L1ErrorMetaArray              # TL denied/corrupt 错误标记
├── L1PrefetchSourceArray         # 预取来源标记
├── L1RefillLatencyArray          # refill 延迟标记（GenLatencyArray 关闭时不存在）
├── L1FlagMetaArray               # access 标记
├── DuplicatedTagArray (4 读端口)  # 4 份 TagArray，每份 2 个 TagSRAMBank × 2 way
│   └── TagArray → TagSRAMBank ×2 → SRAMTemplate_278 / 256×86 SRAM
├── PrefetcherMonitor
├── CounterFilter                 # FDP 计数过滤
├── LoadPipe ldu_0/1/2            # 3 条 load 流水
├── MainPipe                      # store/atomic 主流水 + refill 写回
│   └── AMOALU
├── MissQueue (16 MissEntry + CMOUnit)
├── ProbeQueue (8 ProbeEntry)
├── WritebackQueue (18 WritebackEntry)
├── MissTrack (16 项)
├── MissReadyGen                  # 4 路 miss 请求直通/背压
└── Arbiter*（tag/data 写仲裁）
```

`DCacheWrapper.scala:1044` 的 `DCacheImp` 是上述接线的来源；`CtrlUnit.scala`、`meta/TagArray.scala`、`loadpipe/LoadPipe.scala`、`mainpipe/*.scala`、`loadpipe/MissTrack.scala` 分别给出各块语义。

## 4. 验证顺序（自下而上）

| 阶段 | DUT | 层次 | 关键语义 |
|---|---|---|---|
| P1 | `DuplicatedTagArray` | 叶 | 复位全清扫描、4 读端口、way 掩码写、单端口读写冲突、SECDED 编码 |
| P1 | `CtrlUnit` | 叶 | TL 寄存器映射、pseudo error 注入（bank/mask/comp/ede/persist） |
| P1 | `MissReadyGen` | 叶 | 4 路 miss 请求直通与 ready 背压 |
| P1 | `CounterFilter` | 叶 | load 历史计数、3 个查询端口的过滤语义 |
| P2 | `MissTrack` | 中 | 16 项分配/命中/owner/install/invalidate/clear/spec 查询 |
| P2 | `LoadPipe` | 中 | s0/s1/s2 流水、tag/meta/data、hit/miss、kill、bank conflict |
| P2 | `BankedDataArray` | 中 | 32 bank 路由、way/word 读写、line read、复制写端口、ECC 错误 |
| P3 | `MainPipe` | 上 | store/atomic、tag/data 写、refill 写回、错误标记、miss 请求 |
| P3 | `MissQueue` | 上 | MSHR 分配/合并、refill、release、probe 冲突、CMO |
| P3 | `ProbeQueue` | 上 | TileLink B 通道 probe 生命周期 |
| P3 | `WritebackQueue` | 上 | TileLink C 通道写回生命周期 |
| P4 | `DCache` | 顶 | 命中、miss/refill、store 合并、probe/writeback、error、flush/reset |

尚未单列：`L1CohMetaArray` 等 SRAM 元数据阵列。它们与 `DuplicatedTagArray` 共用 SRAMTemplate 行为，先由父块（MainPipe/DCache）覆盖；若父块覆盖率显示缺口集中在这些叶块，再提升为独立 DUT。该边界在 README 与最终报告中保留。

## 5. 循环方法

每个 DUT 执行同一闭环：

1. `docs/functional-points-<dut>.md`：用人类可读的微架构语义描述功能点与情形枚举；
2. 独立参考模型 + 端口级 driver/monitor + 语义覆盖组（toffee `CoverGroupDef`）；
3. 通过 `tools/run.py` 在 toffee runner 下运行并导出功能覆盖与原生覆盖率；
4. `tools/coverage_audit.py` 统计 line/toggle/branch，列出未覆盖过程行、连续块、分支与 toggle 点；
5. 逐项归因：已有功能点的情形缺失 → 补情形；整体功能点缺失 → 补功能点；工具/范围限制 → 记录证据；
6. 补用例重跑，记录覆盖率变化与仍未关闭项。

## 6. MemBlock 边界：DCacheWrapper（2026-10-25 补充）

`MemBlock.sv` 直接实例化 `DCacheWrapper inner_dcache` 和 `Uncache inner_uncache`，
两者平级。`DCacheWrapper.sv` 内部只有一个 `DCache` 实例：

- **861 个端口 1:1 映射**：766 同名直连、53 改名（14 个
  `auto_cacheCtrlOpt_in_*` → `auto_uncache_in_*`；39 个
  `auto_spec_fabric_source_out_*` → `auto_dcache_spec_fabric_source_out_*`）、
  42 个 perf 输出经 wrapper 内两级寄存器。
- wrapper 内没有 Uncache 数据通路、没有 uncache 仲裁、没有第三条 L2 通道、
  没有 flush/drain 状态机。
- 因此 `DCacheWrapper` 的 UT 目标是边界保真（映射完整性 + 改名组走通 + perf 延迟）
  和 DCache 场景原样回放；Uncache 与 DCache 的仲裁应在 `MemBlock` 或 uncache
  仲裁子块上验证。

端口映射的可审计产物：`manifest/dcache-wrapper-portmap.json`
（由 `tools/wrapper_portmap.py` 从实例化文本自动生成）。
