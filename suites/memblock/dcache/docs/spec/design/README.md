# DCache Design spec

状态：**整理入口，设计确认待完成**。本页把现有合同、层次说明和功能点收敛到设计入口；
设计要求主要来自固定基线 RTL、Chisel 源码和已有验证合同，尚未记录设计 owner 的逐条确认。
因此这些条目是当前验证依据，不等同已签核的微架构规格。

适用基线：最近完整证据绑定 `public-893e1580b` / DefaultConfig；当前根默认基线为
`public-a0c2a26cb`，本工程尚未在该基线重新生成 RTL、构建或回归。实际选用版本以
`ucv info dcache` 和根配置为准。

## 1. 范围与层次

本工程覆盖 DCache 顶层、MemBlock 边界的 `DCacheWrapper`，以及 11 个内部/叶块 DUT。
各 DUT 的功能点文档描述可观察行为、合法域、时序和已知边界；顶层结论不能自动外推到
未实例化或未驱动的 Uncache、WPU、CSR 等旁路。

| DUT 键 | 顶层 | 层次 | 设计要求入口 |
|---|---|---|---|
| `duplicated_tag_array` | DuplicatedTagArray | 叶（标签） | [DTA 功能点](functional-points-duplicated-tag-array.md) |
| `ctrl_unit` | CtrlUnit | 叶（控制寄存器/伪错误注入） | [CU 功能点](functional-points-ctrl-unit.md) |
| `miss_ready_gen` | MissReadyGen | 叶（miss 请求直通） | [MRG 功能点](functional-points-miss-ready-gen.md) |
| `counter_filter` | CounterFilter | 叶（预取过滤 FIFO） | [CF 功能点](functional-points-counter-filter.md) |
| `miss_track` | MissTrack | 中（推测 miss 历史） | [MT 功能点](functional-points-miss-track.md) |
| `load_pipe` | LoadPipe | 中（load 流水） | [LP 功能点](functional-points-load-pipe.md) |
| `banked_data_array` | BankedDataArray | 中（数据阵列） | [BDA 功能点](functional-points-banked-data-array.md) |
| `main_pipe` | MainPipe | 上（store/atomic/refill/probe） | [MP 功能点](functional-points-main-pipe.md) |
| `miss_queue` | MissQueue | 上（MSHR/CMO） | [MQ 功能点](functional-points-miss-queue.md) |
| `probe_queue` | ProbeQueue | 上（B 通道 probe） | [PQ 功能点](functional-points-probe-queue.md) |
| `writeback_queue` | WritebackQueue | 上（C 通道写回） | [WQ 功能点](functional-points-writeback-queue.md) |
| `dcache` | DCache | 顶（完整缓存子系统） | [DC 功能点](functional-points-dcache.md) |
| `dcache_wrapper` | DCacheWrapper | MemBlock 边界封装 | [WFP 功能点](functional-points-dcache-wrapper.md) |

真实实例化层次、容量、通道数、SRAM 行宽、ECC 和工具锁见 [层次与参数](hierarchy.md)。
源码路径和导出名由 [ucv.json](../../../ucv.json) 与 `ucv info dcache` 提供。

## 2. 接口、配置与合法输入

- DCache 顶层通过 LSU load/store/atomic/CMO、B 通道 probe、C 通道 writeback 和两条
  TileLink A/D 通道对外；L2 传输检查的独立依据与当前边界见
  [L2 传输合同](l2-transport-contract.md)。
- 64 KiB、256 set × 4 way、64B line、2 个 L2 通道、3 条 load 流水；miss/probe/release
  条目数、ECC 和预取能力以 `hierarchy.md` 与生成 RTL 为准。
- 复位释放后 tag/meta SRAM 按 256 拍逐 set 清扫；清扫完成前不发起功能事务。
- 当前所有工程使用 DefaultConfig；工程不增加单 DUT 的源码或配置 override。
- 本工程只使用公开端口，不启用 VPI 或 internal signal config；运行期不保存波形或逐周期 dump。

## 3. 行为要求与已知边界

逐 DUT 的稳定功能点 ID、合法情形、时序与观察点维护在功能点文档中。跨模块顶层要求见：

- [DC-FP-001..013](functional-points-dcache.md)：reset/清扫、load 命中与窗口掩码、冷 miss/refill、
  预取标记、替换/写回阻塞、双通道、store 主流水、MSHR 耗尽、refill 错误、probe、
  victim 写回、AMO 和 CMO。
- [WFP-001..007](functional-points-dcache-wrapper.md)：861 端口 1:1 映射、改名组、spec fabric
  透传、核心行为回放、双通道/source、perf 两级延迟和复位边界。

当前已确认 RTL 缺陷：`MQ-STORE-MERGE-DATA-PENDING`。同一 cache line 的第二笔部分
store 合并后字节丢失，详见 [问题记录](../../bugs/open/MQ-STORE-MERGE-DATA-PENDING.md)。
相关功能点 `DC-FP-007` 和 `MQ-FP-002` 已标注该缺陷，不能把严格 xfail 当作通过。

`DCacheWrapper` 内只有一个 `DCache` 实例，不包含 Uncache 数据通路或仲裁、flush/drain
状态机、CSR/中断或第三条 L2 通道；这些内容不属于本 DUT，若需验证应建立 MemBlock 或
相应用例的子块 DUT。该边界是设计范围说明，不是缺陷；稳定 ID 和原依据见
[验证约束](../verification/constraints.md#wrapper-no-uncache-logic)。

## 4. 依据与待确认问题

- 功能点中的寄存器映射、地址函数、编码和时序依据来自对应 Chisel/Scala 源码与生成
  RTL；每条文档中给出的行号/文件只用于定位当时基线，不自动迁移到新基线。
- L2 TileLink 检查依据来自该基线 rocket-chip `tilelink/Monitor.scala` 与真实 A/D/C 行为；
  bench 注入只用于检查器反例，不宣称做过 RTL mutation。
- 功能点审计记录修正过若干“文档与 RTL 相反”的期望；历史修正见
  [功能点复核](../verification/evidence/functional-point-audit-20261025.md)。
- 待确认：设计 owner 对各条行为要求的逐条确认、wrapper perf 两级延迟的设计承诺、
  CounterFilter 无复位流水是否由上游修复，以及 Uncache/DCache 仲裁的验证归属。
- 设计要求变更使用 Git review；新增要求分配稳定 ID，并在验证规格中登记场景与证据。
