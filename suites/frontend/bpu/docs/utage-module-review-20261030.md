# MicroTAGE（UTAGE）DefaultConfig 迁移复核与覆盖率闭环（2026-10-30）

本文记录整芯片 DefaultConfig RTL 下 MicroTage 单 DUT 的迁移适配、语义闭环与覆盖证据。
功能点沿用 `BPU-UTAGE-001..028`；真实 FAIL/XFAIL 原样保留，未删除、未放宽。

## 整芯片端口裁剪与适配

| 实际端口 | 处理 |
|---|---|
| `normalPathHist_hist` | 只保留索引 2、7（两张表的索引折叠） |
| `s1PathHist_hist` / `overridePathHist_hist` / 训练历史 | 只保留 1、2、5、6（tag/alternate 折叠） |
| `fastTrain.bits.branch` | 只有 `taken`/`cfiPosition`/`attribute_branchType`；无 `mispredict`、`ras_action` |
| `fastTrain.bits.utageMeta.foldedPathHistForTrain_hist` | 稀疏 4 行（1、2、5、6） |
| `io.meta_valid` | 父模块未消费，整芯片删除；语义上等于“任一 public hit” |
| `fromAheadBtb.result.bits` | 只有 `taken`/`attribute_branchType`；位置由独立 `fastPositions` 提供 |
| `io.prediction.takenVec/hitVec` | 4 槽完整 |
| `io.trainReady` | Scala 恒 `true.B`，按常量绑定 |

## 语义适配修正

1. **稀疏 PHR**：编码器、监视器、checker 按实际保留的 fold 索引构造/投影；33 折上下文在模型内部保持完整，
   公共比较只针对可观测索引。
2. **训练元数据稠密重建**：训练观察端口把稀疏行放回 33 折；模型 `training_folds` 同时接受稠密与 4 行紧凑域。
3. **复位边界**：`dut.reset` 断言拍不参与输出比较；`capture_input` 在复位引脚为高的同一拍清模型状态，
   使模型清零与 DUT 在复位沿的清零对齐（此前跨 reset 场景出现 low 计数 3/0 假失败）。
4. **`Context.from_recent` 合法域**：仅使用自身低 `length` 位折叠（≤397），接受 532 位循环历史存储域。
5. **被裁 metadata 的负对照**：纯模型负对照翻转 `TRAIN_HISTORY_INDICES` 中的真实 fold，
   不再翻转被 DCE 删除的 fold 0。
6. **`cfiPosition` 5 位**：DefaultConfig 位置 0..31，边界用例已迁出 4 位域。
7. **低 tick 老化语义**：`lowTickCounter` 的 bit7 同时驱动有用数组 aging；模型按 128 次失败分配触发。

## 运行结果

```sh
.venv/bin/ucv run bpu --workers 12 --output results/ut-utage-final-20261030 -- tests/utage
```

- 原生 UTAGE：**234 PASS / 35 FAIL / 1 XFAIL**（迁移前基线：232 PASS / 35 FAIL / 3 XFAIL）。
- 35 个 FAIL 与迁移前 FAIL 集合**逐条一致**（`cases` 对比 new=0、fixed=0）；2 个 strict XFAIL 因真实修复转为 PASS：
  `test_useful_update_full_required_address_matrix`（utage-007 标签在 DefaultConfig 读路径上不再阻断）
  与 `test_utage_guarded_pc_tag_width`；`test_saturated_rows_survive_full_shadow_replacement...` 仍是 strict XFAIL。
- 35 个 FAIL 的根因仍是已归档的真实缺陷/边界：
  - 16 条 `test_two_warm_providers...`：共享执行前缀的双源学习计数差异；
  - 8 条 `test_multiple_incoming_edges...` + 3 条 `test_original_learning_survives...` 等保留/退休版本计数差异；
  - 其余为 confidence、working-set、read ownership 与 resolved-nonconditional 的已存在差异。
  这些均与迁移前一致，未新增 XFAIL、未删除用例。

## 覆盖率（`results/ut-utage-final2/rtl-line-coverage.json`，270 个用例覆盖文件）

| 指标 | 结果 |
|---|---|
| RTL 源行 | **11279/11286 = 99.94%** |
| `v_branch` 分支臂 | **3725/3734 = 99.76%** |
| `v_toggle` 位方向 | **8758/11384 = 76.93%** |

### 本轮新增功能点：BPU-UTAGE-028（整表 useful aging）

首轮覆盖显示 `BypassShadowBuffer` 的 498 个 aging 三元表达式行未覆盖（500 行中只有 2 个三元表达式被执行）。
逐项归因后判定为**整体功能点缺失**：已有功能点只验证了“单个 lower/upper useful 计数器在 aging 后保持或下降”，
没有构造“整表每个非零 useful 单元都在同一 aging 拍各减一”的语义。

新增 `test_every_useful_cell_is_aged_by_one_global_sweep`：
- 通过真实预测/反馈把表 0 全部 512 个索引建立为 useful=1；
- 在最高表制造 126 次失败分配，跨越 bit7；
- 验证 aging 拍覆盖全部 4 bank × 128 set 的 512 个非零单元，且条目仍命中。

复跑后 `BypassShadowBuffer.sv` 的 aging 行 **512/512 覆盖**，模块总行覆盖从 95.53% 提升到 99.94%。
剩余 7 行均为各模块初始化复位 else 臂或 SRAM 初始化，不可在时间 0 后到达。

未覆盖归类：

| 项 | 归类与依据 |
|---|---|
| 7 个初始化复位 else 行 | 结构不可达（时间 0 即复位） |
| `SRAMTemplate_44` 3 个分支臂 | MBIST/SRAM 复位握手在功能 UT 中未活动 |
| 9 个分支臂 | 上述结构不可达臂 |
| 2626 个 toggle 位方向 | 1590 位为 BIST `boreChildrenBd`；其余为 SRAM 广播/内部数据模式（`MicroTage` 1345 位、两个 table 各约 436 位），属数据值覆盖而非功能臂缺失 |

## 结论边界

- UTAGE 在整芯片实际端口下完成“定义语义功能点—用例—覆盖—缺口—补点—复跑”闭环，行覆盖 99.94%。
- 35 个真实 FAIL 与既有 XFAIL 保留；它们不是迁移引入，也不以覆盖提升改写为通过。
