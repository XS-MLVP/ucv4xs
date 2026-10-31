# ITTAGE（5 表间接目标预测器）DefaultConfig 迁移复核与覆盖率闭环（2026-10-30）

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


本文记录整芯片 DefaultConfig RTL 下 `Ittage` 单 DUT 的迁移适配、功能判定与覆盖率证据。
功能点沿用 `BPU-ITTAGE-001..0xx`；真实 FAIL 保持原样。

## 整芯片端口裁剪与适配

| 实际端口 | 处理 |
|---|---|
| `s1_foldedPhr_hist` / `trainFoldedPhr_hist` | 只保留 9 个被 5 张表 index/tag 哈希消费的 fold（0/3/4/8/9/11/12/19/20），按 picker 元数据逐叶绑定 |
| `meta.valid` | 父模块未消费，整芯片删除；适配层用 `enable && s3_fire` 作为发布资格 |
| `trainReady` | Scala 恒 `true.B`，按常量绑定 |
| `meta` / `train.meta_ittage` | provider/alternate/allocate/target 字段完整保留 |
| `prediction` | 只有 `hit` + `target_addr` |

`suites/frontend/bpu/ittage/bundle/ports.py` 用 `bind_leaf` 绑定稀疏历史；`monitor/semantic.py` 把稀疏行放回 33 折上下文。
`driver/encoding.py` 不再驱动被裁的 `position` 叶；训练从公共 branch 向量解码 kind/action。

## 语义适配修正

1. **默认 LFSR 分配表**：DefaultConfig 的首分配表由 15 位 LFSR 选择，不再固定 table 0。
   用例改为先扫描确定行，再选择“首个可分配表低于最长表”的真实上下文；不再假定旧二维几何。
2. **metadata 发布资格**：整芯片没有 `meta.valid`；`enable && s3_fire` 是父模块消费该 payload 的资格。
3. **sparse fold**：编码、监视器、checker 使用同一 `history_indices`；`Context.from_recent` 仍然按配置折叠。
4. **复位边界**：复位拍输出不参与比较。

## 运行结果

```sh
.venv/bin/ucv run bpu --workers 10 --output results/ut-ittage-final-20261030 -- tests/ittage
```

运行结果以该目录 `cases/bpu-ittage/cases.json` 为准。迁移后已修复：
`test_unconfident_primary_training_keeps_alternate_target`、
`test_unconfident_provider_falls_back_to_alternate`、功能覆盖门禁的默认分配表选择。
保持的 FAIL 是迁移前即存在的 RTL/模型边界：
- `test_late_feedback_for_an_unpublished_original_does_not_create_a_target`；
- `test_zero_confidence_retarget_preserves_full_region_without_new_table[existing-region]`；
- `test_zero_confidence_retarget_preserves_full_region_without_new_table[new-region]`。

这 3 条与迁移前判定逐条一致，未新增 XFAIL、未删除用例。前一条暴露“未发布原始快照的迟到反馈”没有被 RTL 拒绝；
后两条的 region 目录重定向与独立模型不一致（RTL 选择已存在 region pointer，而模型按新 region 解释）。
后续需要单独判定是 RTL 缺陷还是模型对 region 目录共享语义的建模缺口。

## 覆盖率（`results/ut-ittage-final/rtl-line-coverage.json`）

| 指标 | 结果 |
|---|---|
| RTL 源行 | **2126/2190 = 97.08%**（设计行 100%，缺口全在 BIST wrapper） |
| `v_branch` 分支臂 | **1218/1670 = 72.93%**（383 个未覆盖臂在 `MbistPipeIttage`） |
| `v_toggle` 位方向 | **18955/212758 = 8.91%**（179k 位在 BIST/DFT 与内部大 SRAM 数据域） |

未覆盖归类：

| 项 | 归类与依据 |
|---|---|
| `MbistPipeIttage*` 行/分支 | **扫描/DFT 域**：MBIST pipe 未在功能 UT 中启用；不属于算法功能缺失 |
| `IttageTable`/`Ittage` 内部 toggle | **数据模式覆盖缺口**：5 张表的 tag/target 高位数据模式未遍历；功能臂已覆盖 |
| BIST `boreChildrenBd` toggle | 扫描端口未活动，不可作为功能判定 |

## 结论边界

- 本轮完成整芯片端口适配并消除迁移引入的全部 setup ERROR 与几何假设失败；原生 3 条失败与迁移前一致。
- 覆盖率结论只适用于当前生成 RTL 与 Picker mem-direct 构建。
