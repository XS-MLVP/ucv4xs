# TAGE（8 表 512 行 2 way）DefaultConfig 迁移复核与覆盖率闭环（2026-10-30）

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


本文记录整芯片 DefaultConfig RTL 下 `Tage` 单 DUT 的迁移适配、功能判定与覆盖率证据。
功能点沿用 `BPU-TAGE-001..034`；本轮不新增豁免、不删除失败，真实 XFAIL 原样保留。

## 整芯片端口裁剪与适配

| 实际端口 | 处理 |
|---|---|
| `fromPhr.foldedPathHist_hist` | 仅保留 20 个被 8 张表 index/primary/secondary 哈希消费的 fold，按 picker 元数据逐叶绑定并做宽度校验 |
| `fromPhr.foldedPathHistForTrain_hist` | 同样 20 折稀疏；编码器按 `training_history_indices` 投影 |
| `fromMainBtb.result.N.bits` | 整芯片只保留 `valid` + `bits_taken`；位置由 `s1_positions` 提供，kind 来自训练元数据 |
| `fromMainBtb.baseConf` | 10 位完整保留 |
| `stageCtrl` | 只有 `s0_fire`/`s1_fire`/`t0_fire`；S2/S3 由 S1 token 与基础结果驱动阶段代替 |
| `train.meta.mbtb_entries` | 每 bank 4 个 MainBTB way（Victim slot 的元数据被裁），训练编码按 4 way 投影 |
| `train.meta.tage_entries` | 10 个预测槽完整保留 |
| `prediction.fastTakenVec` / `toSc_providerTakenCtrVec` | 10 槽完整 |

`suites/frontend/bpu/tage/bundle/ports.py` 新增稀疏 fold 绑定与根级数组绑定；`monitor/semantic.py` 把稀疏行放回 33 折以重建上下文，
并用 `VISIBLE_HISTORY_INDICES` 把 DCE 删除的 fold 在两侧置零，避免把不可观测输入当作比较目标。

## 语义适配修正

1. **预测上下文只比较可观测 fold**：`Context.from_recent` 现在只计算被 TAGE 哈希消费的 20 折；
   模型与监视器使用同一 `VISIBLE_HISTORY_INDICES` 投影。纯模型负对照仍会翻转被消费 fold。
2. **MainBTB 结果不含位置/属性**：位置属于 S1 输入 `s1_positions`，属性属于训练侧 branch 向量；
   预测比较只覆盖 valid/direction/confidence，位置在请求关联与模型侧单独检查。
3. **复位边界**：复位引脚为高的输出拍不参与比较（与其他模块一致）。
4. **写缓冲/队列**：`t0_fire` 是训练脉冲；`s1_fire` 驱动读回应答、`t0_fire` 推进训练流水，
   驱动层用独立 S1/S2 token 防止连续 S2 fire 清理陈旧读。

## 运行结果

```sh
.venv/bin/ucv run bpu --workers 12 --output results/ut-tage-probe4-20261030 -- tests/tage
```

- 原生 TAGE：**247 PASS / 0 FAIL / 1 XFAIL**；纯模型分区 **867 PASS**。
- XFAIL 为既有 strict 用例
  `test_captured_feedback_after_way_migration_preserves_unrelated_tag_useful`，保持原判定。

## 覆盖率（`results/ut-tage-probe4/rtl-line-coverage.json`）

| 指标 | 结果 |
|---|---|
| RTL 源行 | **4978/5308 = 93.78%** |
| `v_branch` 分支臂 | **2841/3154 = 90.08%** |
| `v_toggle` 位方向 | **27837/66424 = 41.91%** |

未覆盖项归类：

| 项 | 数量 | 归类与依据 |
|---|---:|---|
| 多槽 alternate 选择 mux（`Tage`） | 145 行 / 240 臂 | **已有功能点缺失情况枚举**：只有槽 0 的 alternate 选择被驱动；测试没有构造“同拍 10 槽中多槽同时命中并提供 alternate”的情况 |
| 写缓冲同拍双写/合并（`WriteBuffer_12`） | 169 行 / 49 臂 | **已有功能点缺失情况枚举**：写缓冲的 `hitMask` 双 way 合并与满队列强制写回只在单写路径下运行，未构造同拍两路写 |
| 初始化复位 else 臂 | 各子模块 1 行 | 初始化块结构不可达（时间 0 即复位） |
| SRAM/BIST toggle | 29104 位 | BIST 端口未在功能 UT 中活动；属于扫描/DFT 域，不改变功能判定 |
| 内部数据 toggle | 3929 位 | 表项高位 target/tag/计数器数据模式未遍历；属数据值覆盖，不是功能缺失 |

本轮新增的纯模型/用例修正：`test_history_parity_is_independent_of_driver_chunk_fold` 与
`test_pipeline_context_cannot_be_reassociated_from_actual_payload` 适配稀疏 fold 域。

## 结论边界

- 本轮证明 TAGE 在整芯片实际端口下的查表、分配、更新、选择器、写回与服务语义，以及复位/禁用边界。
- 未覆盖的多槽 alternate 与同拍双写属于已定义功能点的**情况枚举缺口**，不是通过；下一轮应补对应用例。
- toggle 结论受 BIST 与数据模式影响，不能写成“功能未验证”。
