# SC（统计相关分支预测器）DefaultConfig 迁移复核与覆盖率闭环（2026-10-30）

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


本文记录整芯片 DefaultConfig RTL 下 `Sc` 单 DUT 的迁移适配、功能判定与覆盖率证据。
功能点沿用 `BPU-SC-001..0xx`；不新增豁免、不删除失败。

## 整芯片端口裁剪与适配

| 实际端口 | 处理 |
|---|---|
| `foldedPathHist_hist` / `trainFoldedPathHist_hist` | 只保留 SC 两段 path/global 折叠索引 3、10；编码器按索引投影 |
| `mbtbResult` / `providerTakenCtrs` | 根级数组，逐元素绑定；仅 `bits.attribute_branchType`、`cfiPosition`、`valid`、`bits_value` |
| `train.meta.mbtb_entries` | 每 bank 只有 `rawHit`、`position`（属性和 counter 被裁）；branch kind 由 branch 向量提供 |
| `meta.debug` | 预测侧 10 槽 debug 向量完整保留 |
| `scTakenMask` / `scUsed` | 10 槽根级数组，按叶绑定 |

`suites/frontend/bpu/sc/bundle/ports.py` 使用 `bind_leaf`/`bind_sequence`/`nested_sequence` 绑定稀疏历史与根级数组；
`monitor/semantic.py` 与模型共享 `history_indices`，把训练元数据中的 branch kind 从真实 branch 向量解码，
从旧的重复 attribute 副本迁移出来。

## 语义适配修正

1. **训练 MainBTB 元数据只有 rawHit/position**：模型/checker 的 `expected_feedback` 不再比较被裁的
   `attribute`/`counter_value`；branch kind 由 branch 向量承载。
2. **Victim slot 训练元数据被裁**：模型反馈源固定为每 bank 4 个可训练 way。
3. **`IMMEDIATE` 预测槽宽**：`takens`/`useds` 为 10 槽（`RESULT_SLOTS`），绑定和纯模型测试同步放宽。
4. **enable 语义**：`Sc` 的 `io_enable` 是模块级门控；驱动/监视器按真实引脚驱动和采样。

## 运行结果

```sh
.venv/bin/ucv run bpu --workers 10 --output results/ut-sc-final-20261030 -- tests/sc
```

- 原生 SC：**61 PASS / 0 FAIL**；纯模型分区 **403 PASS**。
- 迁移初期 29 个原生 FAIL 已全部消除（训练元数据侧带裁剪、槽宽、稀疏历史、纯模型夹具）。

## 覆盖率（`results/ut-sc-final/rtl-line-coverage.json`）

| 指标 | 结果 |
|---|---|
| RTL 源行 | **4556/5245 = 86.86%** |
| `v_branch` 分支臂 | **1878/2256 = 83.24%** |
| `v_toggle` 位方向 | **29135/41226 = 70.67%** |

未覆盖项归类：

| 项 | 数量 | 归类与依据 |
|---|---:|---|
| 全局计数器饱和臂（`Sc`） | 27 行 / 350 臂 | **已有功能点缺失情况枚举**：`global` 表项 `+31/-32` 双向饱和边界未同时遍历；现有用例只覆盖部分方向 |
| 写缓冲合并/满队列（`WriteBuffer_68`、`WriteBuffer_54`） | 658 行 / 20 臂 | **已有功能点缺失情况枚举**：多 way `wayMask` 合并、同拍双写与满队列强制写回未构造 |
| 初始化复位 else 臂 | 2 行 | 结构不可达 |
| BIST/SRAM/DFT toggle | 约 9000 位 | 扫描/DFT 域，不改变功能判定 |

## 结论边界

- 本轮证明 SC 在整芯片实际端口下的历史/门控、选择、阈值、反馈与更新语义，原生用例全部通过。
- 剩余覆盖缺口属于已定义功能点的边界情况枚举（全局计数器饱和、写缓冲合并/满队列），
  需要下一轮补用例，不以现有通过替代。
