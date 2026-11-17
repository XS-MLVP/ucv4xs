# Frontend 集成验证设计规格

真实 Frontend 顶层闭包的连接、取消/背压、WFI 等集成合同；当前为待实现骨架。

- [frontend](frontend.md)

## 当前硬件绑定观察

2026-11-16 观察：`public-e716c7658 / DefaultConfig`，单核、CHI E.b、OpenLLC，
含 `--fpga-platform --reset-gen`。源码位置来自锁定源码及完整生成注解，
实例为实际 RTL 样本；全部直接父实例见 workspace。数字后缀不是跨基线稳定身份。

| DUT | 配方 top | Chisel 定义/生成位置 | RTL 实例样本 |
|---|---|---|---|
| `frontend` | `Frontend` | `src/main/scala/xiangshan/frontend/Frontend.scala:106` | `XSTop.core_with_l2.core.frontend` |

这些观察不证明端口兼容、独立预期成立或硬件通过；当前工作与验收范围见
[验证合同](../verification/README.md)。历史报告按原基线解释。
