# ICache 设计规格

状态：**待设计 owner 确认**。本工程没有独立的设计规格正文；本页只汇总验证所依据的
层次、职责、配置和接口边界。各 DUT 的详细合同、期望来源与观察点分别记录在验证文档
与事务合同中，入口见[验证规格](../verification/README.md)，不能把本页当作完整微架构规格。

## 范围与层次

基线：`public-a0c2a26cb` / DefaultConfig / 单核。整块 `ICache` 与它的子块分别作为
平级 DUT 构建和验证，避免外层适配或兄弟子块改动改变另一个 DUT 的测试面；整块
`ICache` 闭包保留真实子模块 RTL。

| DUT | RTL top | 设计职责 | 模块级材料 |
|---|---|---|---|
| `waylookup` | `ICacheWayLookup` | 预取/取指回填元信息队列、flush 与异常条目 | [覆盖闭环](../verification/coverage/waylookup-coverage-closure.md)、[缺陷复核](../verification/error-review.md) |
| `replacer` | `ICacheReplacer` | tree-PLRU、端口分派与 victim 反馈 | [覆盖闭环](../verification/coverage/replacer-coverage-closure.md) |
| `mshr` | `ICacheMshr` | 单条目 miss 状态与完成释放 | [新基线逐 DUT 覆盖记录](../verification/reports/baseline-update-a0c2a26cb.md) |
| `databank` | `ICacheDataBank` | way-mask 写、全 way 读的 SRAM 数据面 | [事务适配](../verification/transactions/databank-transaction-adaptation.md)、[SRAM 覆盖](../verification/coverage/sram-dut-coverage-limitation.md) |
| `metabank` | `ICacheMetaInterleavedBank` | 交织元数据 bank、有效位与全清 | [事务适配](../verification/transactions/metabank-transaction-adaptation.md)、[SRAM 覆盖](../verification/coverage/sram-dut-coverage-limitation.md) |
| `metaarray` | `ICacheMetaArray` | 交织 bank 路由与有效位模型 | [SRAM 覆盖](../verification/coverage/sram-dut-coverage-limitation.md) |
| `dataarray` | `ICacheDataArray` | bank 交织路由与多行请求 | [SRAM 覆盖](../verification/coverage/sram-dut-coverage-limitation.md) |
| `missunit` | `ICacheMissUnit` | fetch/prefetch MSHR 仲裁、TileLink 请求与回填 | [覆盖闭环](../verification/coverage/missunit-coverage-closure.md) |
| `mainpipe` | `ICacheMainPipe` | 需求取指的命中/缺失、ECC 与异常路径 | [覆盖闭环](../verification/coverage/mainpipe-prefetchpipe-coverage-closure.md) |
| `prefetchpipe` | `ICachePrefetchPipe` | 预取请求、waylookup 写入和 flush 豁免 | [覆盖闭环](../verification/coverage/mainpipe-prefetchpipe-coverage-closure.md) |
| `icache` | `ICache` | 顶层组合、FTQ/IFU/ITLB/PMP/TileLink 接口 | [整块覆盖闭环](../verification/coverage/icache-coverage-closure.md) |

## 配置与合同来源

- 配置、端口和真实闭包以 `ucv.json`、有效基线和生成 RTL/构建收据为准；
  具体 set/way、MSHR 数量和总线宽度不在本页重复，避免与配方漂移。
- 参考模型依据 ISA/公开协议/教科书语义（VIPT 组相联、循环 FIFO、tree-PLRU、
  MSHR 纪律、RISC-V Svpbmt/fence.i/WFI/ECC 语义）和 Scala 接口意图；不从 RTL 赋值
  反推期望。
- 生成器会裁剪常量、去掉 verification layer 的 `$fatal`、把部分字段降级为
  don't-care。哪些端口/字段可观察、哪些属于结构裁剪，按各 DUT 的覆盖闭环和
  [错误复核](../verification/error-review.md)记录。
- 缺失对端由只使用公开端口的事件驱动辅助模型提供（TL 存储/寄存器从端、
  FTQ/IFU/ITLB/PMP、replacer 对端等）；它们不是 DUT 替身。

## 合法输入与责任边界

- 所有激励必须来自 DUT 的公开合法域；非法高位、非对齐、未定义组合和端口级任意压力
  单独归类，不冒充生产可达。
- `WAYLOOKUP-020` 的 flush 同拍写属于子模块接口合同；整块 ICache 中当前不可达，
  但仍是未修复 RTL 问题，不能删除反例。
- `ICACHE-012` 的 stale `vSetIdx` 已由上游拆除；`ICACHE-030` 的合并路径已随接口退役，
  ICache 侧义务改为“未完成握手的预取 issue 不得触达内存”。
- 其他配置、Frontend/后端消费、真实 L2 行为和芯片验收不在本设计边界内。

## 未确认项

- `Frontend` 与 ICache 的软预取/重定向交互由 FTQ、IFU 和顶层集成工程承接，本工程
  只验证 ICache 侧握手与数据面。
- `frontend/design` 尚未对 `WAYLOOKUP-020` 的修复或接受方式签字；当前保留 strict
  XFAIL。
- 覆盖闭环中的结构不可达与 don't-care 归因属于当前配置的工程判断，配置变化后需重做
  [覆盖分析](../verification/coverage/icache-coverage-closure.md)。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

沿用既有工程功能合同；本表补充当前源码、生成名与实际放置位置。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `waylookup` | `ICacheWayLookup` | `src/main/scala/xiangshan/frontend/icache/ICacheWayLookup.scala:30` | `XSTop.core_with_l2.core.frontend.inner_icache.wayLookup` | 已有实现；新基线未验收 |
| `replacer` | `ICacheReplacer` | `src/main/scala/xiangshan/frontend/icache/ICacheReplacer.scala:24` | `XSTop.core_with_l2.core.frontend.inner_icache.replacer` | 已有实现；新基线未验收 |
| `mshr` | `ICacheMshr` | `src/main/scala/xiangshan/frontend/icache/ICacheMshr.scala:28` | `XSTop.core_with_l2.core.frontend.inner_icache.missUnit.allMshr_0` | 已有实现；新基线未验收 |
| `databank` | `ICacheDataBank` | `src/main/scala/xiangshan/frontend/icache/ICacheDataBank.scala:24` | `XSTop.core_with_l2.core.frontend.inner_icache.dataArray.banks_0` | 已有实现；新基线未验收 |
| `metabank` | `ICacheMetaInterleavedBank` | `src/main/scala/xiangshan/frontend/icache/ICacheMetaInterleavedBank.scala:24` | `XSTop.core_with_l2.core.frontend.inner_icache.metaArray.banks_0` | 已有实现；新基线未验收 |
| `metaarray` | `ICacheMetaArray` | `src/main/scala/xiangshan/frontend/icache/ICacheMetaArray.scala:24` | `XSTop.core_with_l2.core.frontend.inner_icache.metaArray` | 已有实现；新基线未验收 |
| `dataarray` | `ICacheDataArray` | `src/main/scala/xiangshan/frontend/icache/ICacheDataArray.scala:22` | `XSTop.core_with_l2.core.frontend.inner_icache.dataArray` | 已有实现；新基线未验收 |
| `missunit` | `ICacheMissUnit` | `src/main/scala/xiangshan/frontend/icache/ICacheMissUnit.scala:31` | `XSTop.core_with_l2.core.frontend.inner_icache.missUnit` | 已有实现；新基线未验收 |
| `mainpipe` | `ICacheMainPipe` | `src/main/scala/xiangshan/frontend/icache/ICacheMainPipe.scala:37` | `XSTop.core_with_l2.core.frontend.inner_icache.mainPipe` | 已有实现；新基线未验收 |
| `prefetchpipe` | `ICachePrefetchPipe` | `src/main/scala/xiangshan/frontend/icache/ICachePrefetchPipe.scala:34` | `XSTop.core_with_l2.core.frontend.inner_icache.prefetcher` | 已有实现；新基线未验收 |
| `icache` | `ICache` | `src/main/scala/xiangshan/frontend/icache/ICacheImp.scala:39` | `XSTop.core_with_l2.core.frontend.inner_icache` | 已有实现；新基线未验收 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。
