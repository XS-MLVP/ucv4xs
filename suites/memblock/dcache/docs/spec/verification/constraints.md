# DCache 验证约束

本页保存**设计/验证范围约束**，不是当前缺陷，也不表示设计或接口已经退役。条目沿用历史
`manifest/known-issues.json` 的稳定 ID、原分类和依据；它们不再放在 `docs/bugs/`，因为
`open`/`closed` 记录只表示需要处置的问题。当前缺陷和误报分类见 [bugs/](../../bugs/README.md)。

最近完整验证绑定 `public-893e1580b`；当前默认基线为 `public-a0c2a26cb`，本工程尚未在
当前基线重新构建或回归。以下约束本身仍需在对应 DUT 范围内遵守。

| 稳定 ID | 原分类 | 当前处理 |
|---|---|---|
| `WRAPPER-NO-UNCACHE-LOGIC` | `documented_scope` / `closed_by_design` | 范围约束，不放进 bug 台账 |

## WRAPPER-NO-UNCACHE-LOGIC

- **原分类**：`documented_scope` / `closed_by_design`；稳定 ID 保留为
  `WRAPPER-NO-UNCACHE-LOGIC`。
- **约束**：`DCacheWrapper.sv` 内部只有一个 `DCache` 实例，不包含 Uncache 数据通路、
  uncache 与 DCache 的仲裁、第三条 L2 通道或 flush/drain 状态机。真实 `Uncache` 在
  `MemBlock.sv` 中与 `DCacheWrapper` 平级实例化，仲裁在 MemBlock 层完成。
- **对验证的影响**：DCacheWrapper 的 UT 只覆盖边界保真（861 端口 1:1、改名组、spec
  fabric 透传、核心 DCache 行为回放、双通道/source、perf 两级延迟）；不能用它验证
  Uncache 仲裁，也不能在本工程中虚构该逻辑。需要覆盖时另建 MemBlock 或 uncache
  仲裁子块 DUT。
- **依据**：
  - [DCacheWrapper 功能点第 0 节与第 7 节](../design/functional-points-dcache-wrapper.md)
  - [DCacheWrapper UT 报告](evidence/dcache-wrapper-20261025.md)
  - [端口映射审计产物](../../../manifest/dcache-wrapper-portmap.json)（由
    [wrapper_portmap.py](../../../tools/wrapper_portmap.py) 生成）
  - [历史问题台账](../../../manifest/known-issues.json) 的同名条目
- **当前状态**：约束；不需要修复，也不属于本轮文档整理的设计/接口退役。
