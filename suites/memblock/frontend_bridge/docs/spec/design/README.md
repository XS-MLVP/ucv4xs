# FrontendBridge设计规格

MemBlock 内 FrontendBridge 及 ICacheBuffer、ICacheCtrlBuffer、InstrUncacheBuffer；当前为待实现骨架。

- [icache_ctrl_buffer](icache_ctrl_buffer.md)
- [icache_buffer](icache_buffer.md)
- [instr_uncache_buffer](instr_uncache_buffer.md)
- [frontend_bridge](frontend_bridge.md)

## 当前硬件绑定观察

2026-11-16 观察：`public-e716c7658 / DefaultConfig`，单核、CHI E.b、OpenLLC，
含 `--fpga-platform --reset-gen`。源码位置来自锁定源码及完整生成注解，
实例为实际 RTL 样本；全部直接父实例见 workspace。数字后缀不是跨基线稳定身份。

| DUT | 配方 top | Chisel 定义/生成位置 | RTL 实例样本 |
|---|---|---|---|
| `icache_ctrl_buffer` | `ICacheCtrlBuffer` | `src/main/scala/xiangshan/mem/MemBlock.scala:310` | `XSTop.core_with_l2.core.memBlock.inner_frontendBridge.icachectrl` |
| `icache_buffer` | `ICacheBuffer` | `src/main/scala/xiangshan/mem/MemBlock.scala:298` | `XSTop.core_with_l2.core.memBlock.inner_frontendBridge.icache` |
| `instr_uncache_buffer` | `InstrUncacheBuffer` | `src/main/scala/xiangshan/mem/MemBlock.scala:277` | `XSTop.core_with_l2.core.memBlock.inner_frontendBridge.instr_uncache` |
| `frontend_bridge` | `FrontendBridge` | `src/main/scala/xiangshan/mem/MemBlock.scala:323` | `XSTop.core_with_l2.core.memBlock.inner_frontendBridge` |

这些观察不证明端口兼容、独立预期成立或硬件通过；当前工作与验收范围见
[验证合同](../verification/README.md)。历史报告按原基线解释。
