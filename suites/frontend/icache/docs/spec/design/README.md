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
