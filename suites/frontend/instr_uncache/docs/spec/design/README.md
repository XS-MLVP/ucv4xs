# InstrUncache 设计规格

状态：合同已按 Scala、ISA/TileLink 和生成端口整理；**`Frontend` 的 flush 连接设计
决定没有 owner 签字**。详细正文直接采用迁移后的[合同](contracts.md)，本页只给出
层次、配置和需要显式确认的设计边界。

## 范围与层次

| 层 | DUT | RTL top | 角色 |
|---|---|---|---|
| 1 | `instr_uncache_entry` | `InstrUncacheEntry` | 单 outstanding 四状态 MMIO 取指状态机，8B Get、4B 窗口、resend、needResend、WFI |
| 1 | `instr_uncache_resp_arbiter` | `Arbiter1_InstrUncacheResp` | `nMmioEntry=1` 时 Chisel `Arbiter` 退化成的 1:1 响应线 |
| 2 | `instr_uncache` | `InstrUncache` | 真实 Entry + 真实 Arbiter，外加 TL A/D、fromIfu/toIfu、wfi |

顶层 DUT 保留生成的真实 Entry/Arbiter RTL；Python 参考模型只提供期望值。
`Arbiter1_InstrUncacheResp` 不是独立 Scala 类名，而是
`new Arbiter(new InstrUncacheResp, nMmioEntry)` 在 `nMmioEntry=1` 后的生成模块名。
`public-a0c2a26cb` 的生成 `XSTop.fir` 把该模块的 source loc 记为 Chisel 库的
`chisel3/util/Arbiter.scala:149`，实例位置为 `InstrUncacheImp.scala:43`；因此
`workspace.json` 的 `chisel` 登记实例化源文件和 `InstrUncacheResp` 的 bundle 定义，
不把生成模块冒充成香山工程内的独立 Scala 类。

## 配置与结构事实

- DefaultConfig：`nMmioEntry=1`、8B Get、4B 窗口；合法物理地址上限 `2^43`。
- `Frontend.scala:266` 把 `instrUncache.io.flush` 恒接 `false.B`，唯一实例在
  `Frontend.scala:125`；`EnableSimFrontend` 默认 false，`SimFrontendInlinedImp` 也把
  整个 `instrUncache.io` 接 0。
- 生成的 `InstrUncache.sv`（24 端口）和 `InstrUncacheEntry.sv`（23 端口）没有
  `flush`/`needFlush`；`Frontend.sv` 的实例也没有 flush 连接。
- 闭包没有 `io_id`、`io_mmioGrant_ready`、`io_resp_ready`；A 通道只引出 `address`
  与 `user_memPageType_NC`/`user_memBackType_MM`，opcode/size/source/mask 由
  `edge.Get` 固定。
- A 地址 bit47 固定为 0（Scala `Cat` 只产生 47 位）；合法物理地址不会触及该位。
- 生成闭包没有 `needFlush` 寄存器；`nMmioEntry=1` 使响应仲裁退化为 1:1。

## 行为合同

- **Entry**：单 outstanding 四状态机；请求/对齐/4B 抽取/跨 8B resend/跨页
  needResend/异常/WFI/reset/响应丢失按合同。
- **响应仲裁**：`nMmioEntry=1` 时 1:1 映射，D source 过滤和响应有效性由顶层合同约束。
- **顶层**：fromIfu 请求到 TL A、TL D 到 toIfu，wfi 与取消路径按 DefaultConfig 的
  裁剪边界；flush 恒 0，取消路径不可达。
- 时序、字段域和端口裁剪的完整条款见[合同](contracts.md)；功能点 ID 和 checker 映射
  见[功能点](functional-points.md)。

## 未确认项与开放问题

- **`FRONTEND-FLUSH-CONNECT`（blocking/open）**：要求 `frontend/design` 确认
  `false.B` 是永久意图并写入合同，或补上真实 flush 连接/删除端口。确认前整体保持
  INCOMPLETE；本单元不能声称 flush 已验证。
- `R-FLUSH`、`R-READY-PRUNED`、`R-A-CONST`、`R-DATA-X`、`R-ADDR47`、
  `R-SRC-OUT-OF-RANGE`、`R-COV-INIT`、`R-COV-TOOL`、`R-COV-TOGGLE` 为非阻塞边界。
- 其他配置若把 flush 接实，或改变 `nMmioEntry`/`MmioBusWidth`/PMA 上限/生成哈希，
  当前分类失效，必须重跑并单独标注。
