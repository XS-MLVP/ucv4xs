# MainBTB（MBTB）DefaultConfig 迁移复核（进行中，2026-10-30）

> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


本文记录整芯片 DefaultConfig RTL 下 `MainBtb` 单 DUT 的迁移适配与当前判定。模块闭环尚未完成：
39 个原生 FAIL 仍需逐项归因，覆盖缺口集中在写缓冲/VictimBTB，不能写成通过。

## 整芯片端口裁剪与适配

| 实际端口 | 处理 |
|---|---|
| `s3_takenMask` | 整芯片只保留父模块消费的槽 4、9；按叶绑定 |
| `meta_entries` | 预测侧每 bank 5 个槽（4 way + victim）完整保留 |
| `train.meta_mbtb_entries` | 训练侧每 bank 只有 4 个 MainBTB way；Victim 属性/counter 叶被裁 |
| `train.meta_mbtb_entries.N.M.attribute` | 训练元数据只保留 `rawHit`/`position`（外层 4 way 才有属性叶） |
| `trainReady` | Scala 常量，按常量绑定 |
| `stageCtrl` | s0..s3 与 t0 均保留 |

`suites/frontend/bpu/mbtb/bundle/ports.py` 用 `bind_leaf` 绑定稀疏 `s3_takenMask`，用 `bind_sequence` 绑定根级
`result`/`meta_entries`/`branches`，用嵌套序列绑定 `train.meta_mbtb_entries`。

## 语义适配修正

1. **训练元数据 4 way**：`expected_mbtb_feedback`、checker、各场景的 `planned_payload` 只比较可训练 4 way；
   Victim 侧带是预测输出，不是训练输入。
2. **空闲槽属性缺失**：checker 对没有 `attribute` 叶的槽只比较 `rawHit/position`（训练侧），
   预测侧 5 个槽仍完整。
3. **物理坐标**：MainBTB `AddrField` 从半字地址起：16 字节对齐偏移 3 位、align bank 1 位
   （PC[4]）、internal bank 2 位（PC[6:5]）、set 8 位（PC[14:7]）、tag 16 位（PC[30:15]）。
   旧模型使用的 `(pc>>5)&63`/`(pc>>11)` 等 MinimalConfig 几何已替换。
4. **默认 4 way LRU**：替换器初始顺序 `(0,1,2,3)`，首个 victim 是 way 3；不再假定首个分配写 way 0。
   场景里的 owner/way 断言改为从独立 LRU 或公共预测读出，而不是硬编码 0/1。
5. **根级结果形状**：`result` 为 10 槽，每个 5 元组；编码器按 10 槽发送，不再假定 4 槽。

## 当前运行结果

```sh
.venv/bin/ucv run bpu --workers 12 --output results/ut-mbtb-probe6-20261030 -- tests/mbtb
```

- 原生 MBTB：**86 PASS / 39 FAIL / 0 ERROR**（迁移初期 48 FAIL + 35 ERROR）。
- 纯模型分区：**全部通过**（此前按旧 33 折/旧几何的负对照已迁移）。

## 尚未闭环的 FAIL 分组

| 组 | 数量 | 现状 |
|---|---:|---|
| `test_cleanup_overlap` | 12 | 多命中清理与训练共享同一服务栈；模型仍按旧两 way owner 身份检查，需按 4 way 重写预期 |
| `test_entry_keys` / `test_depth_owner` | 12 + 2 | 物理坐标已改为真实 `AddrField`；剩余失败在写回偏移与 shadow owner 读取，需逐条复核 |
| `test_full_capacity_learning` | 4 | 满 set 驱逐顺序与写缓冲回写时序的模型仍按旧几何 |
| `test_semantic_reference` | 3 | 重复 clear 的 owner/zero payload 身份与 foreign-tag 方向 |
| `test_shadow` / `test_shadow_depth` | 2 | shadow depth/owner 与 4 way LRU 的组合 |
| `test_shared_service` | 4 | 共享服务 owner 身份 |
| 其他 | 2 | 见 `cases/bpu-mbtb/cases.json` |

这些 FAIL 均为真实判定，未删除、未加 XFAIL。上述分组的第一条已给出归因方向，但不能作为完成证据。

## 覆盖率（`results/ut-mbtb-final/rtl-line-coverage.json`）

| 指标 | 结果 |
|---|---|
| RTL 源行 | **3664/12114 = 30.25%** |
| `v_branch` 分支臂 | **1594/2654 = 60.06%** |
| `v_toggle` 位方向 | **21260/54410 = 39.07%** |

覆盖率低是因为大量场景在准备阶段即失败，深层写缓冲/VictimBTB 路径没有执行；这不是“已覆盖但无缺口”。
未覆盖行集中在 `WriteBuffer_4`（7690 行）、`VictimBtb`（420）、`ReplacerState_4`（218），
归类为“整体功能点尚未执行到”而不是“情况枚举缺失”。

## 结论边界

- MBTB 迁移适配已完成（0 setup ERROR），功能判定尚未闭环；39 FAIL 必须保留并逐项归因。
- 覆盖率不能用于宣称 MBTB 通过；需要先修复场景与模型，再重跑覆盖。
