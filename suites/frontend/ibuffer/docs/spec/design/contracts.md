# IBuffer / VTypeGen 合同

本文件记录验证所依据的规格、接口意图和合法激励域。期望来自 RISC-V V 1.0 规范、
`VTypeGen`/`IBuffer` 的 Scala 接口意图和生成端口，不从生成 RTL 的赋值反推。

## 1. vtype 编码（RISC-V V 1.0）

`vtype` 为 `{vill, 0…, vma, vta, vsew[2:0], vlmul[2:0]}`。DefaultConfig 的
`VLEN=128`、`ELEN=64`：

| 编码 | 支持 | 说明 |
|---|---|---|
| `vsew=000/001/010/011` | e8/e16/e32/e64 | `vsew=100..111` 保留 |
| `vlmul=000/001/010/011` | m1/m2/m4/m8 | |
| `vlmul=101/110/111` | mf8/mf4/mf2 | |
| `vlmul=100` | 保留 | |
| 其他组合 | `sew > ELEN*min(LMUL,1)` 时不支持 | 例：e16/mf8、e64/mf2 |

`VLMAX = LMUL*VLEN/SEW`。支持表（模型 `decode_vtype` 与
`testbenches/vtype_gen/tests/test_vtype_gen.py::test_vlmax_matches_the_architectural_table`
的独立手写表一致）：

```text
e8:  m1 16  m2 32  m4 64  m8 128  mf4 4  mf2 8  mf8 2
e16: m1 8   m2 16  m4 32  m8 64   mf4 2  mf2 4
e32: m1 4   m2 8   m4 16  m8 32   mf2 2
e64: m1 2   m2 4   m4 8   m8 16
```

## 2. vsetvli / vsetivli 语义

- `vsetvli` 的 11 位 `vtypei` 位于 `inst[30:20]`，bit 31 必须为 0；`vsetivli` 的
  10 位 `vtypei` 位于 `inst[29:20]`。两者高位的保留位非零时必须置 `vill`。
- `vtypei` 低 8 位是 `{vma,vta,vsew,vlmul}`；保留或超出 ELEN 的 SEW/LMUL 必须置
  `vill` 并把配置字段清零。
- `vsetvli/vsetivli` 在 `rd=x0 && rs1=x0` 时保持 `vl`；若新 SEW/LMUL 使 VLMAX
  改变，该用法是规范保留的，实现可以置 `vill`。本设计选择置 `vill`。
- 一个 window 内多个 vset 按 lane 顺序链接：第 i 条以第 i-1 条的结果为参考；非
  vset lane 透传前一条的结果。
- `specvtype` 是每条指令执行前的快照：lane 0 为寄存器值，lane i 为 lane i-1 的
  `vtype`。

## 3. VTypeGen 状态机（接口合同）

- `vtypeSpec` = 当前推测配置；`vtypeArch` = 已提交的架构配置。
- 跳变优先级（同一沿）：
  1. `commitVType.hasVsetvl` → `vsetvlVType` 同时写入 spec 和 arch（vsetvl 冲刷流水线）；
  2. `commitVType.vtype.valid` → 只写 arch；
  3. `walkVType.valid` → 写 spec；
  4. `walkToArchVType` → 把**本沿之前**的 arch 复制到 spec；
  5. `canUpdateVType` → spec 取 window 最后一个 lane 的结果。
- 复位：spec/arch 均为 `vill=1, vma=vta=vsew=vlmul=0`。复位期间各 lane 的输出仍由
  当前输入组合决定（只有状态寄存器被复位），所以带 vset 的复位周期仍可观察到该
  vset 的配置；静默复位周期观察 INIT。
- `walkVType/vsetvlVType/commitVType` 是架构路径回灌值，必须使用受支持的 SEW/LMUL
  编码，或全零的 INIT 值；保留编码（如 `vlmul=100`）不是合法的架构 vtype。该域由
  `Inputs.__post_init__` 拒绝。

## 4. IBuffer 接口合同

- 48 槽循环队列；入队 beat 最多 32 条有效指令，写 bank 预对齐：
  `start = enqPtr % 4`，lane `start+n` 对应队列位置 `enqPtr+n`。
- 入队有效位 `valid ⊆ lanes 0..31`，`enqEnable ⊆ valid` 且为连续 run；`prevInstrCount`
  是本周期对**下一周期** `numFromFetch` 的声明。`allowEnq`（即 `io_in_ready`）在沿上
  更新为 `prevInstrCount < 48 - nextNumValid`；因此"恰好占满剩余空间"的声明会被
  保守拒绝（设计使用严格小于）。
- `empty = (enqPtr == deqPtr) && !outputEntries[0].valid`；`full = !allowEnq`。
- 输出窗口 8 项，头部连续。`decodeCanAccept` 时由 `numDeq = min(numValid, 8)` 个
  出队项替换；否则在窗口未满时追加 `numDeq = min(numValid, 8 - 当前有效数)` 项。
- 旁路条件：队列空、`decodeCanAccept`、非 `resumingVType`、beat 不含任何
  vsetivli/vsetvl/vsetvli。旁路最多前 8 条；其余仍写入 ibuf。旁路项取当前
  `vtypeSpec`，因为 vset 会改变推测配置，所以含 vset 的 beat 禁用旁路。
- 非旁路路径把即将进入窗口的指令送给真实 VTypeGen；`canUpdateVType =
  !resumingVType && (decodeCanAccept || !outputEntries[7].valid)`。追加模式下新项按
  窗口坐标编号，链从当前 spec 重新开始。
- `flush` 清空队列、输出窗口 valid、所有 enq/deq/bank 指针和已存异常，并恢复
  ready；flush 周期不写入入队数据。
- 前端异常：每个 beat 只有一组异常字段，`exceptionMask = OH(alignShift)`（即该 beat
  第一条指令的 lane）。IBuffer 只保存一个异常，附加到其队列指针匹配的指令；其余
  lane 不重复报告。`satpFlushFirstFetchFault = hasSatpFlush && hasException`。
- stall reason：每个浪费的输出 lane 报告最高有效 topdown reason；无 reason 且窗口
  非全空时为 FetchFragBubble(13)；窗口全空时为 0。redirect override 中未导出的
  `btbMissBubble/scMissBubble` 视为 0。
- `io_perf_*` 是性能计数器，本工程绑定并驱动，但不把其累加语义作为架构判定。

## 5. 端口裁剪与观察边界

| 缺失/常量 | 依据 | 处置 |
|---|---|---|
| lane 35 `predTaken` | IFU 对 36-lane padding 的 constant | 绑定层记录，驱动时跳过 |
| `btbMissBubble/scMissBubble` | 生成端口未导出 | stall reason 模型按 0 处理 |
| `pc/isLastInFtqEntry/debug_seqNum` | `IBufOutEntry.toCtrlFlow` 不导出 | 不比较（`R-OBS-PC`） |
| `io_perf_*` 累加语义 | 性能监视器，非架构合同 | 只绑定/驱动（`R-OBS-PERF`） |
| `VSetFuncUnit` 的 `readVl/vlFromGp/vlFromVl/oldVType` 等 | VTypeGen 将其 valid 固定为 0 | 分支/toggle 不可达 |

`VTypeBuffer`/`VtypeModule` 由 `Rob/NewCSR` 实例化，不属于 IBuffer 闭包；本工程不
包含它们，也不把 CSR vtype 写入当作本层结果。

## 6. 已知设计边界（非本层缺陷）

- **VSETVL 编码重叠**：`VTypeGen` 只识别立即数形式。VSETVL（funct7=0）的编码是
  VSETVLI 的子模式，因此该模块会按 rs2 字段生成一个推测配置；VSETVL 提交时
  `hasVsetvl` 冲刷流水线，该推测被丢弃。见 `R-VSETVL-OVERLAP`。
- **keep-vl 保留情形的 payload**：`rd=rs1=x0` 且 VLMAX 改变时，设计只把
  `illegal` 置 1，保留请求的 vma/vta/vsew/vlmul（该指令本身是规范保留情形）。
  本工程把 vill 下的 payload 视为接口 don't-care；架构 CSR 是否清零属于
  Backend/CSR 边界（`R-VILL-PAYLOAD`）。
- **单异常**：`FetchToIBuffer` 只有一个异常组，IBuffer 只保存第一个异常；同拍多
  lane 异常不是合法 IFU 激励（`R-EXC-SINGLE`）。
