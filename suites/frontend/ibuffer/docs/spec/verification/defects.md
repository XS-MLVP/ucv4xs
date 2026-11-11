# 缺陷与设计边界记录

## 本轮确认的 RTL 缺陷

**无。** seed 1/seed 2 的完整集合均为 83 PASS；没有把任何未解释的失败改写成
XFAIL、SKIP 或 UNCERTAIN，也没有删除反例。

## 设计边界观察（不登记为本层缺陷）

### 1. VSETVL 编码与 VSETVLI 重叠

`VTypeGen` 只按 `{bit31, funct3, opcode} == 11'h3D7` 识别 vsetvli。VSETVL 的
编码（`funct7=0`）是 VSETVLI 的子模式，因此该模块会把 VSETVL 当作 vsetvli，用
`rs2` 字段生成一个推测配置。VSETVL 提交时 `hasVsetvl` 冲刷流水线，推测被丢弃。

- 证据：`VTypeGen.scala` 只有 `isVsetvli/isVsetivli`；`IBuffer.scala` 的
  `enqHasVSet` 显式包含 VSETVL，说明队列侧知道它；本工程
  `test_vsetvl_encoding_overlaps_vsetvli_at_this_boundary` 固定这一接口事实。
- 归类：`R-VSETVL-OVERLAP`（out-of-domain，非阻塞）。若主解码器改变 VSETVL 的
  冲刷合同，需要重新审查该丢弃路径。

### 2. keep-vl 保留情形的 vill payload

`rd=rs1=x0` 且新 SEW/LMUL 改变 VLMAX 时，ISA 将该用法定义为 reserved，实现
"可以置 vill"。设计置 `illegal=1`，但保留请求的 vma/vta/vsew/vlmul。RISC-V 的
CSR 描述同时要求 vill=1 时其余位为 0；本设计把该值作为内部推测快照，
`Backend.scala:542` 才把它转成 CSR 值。

- 证据：`VTypeGen.scala` 的 `correctedVtype(i).illegal := true.B` 只改 illegal；
  `testbenches/vtype_gen/tests/test_vtype_gen.py::test_keep_vl_changed_vlmax_sets_vill` 固定该
  接口行为。
- 归类：`R-VILL-PAYLOAD`（observation-limitation，非阻塞）。CSR 零化是否必须发生
  属于 Backend/CSR 边界，本层不把它写成 RTL 缺陷；若 CSR 验收要求全零，应在
  Backend 层新增检查。

### 3. 单异常和 IFU padding

`FetchToIBuffer` 只有一个异常组，IBuffer 只保存第一个异常；`exceptionMask` 是
`OH(alignShift)`（bit0..3）。因此旁路异常槽 1..7、`exceptionMask` 高位和
lane 32..35 的有效载荷不是合法 IFU 激励，相关覆盖缺口按 `R-EXC-SINGLE`/
`R-LANE-PAD` 归因，而不是功能场景缺失。

### 4. 性能计数器

`io_perf_*` 由 `QueuePerf/XSPerfAccumulate` 驱动，本工程绑定并运行，但不把
累加值作为架构期望（`R-OBS-PERF`）。这不是缺陷。

## 开发过程中的模型修正（不改变 DUT 判定）

以下问题在模型/测试实现阶段被发现并修正，均有对照证据，最终 DUT 判定为 PASS：

- `outputEntriesValidNum` 的 `PriorityMuxDefault` 配对是 `(valid_i, i+1)`，
  不是 `(valid_i, i)`；修正后追加模式与 RTL 一致。
- keep-vl 的 VLMAX 参考使用请求 payload 的解码值（即使保留位使该 lane 非法），
  且寄存器参考解码已存 SEW/LMUL 字段而不看 vill；修正后随机回归通过。
- `flush` 同时清除 `firstException.valid`；修正后异常不会在 flush 后重放。
- stall reason 的全空窗口为 0、窗口非空且无 reason 为 13、有 reason 时为最高
  索引；修正后 directed 与随机均一致。
- 后端 vtype 输入必须使用受支持的 SEW/LMUL 编码；保留编码不是合法架构输入，
  由 `Inputs` 拒绝。
