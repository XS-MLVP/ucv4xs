# 设计规格

按模块维护职责、接口、时序、合法域与行为要求。

初始模块：[`syscnt`](syscnt.md)。新增模块由 `ucv info` 发现。
## 当前切分与 Chisel / RTL 映射

本表是 **2026-11-16** 的设计身份核对，基线 `public-e716c7658`，完整 commit `e716c765824900ff78816b92ac827fd4aa2cab35`。配置为 DefaultConfig、单核、CHI E.b、OpenLLC，含 `--fpga-platform --reset-gen`。

Chisel 位置来自该次 FIRRTL 源位置注解，并与源码核对；RTL 实例来自生成模块中的实际实例声明。表中实例为可定位样本，全部直接父实例见 workspace.json。数字后缀只属于该基线，不是稳定逻辑身份；同一个 RTL 类型可能有多个实例。

TIMER、SYSCNT 与 TimeAsync 的计时、寄存器访问及跨域传递。

| DUT | 当前配方 top | Chisel 定义/生成位置（相对源码根） | RTL 实例样本 | 接入状态 |
|---|---|---|---|---|
| `syscnt` | `SYSCNT` | `src/main/scala/device/SYSCNT.scala:72` | `XSTop.nocMisc.syscnt` | 骨架；待实现 |
| `timer` | `TIMER` | `src/main/scala/device/TIMER.scala:78` | `XSTop.nocMisc.timer` | 骨架；待实现 |
| `time_async` | `TimeAsync` | `src/main/scala/device/TimeAsync.scala:29` | `XSTop.nocMisc.syscnt.timeasync` | 骨架；待实现 |

这些映射不证明接口向后兼容、硬件等价或功能覆盖；历史规格和报告沿用原日期及基线。构建、冒烟、功能、覆盖分别验收。公共 NewPipelineConnectPipe 与 internal VAGQ 同名模块没有互相覆盖结论。
