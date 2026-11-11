# IBuffer / VTypeGen 设计规格

状态：合同已按 ISA、Scala 接口意图和生成端口整理；**未取得设计 owner 正式签核**。
详细正文直接采用迁移后的[合同](contracts.md)，本页只给出层次、配置和验证边界。

## 范围与层次

```text
IBuffer（Frontend 中的取指缓冲队列）
└── VTypeGen（唯一的真实子模块实例）
    └── VSetFuncUnit
```

| 层 | DUT | RTL top | 角色 |
|---|---|---|---|
| 叶 | `vtype_gen` | `VTypeGen` | 8 个 decode lane 的 vtype 生成、spec/arch 双状态、walk/commit 输入 |
| 顶层 | `ibuffer` | `IBuffer` | 48 槽队列、36-lane IFU 入队、8 lane 输出窗口、旁路、flush、前端异常 |

顶层 DUT 是真实 `IBuffer`，闭包包含 `IBuffer.sv`、`VTypeGen.sv`、`VSetFuncUnit.sv`；
`testbenches/ibuffer/tests/framework/test_binding_contract.py` 从构建收据核对真实子模块存在。参考模型只
提供期望值。`VTypeBuffer`/`VtypeModule` 由 `Rob/NewCSR` 实例化，不在本闭包。

## 配置

DefaultConfig：`VLEN=128`、`ELEN=64`、`IBuffer Size=48`、`NumWriteBank=4`、
`NumReadBank=8`、`EnqueueWidth=36`、`DecodeWidth=8`。IFU fetch block 为 64 B / 32 个
指令槽；36 lane 中只有 0..31 可能有效，32..35 是写 bank 对齐 padding。

## 接口与行为合同

- **vtype 编码与 VLMAX**：按 RISC-V V 1.0 支持表；保留编码、超 ELEN 组合置 `vill`。
- **vsetvli/vsetivli**：`vtypei` 位置、保留位、`rd=rs1=x0` 的 keep-vl 保留情形按
  合同；window 内 vset 按 lane 链接，`specvtype` 是每条指令执行前的快照。
- **VTypeGen 状态机**：同沿优先级为 `commitVType.hasVsetvl` > `commitVType.vtype.valid`
  > `walkVType.valid` > `walkToArchVType` > `canUpdateVType`；复位 spec/arch 为
  `vill=1`、零配置。
- **IBuffer 队列**：入队 beat 最多 32 条有效指令，写 bank 预对齐；`allowEnq` 使用
  上一周期声明的 `prevInstrCount`，严格小于剩余空间时保守拒绝。
- **输出窗口与旁路**：8 项头部连续；替换/追加模式按 `decodeCanAccept` 选择；队列空、
  非 `resumingVType` 且 beat 不含 vset 时允许最多 8 条旁路。
- **flush 与异常**：flush 清队列、窗口、指针和已存异常；每个 beat 只有一组前端异常，
  `exceptionMask=OH(alignShift)`，只附加到匹配的队列指针。

完整条款和合法输入域见[合同](contracts.md)；功能点 ID 与检查器映射见
[功能点](functional-points.md)。

## 设计边界与未确认项

- `VTypeGen` 只按 vsetvli 编码识别 vsetvli，VSETVL 编码是其子模式；VSETVL 提交时由
  流水线冲刷丢弃推测，登记为 `R-VSETVL-OVERLAP`（out-of-domain）。
- keep-vl 保留情形只置 `illegal=1` 并保留 payload；CSR 零化属于 Backend/CSR 边界，
  登记为 `R-VILL-PAYLOAD`（observation-limitation）。
- 单异常组和 IFU padding lane 32..35 不是合法激励；见 `R-EXC-SINGLE`、`R-LANE-PAD`。
- 本层不证明 Frontend redirect/FTQ/ICache 交互、真实 CSR vtype 写入、其他配置或芯片
  验收。
