# MicroRAS（URAS）DefaultConfig 迁移复核与覆盖率闭环（2026-10-29）

本文记录整芯片 DefaultConfig RTL 下 MicroRas 单 DUT 的复核结果。功能点沿用 `BPU-URAS-001..017` 与原模块闭环
`docs/uras-module-closure-20261020.json`，不新增或放宽豁免。

## 迁移适配

1. **无 enable 引脚**：`MicroRas.scala` 完全没有引用 `BasePredictorIO.enable`，整芯片优化把该输入删除了。
   模块边界无法再驱动该引脚。适配层从写事务中剔除 `enable`，语义监视器按模块级 `enabled=True` 解码；
   父级 `rasEnable` 使用资格仍是 Bpu 顶层义务，对应已归档的 [BPU-BUG-05](bugs/BPU-BUG-05-microras-ignores-enable.md)。
2. **属性字段被展平**：`specIn.attribute` / `s2OverrideData.bits.attribute` 只剩 `attribute_rasAction` 叶，
   绑定改为展平叶名。
3. **常量状态端口**：`sramResetDone` / `trainReady` 在 Scala 中恒为 `true.B`，整芯片构建删除了引脚；
   适配层按声明常量绑定，复位后仍检查其值。
4. **复位边界对齐**：`isCanUse` 在异步复位时清零，而语义输入事件滞后一个边界。此前跨多次 `reset()` 的场景
   会在复位断言拍把 DUT 的 0 与模型上一拍的主栈地址比较，产生两个迁移后新增假失败。监视器现在把
   `dut.reset` 与输出一起采样，复位引脚为高的拍不参与比较；复位事件仍按原节奏推进独立模型。

## 运行结果

```sh
.venv/bin/ucv run bpu --workers 2 --output results/ut-uras-gap3-20261029 -- tests/uras
```

- 原生 URAS：**29 PASS / 4 FAIL**；同次纯模型分区：137 PASS。
- 4 个 FAIL 均为已归档的真实 RTL 问题，不是本轮适配引入：
  - `test_disabled_micro_ras_withholds_the_armed_return_target` → BPU-BUG-05；
  - `test_return_and_call_replaces_top_instead_of_becoming_neutral[speculation|pending-correction|retiring-correction]` → BPU-BUG-10。
- 迁移后曾新增的 `test_neutral_override...`、`test_s1_action_against_pending_s2_operation` 与功能覆盖门禁
  已恢复通过（复位边界对齐修复）。

## 覆盖缺口与补充

运行目录：`results/ut-uras-gap3-20261029/bpu-uras/`。设计源 `UrasDut.v` 与 `rtl/uras/MicroRas.sv`
除模块名外逐字节一致（8934 字节），`UrasDut_top.sv` 是 picker 引脚 shim，不计入设计行覆盖率。

| 指标 | 结果 |
|---|---|
| 行覆盖 | **73/73 = 100.0%** |
| 分支臂 | **30/31 = 96.8%** |
| toggle 位（双向都出现） | **439/440 = 99.8%** |
| toggle 迁移记录（每个方向计一次） | **1436/1440 = 99.7%** |

未覆盖项与归类：

| 项 | 归类与依据 |
|---|---|
| `MicroRas.sv:225` 的 `if (reset)` else 臂 | 初始化块；DUT 在时间 0 即断言复位，else 不可达。 |
| `io_fullRetAddr_addr[0]` / 地址 bit0 | GuardedPc 半字地址 bit0 恒为 0，由地址域约定决定。 |

### 补充的语义用例

- `test_full_width_address_bits_reach_the_public_target`（BPU-URAS-007）：交替驱动 0、全高位模式与
  块内偏移，覆盖主 RAS 直通、S1 call、S2/S3 修正以及 **S2→S3 的 `s2_fire` 推进存储路径**，确认 50 位
  地址没有截断或串位。
- `BOUNDARIES` 增加位置 16、31：DefaultConfig 取指行为 64 字节，`cfiPosition` 是 5 位 0..31，
  原 4 位边界会漏掉位置 bit4。

这些用例把 toggle 双向完整位从 76/421（18.1%）提升到 439/440（99.8%），并补上了 S3 返回地址寄存器
只在 `s2_fire` 时装载的情况枚举。

## 结论边界

- 本轮证明 MicroRas 模块级地址、栈合成、修正、复位与存储语义；不证明 Bpu 顶层 CSR 路由。
- `BPU-URAS-016/017` 保持真实 FAIL，未删除、未登记 XFAIL。
- 覆盖率结论基于当前整芯片生成 RTL 与 Picker mem-direct 构建；源或工具变更后需重建重跑。
