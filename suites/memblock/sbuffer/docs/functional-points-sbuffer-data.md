# Sbuffer 分层 UT：功能点、合同与状态

本工程只验证 `Sbuffer` 真实子树，顺序为 **SbufferData（内部数据/掩码阵列）→ Sbuffer（顶层）**。
功能点先用人类可读的微架构语义描述“这块硬件保证什么”，再映射到测试用例与覆盖 bin；
枚举值只作为语义的边界情况出现，不单独构成功能点。

源码基线：`kunminghu-v3 @ 893e1580`（`../../XiangShan`），RTL 取自
`../../soc-split/rtl/`，哈希见 `manifest/sbuffer-rtl.sha256`。

## 1. 层次与职责

```
Sbuffer（顶层，16 项 Store Buffer 行）
└── SbufferData（dataModule）
    ├── 16 行 × 4 个 16B lane × 16 字节的 data 阵列
    ├── 同形状的 mask 阵列（bit=1 表示该字节有尚未写出的 store 数据）
    └── 按行清理 mask、按 16B 粒度 merge 新 store 数据
```

来源：`Sbuffer.scala:191`（`Sbuffer`）、`Sbuffer.scala:97`（`SbufferData`）、
`Sbuffer.scala:218`（`val dataModule = Module(new SbufferData)`）、
`Sbuffer.sv:16742`（`SbufferData dataModule`）。

`SbufferData` 的输入只来自 `Sbuffer` 的两级入队流水（`writeReq`）和 DCache 命中写回
（`maskFlushReq`）；它没有自己的 valid/ready，数据在固定延迟后生效。因此 `SbufferData`
的 UT 关注“存储语义 + 固定延迟”，`Sbuffer` 的 UT 才关注握手、状态机和跨模块交互。

## 2. SbufferData 功能点

> 语义约定：行 `line∈[0,16)`、lane `vword∈[0,4)`、字节 `byte∈[0,16)`；
> `mask[line][vword]` 的 bit `b` 表示该字节有未写出的 store 数据；
> `vwordOffset` 的 `[1:0]` 选择 lane；`wvec` 是行级写使能位图。

### SBD-WRITE-01 字节掩码写
一笔窄写只改变目标行、目标 lane 中 mask 选中的字节：`mask` 位 `b` 对应 lane 内第 `b`
个字节，未选中的字节保持原来的数据和 mask。语义上这是“把一个 store 的字节掩码 merge
进 cacheline 的 16B 窗口”，而不是覆盖整个 lane。
**观察**：`maskOut` 目标 lane 的选中位置 1、未选中位保持不变；`dataOut` 选中字节等于 payload 的低/高对应字节。

### SBD-WRITE-02 整行写广播
`wline=1` 表示整条 64B cacheline 写：忽略 `mask`，把 16B payload 依次复制到该行 4 个 lane
的 16 个字节位置，并把该行 64 个 mask 位全部置 1。零 payload 与任意非零 payload 都是
同一语义（父块目前只会发整行为 0 的 wline，但数据模块本身不限制）。
**观察**：该行 4×16 个 mask 全 1，4 个 lane 的字节都等于 payload 对应字节。

### SBD-WRITE-03 16B lane 选择
`vwordOffset[1:0]` 选择 4 个 16B lane 之一；更高位是页内地址，不参与 lane 选择。
因此低 2 位相同、高位不同的两次写必须落在同一个 lane 上。
**观察**：只有目标 lane 的 mask 变化；高位取全 1 时结果不变。

### SBD-WRITE-04 行位图广播
`wvec` 是行级写使能位图：每个置位行都接收同一笔 payload，未置位行完全不受影响。
父块当前只发 one-hot（新行或 merge 行），但模块合同允许同一拍选中多行；这是“同一笔
store 数据可被写到多个同名行”的硬件语义，不是简单的位枚举。
**观察**：多个置位行的 mask/data 同时更新，其余行不变。

### SBD-WRITE-05 无效写不改变状态
`valid=0` 时，即使 `wvec`、`mask`、`data`、`wline` 任意，也不更新任何行。
**观察**：全 1024 个 mask 位与已知数据字节均保持不变。

### SBD-WRITE-06 两拍写入延迟
请求在第一个上升沿被 s1 捕获，在下一个上升沿由 s2 才更新存储；捕获拍不得提前看到新
值。这是 `Sbuffer` 入队两级流水（`sbuffer_in_s1/s2`）的合同基础。
**观察**：驱动后第一个上升沿输出与驱动前完全一致；第二个上升沿才出现预期变化。

### SBD-WRITE-07 双端口同拍写入
两个写端口同一拍可以各自写入。不同行、不同 lane、同一 lane 内不重叠字节互不破坏；
同一字节被两个端口同时写时，1 号端口的数据/mask 覆盖 0 号端口（生成 RTL 的赋值顺序）。
该重叠属于模块级优先级，父块正常使用不会制造重叠写，测试只记录这一行为，不把它当作
父块合法并发域。
**观察**：分别检查四种组合的完整 mask 和字节数据。

### SBD-WRITE-08 写入累积
同一行不同 lane 的连续写会累积 mask；后写不清除先前 lane 的 mask。同一 lane 的后续写
只替换其 mask 覆盖的字节，其余字节保留。
**观察**：连续 4 拍写满 4 个 lane 后 mask=0xFFFF×4；再写部分字节只更新对应位。

### SBD-FLUSH-01 命中后按行清 mask、保数据
`maskFlushReq` 置位的行在捕获后第二拍 mask 全清（表示该行已写出），`dataOut` 保留最后
写入的数据。未置位行完全不变。清 mask 不等于清数据。
**观察**：目标行 4 个 lane mask 全 0，已知字节数据仍等于写过的值。

### SBD-FLUSH-02 清理是行位图
清理同样是行级位图：可同拍清理多行，16 个行槽都可被独立清理。父块用 DCache 命中
响应的 id 生成 one-hot，但模块语义是位图。
**观察**：多行同时清 0，未选行不变。

### SBD-FLUSH-03 清理与写同拍
同一行同拍既有清理又有写时，先清空整行 mask，再应用写请求覆盖的字节。因此被写字节的
mask 保持 1，其余字节清 0，数据保留；清理和写作用于不同行时互不影响。
**观察**：同拍组合后的完整 mask 是“清理后的 0”再按写 mask 置位。

### SBD-FLUSH-04 无效清理不生效
`valid=0` 时 `wvec` 不产生清理效果。
**观察**：目标行 mask 保持不变。

### SBD-RESET-01 复位
复位清空所有行所有 lane 的 mask。复位期间在途的写被取消，不会在复位释放后把旧 payload
写回。`data` 不要求初始化；复位后只能比较之后实际写入过的字节，不能把随机数据当已知值。
**观察**：所有 mask=0；复位后继续写新数据，旧请求不出现。

### SBD-STABLE-01 空闲保持
没有请求时，`dataOut/maskOut` 保持上一拍值，不自发变化。
**观察**：连续多个空闲拍与上一拍快照完全相等。

## 3. 功能点 → 用例 → 覆盖 bin

| 功能点 | 用例 | 功能覆盖点 |
|---|---|---|
| SBD-WRITE-01/06 | `test_single_byte_each_lane` | `write_shape=single_byte`、`byte_lane`、`write_line_slot`、`lane_slot` |
| SBD-WRITE-02 | `test_wline_broadcast` | `write_shape=wline_zero/wline_payload`、`lane_slot`、`write_line_slot` |
| SBD-WRITE-03 | `test_vword_offset_alias_high_bits` | `offset_alias=high_bits_ignored`、`lane_slot` |
| SBD-WRITE-04 | `test_wvec_multi_line_broadcast` | `write_line_slot`、`line_x_lane` |
| SBD-WRITE-05 | `test_invalid_write_does_nothing` | `write_shape`（不采样）、`idle_context` |
| SBD-WRITE-07 | `test_dual_port_combinations` | `port_usage`（5 个 bin） |
| SBD-WRITE-08 | `test_back_to_back_accumulate`、`test_all_lines_all_lanes` | `line_x_lane`、`write_line_slot`、`lane_slot` |
| SBD-FLUSH-01/02 | `test_flush_single_multi_all` | `flush_extent`、`flush_line_slot` |
| SBD-FLUSH-03 | `test_flush_and_write_same_cycle` | `flush_concurrency=same_line/other_line` |
| SBD-FLUSH-04 | `test_invalid_flush_does_nothing` | `flush_concurrency=flush_only` |
| SBD-RESET-01 | `test_reset_clears_and_cancels_pending` | `reset_context`（3 个 bin） |
| SBD-STABLE-01 | `test_idle_stability` | `idle_context`（3 个 bin） |
| 合法随机组合 | `test_random_legal_traffic` | 交叉覆盖、补充随机边界 |

覆盖点只在实际比较成功后采样；驱动但未检查的事件不计数。覆盖分母保留全部已定义 bin，
不因未命中而删除。

## 4. 合法输入域与 don't-care

- 写请求的 `wvec` 在当前父块中 one-hot；模块级允许多行，按功能点 04 验证。
- 双端口同一字节重叠只作为模块级优先级记录；父块不应产生。
- `dataOut` 在未写过的字节上是未初始化值；只比较模型标记为“已知”的字节。
- 复位期间不驱动新事务（除专门的复位用例）。
- `vwordOffset[43:2]` 对 SbufferData 是 don't-care；低 2 位决定 lane。
- `maskFlushReq` 在父块中 one-hot；模块级允许多行。

## 5. 当前状态

- 已完成：源码/RTL 层次核对、RTL 复制与 SHA-256、Picker DUT 导出、原生冒烟走时钟。
- 已完成：15 个功能用例全部 PASS；功能覆盖 4 组 100%；DUT LCOV 8518/8518、toggle
  70684/70684、branch 2115/2116（唯一缺口为时间零 `initial` 的 else）。
- 已完成：Sbuffer 顶层功能点与用例，见 [functional-points-sbuffer.md](functional-points-sbuffer.md)。
- 复现与证据见 [SbufferData 报告](reports/sbuffer-data-20261024.md)。
