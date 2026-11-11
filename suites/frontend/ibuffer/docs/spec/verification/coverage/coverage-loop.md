# 覆盖率闭环

## 口径

`tools/coverage_report.py` 从 `ucv run` 的 `manifest.json` 读取：

- **line**：优先使用 LCOV `DA` 行计数；没有 LCOV 时退回原生 `v_line` 点的
  `l`/`S` 行号。只统计真实 RTL 文件。
- **branch**：原生 `v_branch` 臂，保留生成 RTL 文本。
- **toggle**：原生 `v_toggle` 转移 bin，并另报"曾变化信号位"数。
- **排除** Picker 生成包装 `*_top.sv` 的 DA/行点：这些是 DPI/端口胶水，不是设计
  逻辑。没有 line/branch 点的真实文件明确标为 N/A，不按 100% 计入分子。

`ibuffer` 顶层闭包包含 `IBuffer.sv`、`VTypeGen.sv`、`VSetFuncUnit.sv`；顶层 DUT 的
覆盖是三者之和。`vtype_gen` 叶 DUT 的闭包是 `VTypeGen.sv` + `VSetFuncUnit.sv`。
Picker 把顶层 RTL 复制为 `<Top>Dut.v`，所以报告中 `VTypeGenDut.v`/`IBufferDut.v`
分别对应两份真实顶层文件。

## 结果（seed 1 / seed 2）

`vtype_gen`：

| 文件 | line | branch | toggle bin | 曾变化位 |
|---|---|---|---|---|
| `VSetFuncUnit.sv` | 6/6 (100%) | 5/6 (83.33%) | 190/506 (37.55%) / 188/506 | 95/253 / 94/253 |
| `VTypeGenDut.v` (VTypeGen.sv) | 157/157 (100%) | 99/100 (99.00%) | 1036/1090 (95.05%) | 518/545 |
| **DUT 合计** | **163/163 (100%)** | **104/106 (98.11%)** | **1226/1596 (76.82%) / 1224/1596** | **613/798 / 612/798** |

`ibuffer`：

| 文件 | line | branch | toggle bin | 曾变化位 |
|---|---|---|---|---|
| `IBufferDut.v` (IBuffer.sv) | 4014/4046 (99.21%) | 562/620 (90.65%) / 563/620 | 17333/18656 (92.91%) | 8708/9328 |
| `VTypeGen.sv` | 157/157 (100%) | 99/100 (99.00%) | 1020/1090 (93.58%) | 510/545 |
| `VSetFuncUnit.sv` | 6/6 (100%) | 5/6 (83.33%) | 171/506 (33.79%) | 86/253 |
| **DUT 合计** | **4177/4209 (99.24%)** | **666/726 (91.74%) / 667/726** | **18524/20252 (91.47%) / 18522/20252** | **9304/10126 / 9301/10126** |

说明：seed 之间的差异只来自随机激励（一个异常 mux 分支、少量 toggle bin），
两个 seed 的 nodeid、判定和功能点结论一致。

## 未覆盖行

`IBufferDut.v` 32 行（`IBuffer.sv` 的 `outputEntries_*` 寄存器）：

```text
outputEntries_{0..7}_bits_vtype_vsew/vlmul <= 3'h0;
outputEntries_{0..7}_bits_specvtype_vsew/vlmul <= 3'h0;
```

这些赋值来自 `IBufOutEntry.toIBufOutEntry` 对 `vtype/specvtype` 的 `DontCare`：
输出项无效或不在更新路径时，vtype 字段没有架构含义，firtool 选择 0 作为任意值。
它们不是可检查的功能行为，checker 也只在 `valid=1` 时比较 payload。归因为
**工具边界（don't-care lowering）**，没有为了数字去驱动无效项的 payload。

`vtype_gen` 未覆盖行 **0**。

## 未覆盖分支

`ibuffer` DUT（seed 1，60 个臂；seed 2 59 个）分类：

| 归因 | 数量 | 证据 | 处置 |
|---|---:|---|---|
| `VSetFuncUnit` 的 `readVl` 分支 | 1 | VTypeGen 把 `in_readVl.valid` 固定为 0 | 结构不可达 |
| `ENABLE_INITIAL_REG_` 的 `if (reset)` else | 2 | `initial` 只在 time 0 执行且仿真置 reset=1 | `R-COV-INIT` |
| `exceptionMask` 优先级 bit4..33 | 30 | IFU 的 mask 是 `OH(alignShift)`，shift 仅 0..3 | 合法 IFU 域外，`R-EXC-SINGLE` |
| 旁路异常槽 1..7 | 7 | 异常 mask 位于旁路槽 0（beat 首 lane） | 合法 IFU 域外 |
| 指针预回绕 lane 0..3 | 4 | `baseAligned+0..3 <= 47`，只有 lane>=4 会减 48 | 指针算术不变量 |
| 无效项的 vtype 清零分支 | 15 | 同未覆盖行的 `DontCare` 降级 | 工具边界 |
| 一个异常 mux 分支 | 1（仅 seed 1） | seed 2 命中；随机数据相关 | 随机深度，不是结构缺失 |

`vtype_gen` DUT（2 个臂）：`VSetFuncUnit` 的 `readVl`（结构不可达）和初始化块
reset-else（`R-COV-INIT`）。

## 未覆盖 toggle

| 类别 | seed 1 位数 | 证据 |
|---|---:|---|
| VSetFuncUnit 被父模块固定的输入 | 155（叶）/160（顶层） | `readVl/vlFromGp/vlFromVl/oldVType/vill/vsetvlVType` 的 valid 固定 0，bits 为 DontCare |
| IFU padding lane 32..35 | 188 | `FetchBlockInstNum=32`，32..35 不参与有效载荷 |
| `exceptionMask` bit4..35 | 32 | 同 OH(alignShift) |
| 输入端口 payload | 159 | 少数 lane/字段组合在本次随机深度未双向跳变 |
| 内部数据/状态 | 283 | 数据相关位（例如未使用的 FTQ/offset 组合），非结构缺失 |

这些不是缺少功能场景：已加入全 48 槽、全 0/全 1 payload 和逐位置异常用例，剩余
位由合法激励域、常量输入或随机深度解释。没有用非法激励追求数字。

## 闭环过程

1. 首版定向 + 随机后：`vtype_gen` line 100% / branch 98.11%；`ibuffer` line
   99.24% / branch 88.29% / toggle 80.74%。
2. 新增 `test_bypass_caps_at_eight_and_queues_the_remainder`（旁路 8 条上限）和
   `test_queued_exception_attaches_at_each_dequeue_offset`（异常在出队组 1..7 位置）
   后，branch 升到 91.46%。
3. 新增 `test_full_width_payload_reaches_every_queue_position`（随机 32 位 payload
   覆盖全部 48 槽和回绕槽）与
   `test_all_ones_and_all_zeros_payload_toggle_every_queue_bit`（全 1/全 0 双向跳变）
   后，toggle 升到 **91.47%**，branch **91.74%**。
4. 重新运行 seed 1、seed 2 完整集合，均为 83 PASS；nodeid、collection SHA 和
   功能点判定一致。
5. 未覆盖项全部归因；没有删除用例、放宽断言或修改 RTL。

## 证据位置

完整逐点表与 HTML 在忽略目录：

- `results/ibuffer-seed1-final5/coverage.json`、`coverage.md`
- `results/ibuffer-seed2-final5/coverage.json`、`coverage.md`
- 运行 manifest：`results/ibuffer-seed{1,2}-final5/ibuffer/manifest.json`

可入库摘要见 [覆盖率摘要](coverage-summary.md)。
