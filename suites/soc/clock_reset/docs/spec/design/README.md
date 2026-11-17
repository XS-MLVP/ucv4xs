# 设计规格

按模块维护职责、接口、时序、合法域与行为要求。

初始模块：[`clock_gate`](clock_gate.md)。新增模块由 `ucv info` 发现。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

门控时钟与复位同步原语；父模块负责具体复位树、使能连接和跨域集成。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `clock_gate` | `ClockGate` | `utility/src/main/scala/utility/ClockGate.scala:24` | `XSTop.core_with_l2.core.backend.inner_intRegion.intExuBlock.exuALU0_AluCsrFenceLink.ClockGate` | 骨架；待实现 |
| `reset_gen` | `ResetGen` | `utility/src/main/scala/utility/ResetGen.scala:28` | `XSTop.reset_sync_resetSync` | 骨架；待实现 |
| `async_reset_synchronizer_shift_reg_w1_d3_i0` | `AsyncResetSynchronizerShiftReg_w1_d3_i0` | `rocket-chip/src/main/scala/util/SynchronizerReg.scala:80` | `XSTop.nocMisc.syscnt.update_sync_chain` | 骨架；待实现 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。
