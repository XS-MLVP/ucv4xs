# DCacheWrapper 功能点（本轮 UT 范围）

DUT：`DCacheWrapper`（`soc-split/rtl/DCacheWrapper.sv`），层次：MemBlock 直接实例化的
DCache 子系统边界。`MemBlock.sv` 里 `DCacheWrapper inner_dcache (...)`，旁边是独立的
`Uncache inner_uncache`。

## 0. 先厘清 wrapper 到底做了什么（重要）

阅读 `DCacheWrapper.sv` 与 `DCacheWrapper.scala` 后的事实：

- wrapper 内部**只有一个实例**：`DCache dcache (...)`（`DCacheWrapper.sv:1225`）。
- 861 个端口与 `DCache` 的 861 个端口构成**1:1 映射**：
  - 766 个同名直连（`auto_client_nodes_out_0/1_*`、`io_lsu_*`、`io_lqEmpty` 等）；
  - 14 个改名：`auto_cacheCtrlOpt_in_*` → `auto_uncache_in_*`；
  - 39 个改名：`auto_spec_fabric_source_out_*` → `auto_dcache_spec_fabric_source_out_*`；
  - 42 个 perf 计数输出是内部两级寄存器（`io_perf_N_value_REG` →
    `_REG_1` → `io_perf_N_value`），这是 wrapper 唯一自己的时序逻辑。
- `DCacheWrapper` 内**没有**：Uncache 数据通路、uncache 与 DCache 的仲裁、第三条 L2 通道、
  flush/drain 状态机。真实的 `Uncache` 在 `MemBlock.sv` 里与 `DCacheWrapper` 平级实例化
  （`MemBlock.sv:7891 Uncache inner_uncache (...)`），uncache 的 A/D 通道仲裁也在
  MemBlock 层完成。

因此本轮把 wrapper 的验证目标定为"**边界保真 + 端到端可用**"，而不是虚构它不存在的
仲裁逻辑：

1. 端口映射必须完整、1:1、无遗漏（从 RTL 自动提取，不靠人工假设）；
2. 每一个被改名的端口组都要实际走通（cache-control 寄存器可读写、speculative fabric
   信号透传）；
3. 通过 wrapper 端口驱动时，DCache 的全部核心行为（命中/miss/refill、store、probe、
  eviction、AMO、CMO、错误）结果不变——即 wrapper 不吞事件、不迟滞、不改数据；
4. perf 计数在 wrapper 边界有 2 拍延迟，这是设计行为，需要固定下来。

> 若后续需要验证"Uncache 与 DCache 的仲裁/返回"，正确的 DUT 是 `MemBlock`（或
> `MemBlock` 内的 uncache 仲裁器），不是 `DCacheWrapper`。本报告第 7 节记录这一范围
> 边界与后续入口。

## WFP-001 结构等价：861 端口 1:1 映射

`DCacheWrapper` 对 `DCache` 是纯结构封装：每个对外端口都在实例化里精确连接一次，
不存在悬空、重复连接或多路复用。验证方式不是读代码，而是用
`tools/wrapper_portmap.py` 从 `DCacheWrapper.sv` 的实例化文本自动提取 861 条连接，
检查：连接数 861、内部唯一端口数 861、重复连接 0，并输出
`manifest/dcache-wrapper-portmap.json` 作为可审计产物。

- 情形：连接数/唯一性校验；改名组恰好 53 条（14 cacheCtrl + 39 spec fabric）；
  identity 组 766 条；perf 内部 net 42 条不计入对外端口。

## WFP-002 端口改名保真：cache-control TL slave

wrapper 把 `DCache` 的 `auto_cacheCtrlOpt_in_*`（14 位/字段）改名为
`auto_uncache_in_*`。这是 MemBlock 侧访问 DCache 控制寄存器（0x3802_2000 一段）的唯一
入口。验证：通过 `auto_uncache_in_*` 发 TileLink 读写，DCache 内部的 `CtrlUnit`
寄存器必须正确响应：

- 写 `ctrl`（offset 0x00）后读回同值；写 `delay`、`tagMask`、`dataMask` 组后读回；
- 写响应 opcode = AccessAck（0），读响应 opcode = AccessAckData（1），
  `d_source`/`d_size` 回显请求；
- 部分 `a_mask` 的写不改变寄存器（与 CtrlUnit 的字节掩码语义一致）。

这条同时证明改名组两端连的是同一份逻辑，而不是各接了一个悬空口。

## WFP-003 端口改名保真：speculative-miss fabric

`auto_dcache_spec_fabric_source_out_*`（39 条）是 DCache 向 MemBlock 的 speculative miss
预留接口（3 个 candidate + 3 个 resolve + 3 个 committed 等）。验证：

- wrapper 侧看到的 candidate `valid`/`vaddr`/`paddr`/`channel` 必须与 DCache 内部产生
  的一致：用 `DCache` 顶层用例相同的冷 miss 场景，检查 wrapper 的 candidate 输出；
- `committed_*` 输入从 wrapper 端口注入后，能影响 DCache 的 spec 行为（例如
  resolve 的 `commit` 位跟随 `committed_*`）；
- 空闲时必须为 0（无悬空/未知值）。

## WFP-004 核心 DCache 行为经 wrapper 边界不变

把 DCache 顶层的 23 个用例原样跑在 wrapper 端口上（同一份激励、同一套参考模型），
结果必须逐项一致（其中 1 个是已知缺陷的严格 xfail，在 wrapper 上同样失败）：

- load 命中、3 lane 并行、S2 `handled` 语义；
- 冷 miss → AcquireBlock(6,size6) → 2×GrantData → 重放命中，数据逐字节一致；
- 双 L2 通道按 `paddr[6]` 选择，两个通道各自完成；
- store 命中/掩码合并、store miss（整行走 AcquirePerm，部分走 AcquireBlock+合并）；
- MSHR 耗尽 replay；
- denied/corrupt refill 的 `io_error`；
- B 通道 probe → C 通道 ProbeAck(Data)；
- dirty/clean victim 的 C 通道 Release(Data)，以及写回阻塞契约（Release 未接受时同
  block 被拒、drain + ReleaseAck 后恢复）；
- AMO swap/add 命中与 refill 完成；
- CMO clean/flush/inval × denied/corrupt；
- 约束随机 load/store 混合（L2 shadow + 未写回字节模型）。

**已知缺陷**：第二笔合并 store 的字节丢失（`MQ-STORE-MERGE-DATA-PENDING`）在 wrapper
上同样可复现（继承 DCache 的 xfail 用例），说明 wrapper 不会掩盖下级缺陷。

这一条是"wrapper 不得改变下级行为"的直接证据：同一断言在 `DCache` 和
`DCacheWrapper` 两个 DUT 上都通过，且观测到的地址/数据/opcode 相同。

## WFP-005 双通道与 source 映射在边界处保持不变

wrapper 不重排、不缓冲 A/D/C 通道。用两个通道各做一次 refill（`paddr[6]=0/1`），
检查：Acquire 出现在与 `paddr[6]` 对应的 wrapper 通道；`source` 字段原样回传；
D 通道 `source` 与 A 通道 `source` 一致；`sink` 原样。另一通道在事务期间保持 idle。

## WFP-006 perf 计数在边界处两级寄存

wrapper 唯一自己的时序逻辑：`io_perf_N_value` = 两级寄存的
`_dcache_io_perf_N_value`（`DCacheWrapper.sv:1037-1038, 2745`）。验证：

- 复位后 perf 输出为 0；
- 触发一次会累加 perf 的事件（例如一次 load miss），确认 wrapper 的 perf 值在
  2 拍后才反映、而不是与内部同拍；
- 42 个 perf 端口全部有定义值（无 X/悬空）。

## WFP-007 复位与空闲边界

wrapper 复位必须把内部 DCache 一并复位：复位释放后按 DCache 的 256 拍 SRAM 清扫流程
等待，期间不得发事务；清扫完成后 load 命中路径可用。同时检查 wrapper 在无请求时
A/C 通道 `valid=0`、B/D `ready` 不被外部输入拉低（这些是 DCache 输出，wrapper 不驱动）。

## 7. 范围边界（本轮不做，及原因）

| 目标 | 为什么不放在 DCacheWrapper |
|---|---|
| Uncache 与 DCache 的 A/D 仲裁、uncache 返回 | `DCacheWrapper.sv` 内没有 Uncache 实例；`Uncache` 与 `DCacheWrapper` 在 `MemBlock.sv` 平级，仲裁在 MemBlock 层。需要新建 `MemBlock`（或其 uncache 仲裁子块）DUT。 |
| flush / drain 状态机 | DCache 侧没有独立的 flush 端口；flush 由 Sbuffer/外部控制流与 probe/release 完成。DCacheWrapper 不新增该逻辑。 |
| CSR / 中断上报 | wrapper 只有控制寄存器 TL slave（WFP-002 已覆盖）；中断不在本模块。 |
| L2 协议细节（TL 规范一致性） | 由各 A/D 通道的定向用例与 DCache 内部 MissQueue/WritebackQueue 覆盖。 |

## 覆盖组

- `wrapper.portmap`：端口组（identity / cacheCtrl / spec_fabric）× 校验结果。
- `wrapper.ctrl`：控制寄存器 index × 读写 × 掩码形态。
- `wrapper.core`：核心行为类别（hit / miss_refill / store / probe / eviction / atomic /
  cmo / error）× 结果。
- `wrapper.channel`：通道 0/1 × Acquire/Grant。
- `wrapper.perf`：perf 端口组 × 延迟。
