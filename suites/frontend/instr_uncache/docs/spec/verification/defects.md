# 缺陷判定

本轮**未确认新的 InstrUncache RTL 缺陷**。真实 FAIL/ERROR 为 0；不把结构出域或
覆盖边界登记成缺陷，也不为了绿灯扩大 XFAIL。

## 判定标准

一个现象只有在以下条件同时满足时才登记为 RTL 缺陷：

1. 激励属于该接口/配置的合法域（地址对齐、`denied => corrupt`、单 outstanding 等）；
2. 期望来自规格/ISA/TileLink 合同，而不是从 RTL 赋值反推；
3. 失败可在同源码、同种子下复现，并有合法的正确对照；
4. 失败不是被生成的 pruned 端口、consumer 常量或工具边界造成的观察缺失。

## 本轮非缺陷项

| 现象 | 为什么不是缺陷 |
|---|---|
| flush 不可驱动 | `Frontend.scala:266` 明确恒接 `false.B`；生成闭包合法裁剪。登记 `R-FLUSH`（out-of-domain），不作为 RTL 缺陷。 |
| 响应/D/grant ready 无端口 | 消费者分别固定为 1（`IfuUncacheUnit.scala:133`、`InstrUncacheImp.scala:88`）；无合法反压场景，登记 `R-READY-PRUNED`。 |
| A opcode/size/source/mask 不可观测 | `edge.Get(fromSource=io.id, lgSize=3)` 与 8B 对齐使它们为常量，生成器裁剪；登记 `R-A-CONST`。 |
| A 地址 bit47 固定 0 | Scala `Cat` 宽度与 DefaultConfig PMA 上限共同决定；合法地址域 < 2^43，登记 `R-ADDR47`。 |
| 初始化块 reset else 未覆盖 | `ENABLE_INITIAL_REG_` 初始化块只在 time 0 执行且总带 reset=1；结构不可达（`R-COV-INIT`）。 |

## R-FLUSH 分类复核（2026-11-08）

结论：**不是 RTL 缺陷，是 DefaultConfig 的域外结构事实。**

- `Frontend.scala:266` 把 `instrUncache.io.flush` 固定为 `false.B`；全仓库唯一实例
  在 `Frontend.scala:125`，`FrontendInlinedImp` 无条件执行该连接。
- `SimFrontendInlinedImp`（`EnableSimFrontend=false` 才不启用）也把整个
  `instrUncache.io` 接 `WireDefault(0.U...)`（`SimFrontend.scala:195`），同样不会
  产生高电平 flush。
- `InstrUncacheEntry.scala:41,58-63,100,162` 的 `flush`/`needFlush` 路径因输入恒 0
  被 firtool 完全裁剪；生成的 `InstrUncache.sv`、`InstrUncacheEntry.sv` 都没有相关
  端口/寄存器，`Frontend.sv` 的 `inner_instrUncache` 实例也没有 flush 连接。
- 证据与哈希：[`docs/spec/verification/evidence/flush-closure.json`](evidence/flush-closure.json)；
  `tools/audit_flush_closure.py` 逐次复核，证据变化时返回非零。

因此把 `R-FLUSH` 在本单元登记为 **out-of-domain / accepted-limited**，
`INC-FLUSH-012` 改为环境分区的结构检查点。这里没有“修复”，也没有把结构不可达
写成行为验证；flush 期间/迟响应的取消语义仍未证明。

**用户确认保守口径（2026-11-08）**：新增 `FRONTEND-FLUSH-CONNECT`
（blocking/open，owner `frontend/design`）跟踪 `false.B` 这个设计决定本身；在
设计 owner 签字或补上真实连接/删除端口之前，整体 `hardware_verdict` 保持
**INCOMPLETE**。`R-FLUSH` 的 accepted-limited 只表示“单元内无法再验”，不代表
Frontend 连接正确。

## 触发新缺陷时的动作

在 `docs/bugs/open/<name>.md` 新增或更新稳定编号的问题记录，写明复现命令/种子、失败
nodeid、RTL 哈希、最小激励、合法对照、根因文件/行、影响范围和建议修复。根因未定时
明确标记调查状态；配置、观察和集成边界留在所属规格。工程根旧计划已删除，不另增
残余 JSON。修复后保留原 FAIL 的复现记录与前后差分，再按证据更新问题状态。
