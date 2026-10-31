# AheadBTB（ABTB）DefaultConfig 迁移复核与覆盖率闭环（2026-10-30）

本轮把 AheadBTB 从"无法绑定"推进到可复核的语义闭环：整芯片实际端口适配、参考模型与 sideband 裁剪、
复位边界修正、以及针对 toggle 缺口的补例。功能点沿用 `BPU-ABTB-001..054` 与
`docs/abtb-module-closure-20261021.json`，未新增豁免。

## 整芯片端口适配

`AheadBtb.scala` 的 `BasePredictorIO`/`HasAheadPredictorIO` 在整芯片优化后出现以下裁剪：

| 端口 | 处理 |
|---|---|
| `io.prediction.valid`（MicroBTB 是独立输出，ABTB 没有） | 不绑定 |
| `io.stageCtrl.s3_fire` | 未被消费，删除绑定与驱动 |
| `io.normalPathHist_hist` | 只保留 history index 2；用声明元数据路径单独绑定，序列不连续时不能整体 `bind_tree` |
| `io.result_entries` | 根级数组；按元素绑定（`bind_sequence`） |
| `io.trainReady` | Scala 恒 `true.B`，按常量绑定 |
| `fastTrain.branch.mispredict` | 未消费，删除编码/监视 |
| `toMicroTage.result.bits.cfiPosition/isStrongBias/rasAction` | 整芯片只向 MicroTage 提供 `taken` 与 `branchType`；这些叶在公共 sideband 上不存在，仍由条目、meta 与 counter 状态检查覆盖 |
| `io.redirect` | 不再用 `dut.io_redirect` 别名，按声明树绑定 |

## 修复的真实问题

1. **SPARSE PHR 绑定**：`normalPathHist_hist` 只有索引 2，`Bundle.bind_tree` 因序列不连续拒绝绑定。
   新增 `bind_leaf`/`bind_sequence`（按声明元数据校验宽度），不修改生成物。
2. **复位边界**：输出寄存器在异步复位时清零，而语义输入事件滞后一拍；此前会把复位后的清空与上一拍
   预测比较，导致 83 个 setup 之后的假失败。现在把 `dut.reset` 与输出一起采样，复位拍不参与比较；
   写缓冲/计数器检查在复位拍改为与全新参考状态比较。
3. **sideband 裁剪**：`strong/position/action` 在整芯片中不再输出给 MicroTage。删除了对这些不存在叶的
   读取，并把方向仍可观测的字段（`taken`、`branchType`）保留在比较中；state counter/writebuffer/priority
   检查继续逐 cell 比较 1024 个方向计数器与完整条目 payload。
4. **复位清空写缓冲检查**：`CapacityChecker` 在采样到复位时用新参考状态校验 slot/PLRU/计数器全清，
   而不是拿复位前影子状态比较。

## 运行结果

```sh
.venv/bin/ucv run bpu --workers 2 --output results/ut-abtb-gap3-20261030 -- tests/abtb
```

- 原生 ABTB：**93 PASS / 1 FAIL**；同次纯模型分区：**1896 PASS / 7 SKIP**。
- 唯一 FAIL 是已归档的 `BPU-BUG-09`：`test_pending_target_corrections_preserve_destination_ownership[distinct-destinations]`
  （AheadBTB 对同 set 两条间接分支的目标修正选错目的 way），迁移前即存在，原样保留。

## 覆盖率

设计源 `AbtbDut.v` 与 `rtl/abtb/AheadBtb.sv` 的对应关系与子模块一致（生成闭包）。覆盖数据：
`results/ut-abtb-gap3-20261030/bpu-abtb/native/8c8b8c3e.../coverage.{dat,info}`。

| 文件 | 行 | 分支臂 |
|---|---|---|
| `AbtbDut.v` | **11621/11621 (100%)** | 4138/4139 |
| `AheadBtbReplacer.sv` | 1094/1094 | 451/516 |
| `ReplacerState.sv` | 389/389 | 131/132 |
| `WriteBuffer.sv` | 175/175 | 43/44 |
| `SRAMTemplate_36.sv` | 28/28 | 15/18 |
| `array_64x112.sv` | 9/9 | 5/6 |
| `PlruStateGen*.sv` | 4/4 | 8/8, 2/2 |

toggle 完整双向位 **7601/9261（82.1%）**；计入设计（排除 picker shim 与 MBIST/门控常开引脚）后，
未覆盖集中在写缓冲条目存储与训练/重放 payload 的高位。

### 缺口归类与补例

- **已补：完整宽度条目身份**（`tests/abtb/testcase/test_full_width_state.py`）
  - 全 50 位 PC/目标经 S2 重放与训练管道回到公共记录；
  - 四个写缓冲 slot 用互补 24-bit tag / 22-bit target 模式反复写、读、复位，验证不截断、不串槽；
  - 多命中清理覆盖 set 0 与 set 63，观察 `multiHitSetIdx` 的全 6 位。
- **剩余 toggle 缺口**：
  - 写缓冲 4 slot × 24-bit tag / 22-bit target 的完整组合（61+40 位）：需要填充所有 slot 的每个高位并
    反复覆写；本轮已让每个 slot 都写入互补高位，但 SRA M 写端口在 4 拍内只接受部分 payload，
    其余位仍缺反向。归为"已有功能点（写缓冲全宽身份）的缺失情况枚举"，下一轮继续补例。
  - `t1_train_*`/`s2_state_*` 高位（16+7+7）：训练与重放已覆盖极端地址；剩余位来自只在特定 phase
    才写的高位组合，属训练 payload 的情况枚举。
  - `AheadBtbReplacer.sv` 的 65 个未覆盖分支臂：模块闭环文档已给出局部守卫证明（PLRU 链尾与
    WriteBuffer 三元 else 在其自身 false 分支内），本轮未新增功能点。

## 结论边界

- 本轮只证明 AheadBTB 模块级语义与端口适配；不证明 Bpu 顶层组合。
- `BPU-ABTB-053`（写缓冲按键合并会覆盖另一 way 的待决修正）仍是模块闭环中已记录的开放差异，
  对应唯一 FAIL。
- 覆盖结论基于当前整芯片生成 RTL 与 Picker mem-direct 构建；源或工具变更后需重建重跑。
