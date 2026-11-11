# MainBTB（MBTB）DefaultConfig 迁移复核（进行中，2026-10-30）

> **历史材料边界（整理注）**：本页保留原日期、基线、验证源码和选择范围；端口/位宽事实可追溯，但 PASS/FAIL/覆盖数字不自动适用于当前 `public-a0c2a26cb`。当前条款入口见 [design/mbtb.md](../../../design/mbtb.md)。


> 路径迁移说明（2026-10-31）：本报告仍属于原日期、基线和执行源码；实现文件已迁到工程根。可点击源码链接更新到当前位置，不据此重标历史 PASS/FAIL 或覆盖结论。参见[本轮命名空间迁移](../../../../../../../../docs/lessons/suite-namespace-refactor-20261031.md)。


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

## 当前整芯片 BPU 观察边界（2026-11-01复核）

`Bpu.sv` 的 DefaultConfig 整芯片导出中，`io.toFtq.prediction.bits`只保留
`startPc/taken/endPosition/s2Override/s3Override`，`target_addr`由下游未消费而被DCE；
`toFtq.meta`也不含旧适配器依赖的`perfMeta`。这不是把目标默认为0，也不是重新生成一个
带target的BPU专用入口。当前`BpuPorts`显式报告`prediction_target_observable=False`、
`meta_perf_observable=False`，事务仍检查真实可见字段、ready/valid、输入接受和时序；
请求target过滤、S3 target修复及依赖perf echo的操作在该组合DUT上明确拒绝并记为观察域
限制。组件级ITTAGE/ABTB/UBTB等仍在各自真实闭包中独立比较target，不能把组件证据借给
整芯片Bpu。

新增`tests/framework/test_integrated_observation_boundary.py`覆盖正常可见域与错误查询
控制；BPU绑定不再因缺少已DCE字段 setup ERROR。整芯片BPU的target-sensitive功能点
仍不能因此签核；其 DefaultConfig 纯模型/真实回归以及旧维度场景继续保留原FAIL或
待归因，不通过改名、补零或XFAIL隐藏。

后续自检纠正了初版边界实现：不存在的metadata ready不能用可写`InputConstantLeaf`
和虚构`IsInIO()`伪装成物理输入。现在只读常量仅用于SDK协议适配，不进入control driver
payload/引脚所有权；采样字段按已审计schema严格检查，不能把漏字段自动解释成新的DCE。
无retirement-PC观察的`redirect_and_settle`在驱动前拒绝，不先发redirect再报告能力缺失。

## 2026-11-02 事务/DefaultConfig继续审计（尚未完成）

上文“迁移适配已完成（0 setup ERROR）”仅是当时端口绑定范围；**不能**据此签核语义
事务迁移。当前`tests/mbtb`完整基线已实际核验为2257 PASS/229 FAIL（native101 PASS/
24 FAIL、pure2156 PASS/205 FAIL），source69771d1...稳定并在修改前逐文件匹配；不能
将39条历史FAIL直接冒称当前结果。FTQ等模块的绿色也不替代MainBTB本身。

两条新的独立纯控制`results/ucv-goal-mbtb-four-way-cleanup-red-20261102.xml`均FAIL，
直接证明当前`model/cleanup.py`的剩余迁移缺口：

1. `expected_mbtb_cleanup_dual`仍只生成两个way的ports/before/after，实际DefaultConfig
   为4 way、每way4个retained slot；原两way预期不可能完整核验当前shadow所有权。
2. `observed_mbtb_cleanup_dual`要求该bank**全部way**的write_valid同时为1，导致实际
   只有两路有效、另两路idle的cleanup/correction同拍事件被整个漏掉。应完整保留4路
   观察并按真实有效子集判断，不能把4-way硬件截成2-way来迎合旧预期。

这些是Python模型/观察归一化反证，不是RTL缺陷或原生场景通过。完整修复还须核验：
DefaultConfig四路LRU计划、retained深度4下如何通过正常训练回收旧shadow而仍保留SRAM
原件、重复项keep/clear与邻居真实输入owner、同拍共享service和完整写回时序。
`env/shared_service.py`及其checker还存在旧`tag<<11`/`row>>5&63`与固定0/1 owner，
不能只改常量或用DUT live返回的way临时拼expected；必须从已声明输入前史建立独立
分配/保留owner，再用完整字段和合法/错误控制核验。当前仍为必需未完成项。

随后cleanup首段修复使用reset独立LRU分别规划两行的original/displacer=way3、
changed/extra=way2及keep2/clear3，不从返回way临时拼expected。所有4路及每路4个
retained slot都比较；失活写payload不伪造0，外国bank写也保留。有效tag0输入改以
半字PC `1<<31`为tag周期基址，旧`0x40000000+(tag<<15)`实际令“zero-tag”变成32768；
原12种dirty/clean、depth0/1、zero-tag/zero-position组合与全部断言保留，输入坐标修正
不冒称物理激励字节未变。合法later-neighbor位置范围按16半字align扩到0..14。

第一轮`ucv-goal-mbtb-cleanup-four-way-v1-20261102`为21 PASS/12 FAIL，已通过完整双路
写/shadow检查，剩余差异是旧clear模型仍保留无效entry的attribute=3；实际明确all-zero
clear写也清attribute，现补独立零值断言，而非删除比较。第二轮`...cleanup-models-v2...`
为544 PASS/12 FAIL：三个纯适配组（旧cleanup签名、entry-key align重复旋转、depth错误
消息及四way控制）均通过，所有native副作用/独立reference也通过，最后失败仅为覆盖
收据仍要求`len(ports)==2`。现要求完整4路且恰2路有效并补“双方同错2-way/第三路写”
负控制；完整MBTB新回归尚待核验，不签核整个模块。

Retained深度4不意味着必须4个串行displacer：一次写已服务成为clean后，下一次miss
优先复用首个clean rank。探查中“串行4个才回收旧shadow”的假设被2条纯FAIL否定，
不是模型或RTL缺陷；按`WriteBuffer`明确选择规则分开clean重用和4-dirty容量的3条
纯控制通过。不得用增加无关准备流掩盖真实owner/同时服务义务。

## 2026-11-02 后续已核验检查点

完整cleanup v3现已结束为**2539 PASS/12 FAIL**（native113/12、pure2426），原2486项
无删除，217 FAIL→PASS、新65项全部selftest PASS；12个cleanup原生场景均通过。
source0525f9...前后稳定并在后续修改前逐文件匹配，125原生输入、3个覆盖产物、6个构建
文件和processor哈希核验，原生未重建。上述“尚待核验”是先前时点，不重写历史结果。

shared-service按输入LRU、4bank/4way/4slot和真实tag0/1迁移，两个current对照PASS；两个
old-miss场景实际同拍两个完整请求却只服务clear，丢纠正的普通FAIL保留。depth的stale
nomination改为输入计划1而非旧0，外层cleanup收据keep2/clear3；负条件、第二深度方向
及联合零键保留真正反例，不从返回way临时拼答案。

19条纯red证实类型/宽度/schema及嵌套快照边界不严格，1条native red证实正文吞错后close
假成功。现补固定ABI、递归只读metadata、50-bit guarded lookup与49-bit resolve分域、
有界finish及pytest报告控制的checked-close；对应red修后PASS。旧纯夹具的局部/两路/
虚构Victim属性改为完整实际schema，保留全部区分性错误控制。

seed2定向2599 PASS/5 FAIL，后续seed1定向88 PASS/5 FAIL；后者增加真实训练高guard
target消费者，不把两次运行说成完全同源码。根242 PASS，结构/Skill/diff通过，严格全仓
事务门禁仍exit1。完整MainBTB新回归、逐UID/训练来源与其余生命周期仍必需，不能关闭
模块或整体目标。见[当前合同](../../contracts/mbtb-transaction-contract.md)与
[机器证据](../../../../../../../../docs/history/transaction-goal-mbtb-transactions-20261102.json)。
