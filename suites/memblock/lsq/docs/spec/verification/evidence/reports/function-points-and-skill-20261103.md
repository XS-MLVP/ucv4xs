# LSQ 功能点补齐与 SKILL 细化（2026-11-03，接续上游核查）

## 1. 起因与本轮范围

上一轮审计指出 LSQ 的"缺的部分"：8 类事务只覆盖干净完成，共享 actor
（`mixed_owners.py`）把随机注入的总线错误按恒 0 期望吞掉，导致 2575 条用例从未提问
"响应带错误怎么办"。本轮按
[behavior-equivalence](../../../../../../../../skills/design/behavior-equivalence.md)、
[traceability-and-implementation](../../../../../../../../skills/design/traceability-and-implementation.md)、
[verification-completeness](../../../../../../../../skills/verification-completeness/SKILL.md) 补齐，并把
SKILL 本身按实证细化。

范围：LSQ、DefaultConfig、`public-a0c2a26cb`、seed 1。

## 2. 补齐的四项

### 2.1 指令来源映射（新文档）

[instruction-source-mapping.md](../../../design/contracts/instruction-source-mapping.md)：逐族给出
"本层 / 出域（谁承接） / 未证明"。关键结论：

| 指令族 | 结论 | 依据 |
|---|---|---|
| LD/W/LH/LB、SD/W/H/B | 本层 | `Dispatch.scala:733-740` 的 `needAlloc` |
| HLV/HSV | 本层仅"异常携带的 hyper 位" | `NewStoreUnit.scala:336`、`NewLoadUnit.scala:1583` |
| 向量 load/store | 本层（首次向量路由仍未证明） | `LduOpcodes`/`StuOpcodes` |
| CBO clean/flush/inval/zero | 本层，`cboType` 0/1/2/3 | `Opcode.scala:591-596`、`LSQCommon.scala:51-64` |
| AMO/LR/SC | **出域**：`enqLsqIO.req.valid := fire && !isAMOVec` | `Dispatch.scala:741` |
| Zicbop prefetch | **出域**：`isLoadVec` 显式排除 `isPrefetch` | `Dispatch.scala:675-676` |
| fence/fence.i | 出域，仅经 sbuffer flush 影响 | `MemBlock.scala:1178-1187` |

另记两条 **AMO 对 LSQ 的接口义务**（`stIsEmpty`、flush 互斥），归 `MemBlock` 组合域，
单 DUT 观测不到；上游 #6597 说明该交互整核可达。

### 2.2 kind × outcome 矩阵（新文档 + 可执行账本）

- [kind-outcome-matrix.md](../../../design/contracts/kind-outcome-matrix.md)：8 kind × 6 结果域 = 48 格，
  逐格 `pass`/`fail`/`gap`/`na`/`out-of-domain`。
- `suites/memblock/lsq/function_points.py`：同一矩阵的机读版本。
- `tests/meta/test_function_points.py`（6 项自检）：缺行、无证据的 pass/fail、
  没有"缺什么+怎么补"的 gap、指向不存在测试的 fail，都会让测试失败。

覆盖统计（自检脚本实际输出）：48 格中 **23 pass / 2 fail / 4 gap / 19 na / 0 out-of-domain**。
`na` 都有结构依据，例如 Store 无 replay、uncache 响应无 tag_error。

### 2.2b 三向对账：规格 / Scala / 生成端口（机制化）

来源职责：期望答案只从规格来；设计意图只从 Scala 读；能驱动/能观测的端口面只从
生成 DUT 读。三者不能互相替代，尤其不能"从实现找语义"。

新增 `tools/audit_scala_rtl_fields.py`：

- `--report`：按 class 体抽取 `io.*` 链，压平后与 `signals.json` 做形状级差集
  （去 lane 下标、折叠括号、剔除 Scala 集合成员与整体 bundle 赋值）。**只用于分诊。**
- `--strict`：校验 `manifest/critical-fields.json`——功能点依赖的字段必须声明
  `port`（必须存在）或 `absent`（必须不存在 + 理由）。

实测（`public-a0c2a26cb`，38 DUT）：

```
duts compared: 38   scala-only shapes: 377
其中含 debug/diff/topdown 62 项；待分诊 315 项；两个 DUT 为 0（age_replay、unalign_queue）
```

已抽查的类别：firtool 折叠常量/未用字段（`deq_module` 的 `io_toUncacheBuffer_resp_ready`、
`req_bits_cmd`）、叶子未消费的 IO（`uncache_entry_*` 每个 13 项）、Chisel 聚合成员
（`io_allocateReq`/`io_validCount`/`io_lqFull`）、命名重映射（`io_enq_canAccept` →
`lqCanAccept`/`sqCanAccept`）。**不声称 315 项都已判定。**

关键命中：`deq_module` 的 16 项里，`io_toUncacheBuffer_resp_bits_denied` 与 `_corrupt`
正是 `NewStoreQueue.scala:1087/1095` 要读的字段——它们不存在，因为生产者只驱动
`nderr`/`error`。也就是说，**这个缺陷本来可以在写用例之前就以"字段缺失"暴露**，
而不是等 2575 条用例随机跑到。这条已写入 `manifest` 的 `absent` 项，端口一旦出现就
强制重开判定。

### 2.3 修共享 actor 的同源期望（本轮真正的行为改动）

`mixed_owners.py` 原来：

```python
response = s["cache_resp"] or dict(denied=False, corrupt=False)
... exceptionVec_7: int(response["denied"]), exceptionVec_19: int(response["corrupt"])
```

问题：`cache_resp` 只对 CBO 路径存在；普通 MMIO Store 的真实总线响应
（`job["nderr"]` / `job["error"]`，随机 1/8 置位）被忽略，期望恒 0。

改为按真实来源取期望：

- `cbo`：读 DCache 响应的 `denied/corrupt`（这一路 RTL 真的驱动）；
- `cbo.zero`：无 DCache 请求，期望 0；
- `io_store`：读总线 job 的 `nderr`（访问故障）与 `error`（硬件错误）。

同时把"总线故障"与"actor 的 trap 流"分开记账：新增 `s["bus_fault"]`，而 `s["fault"]`
仍只表示 actor 已建模的 Cache 故障 trap 流。理由见 §2.3.2。

#### 2.3.1 修前/修后对照

| 运行 | 选择 | 计数 | PASS→FAIL | FAIL→PASS | 说明 |
|---|---|---:|---:|---:|---|
| `/tmp/opencode/lsq-mixedfix-full-20261103` | 877 节点 | 754/126 | 26 | 0 | **作废：运行期间新增 `function_points.py`/`tests/meta`，`source_after` ≠ `source`** |
| `/tmp/opencode/lsq-mixedfix-expect-only-20261103` | 100 节点 | 20/80 | 26 | 0 | **作废：运行期间修改 `mixed_owners.py`，`source_after` ≠ `source`** |
| `/tmp/opencode/lsq-mixedfix-v2-20261103` | 100 节点 | **39/61** | **7** | **0** | 有效：source 前后均为 `9f3555f9…` |
| `/tmp/opencode/lsq-mixedfix-v2b-20261103` | 36 节点（其余相关文件） | **36/0** | 0 | 0 | 有效：source 前后均为 `9f3555f9…` |

前两次运行除源码不稳定外还各含一个我自己引入的次生错误（保留教训，不隐藏）：

1. 首次修改把 `cbo.zero` 也断言 `cache_resp is not None`，而 zero 根本不发 DCache 请求
   → 19 条额外 FAIL。已改为 `cbo==3` 时单独判 `cache_resp is None and consumed`。
2. 首次修改把总线故障并进 `s["fault"]`，触发了 actor 的
   `external_trap_after_original_LSQ_completion` 重定向流，但该流只对 Cache 故障建模
   → 额外 FAIL。已拆分 `bus_fault`（见 GAP-IO-STORE-TRAP）。

两条都按"运行期间改源码的结果不能作证据"处理：即使改动前的数字看起来合理，也不引用。

基线对照（同一批 100 节点）：`public-a0c2a26cb` 权威结果是 46 PASS / 54 FAIL；
修后 39 PASS / 61 FAIL。54 条原有 FAIL 全部保持 FAIL，7 条新增 FAIL 全部指向同一根因。

#### 2.3.2 有效的 7 条 PASS→FAIL：全部是同一根因

| nodeid | 期望 | 实际 |
|---|---|---|
| `test_ldu_mixed.py::test_LDU_pipeline_...[28929]` | `exceptionVec_19=1` | 0 |
| `test_ldu_mixed.py::test_LDU_pipeline_...[28933]` | `exceptionVec_7=1` | 0 |
| `test_ldu_s3_mixed.py::...[28929]` / `[28933]` | 19 / 7 | 0 |
| `test_ldu_s4_mixed.py::...[28929]` / `[28933]` | 19 / 7 | 0 |
| `test_normal_mixed/test_original_seeds.py[28929]` | `exceptionVec_19=1` | 0 |

（`test_seeded_mixed.py` 的 8 个种子在基线里本来就是 FAIL，因此不在 PASS→FAIL 名单里；
它在修后仍为 FAIL，判定未变。）

即**同一份 8 类型随机域，只要把期望改成真实总线响应，就有 7 个种子暴露
"MMIO Store 总线故障在写回处恒 0"**。这与新增定向探针
`test_uncache_store_fault.py`（1 PASS 对照 + 2 FAIL）指向同一根因。
根因证据：生成的 `PhysicalStoreQueue` 端口只有 `io_toUncacheBuffer_resp_valid`，
没有 `resp_bits`；`DeqModule.sv:684-685` 的 `hasAccessFault/hasHardwareError`
只剩 DCache(CBO) 一路。

**合法控制未被误伤**：`FAIL→PASS = 0`；54 条基线 FAIL 全部仍是 FAIL（判定未变）；
所有 CBO clean/flush/inval 的故障用例照旧通过。

### 2.4 显式缺口条目

矩阵 §4 与 `function_points.CROSS_GAPS` 现登记 6 条，格式统一为
"位置 / 缺什么 / 影响 / 补法":

`GAP-6704`（首尾窗口）、`GAP-6688`（阈值 0 配置域）、`GAP-PSQ-CREDIT`（deq credit）、
`GAP-AMO-OBLIGATION`（AMO 排空）、`GAP-IO-STORE-TRAP`（io_store 故障的 trap 流）、
`GAP-SEG-VSTORE`（segmented store + AMO）。

## 3. SKILL 是否可以细化：结论与落地情况

可以，而且这次漏检正是"功能点没定义好"的直接后果。已落地的改动：

| 文件 | 改动 | 状态 |
|---|---|---|
| `skills/design/behavior-equivalence.md` | 步骤 2 增加"响应结果域"维度；步骤 3 要求错误同时出现在刺激侧和响应侧；步骤 4 要求类别×结果域矩阵逐格给状态；步骤 6 要求新类别/新结果域回填三件套；新增步骤 7"把分类做成可执行账本"；产出与验收各加矩阵要求；末尾加本轮反例 | 已落地 |
| `skills/design/traceability-and-implementation.md` | 步骤 4 增加"输入侧列值域与 producer 分支"；实现记录模板加 `response_domain`、`input_value_domains`；验收加"只改响应结果的对照与只改激励的对照同等必需" | 已落地 |
| `skills/verification-completeness/SKILL.md` | 新增"每轮迭代的强制检查"四项：来源映射、类别×结果域矩阵、未分类项清单、可执行门禁；附本轮反例 | 已落地 |
| `skills/ucv4xs-workflow/SKILL.md` | "修改验证语义"时同步更新来源映射与矩阵并跑矩阵自检，缺行按未完成处理 | 已落地 |
| `suites/memblock/lsq/function_points.py` + `tests/meta/test_function_points.py` | 矩阵的可执行版本与 6 项自检 | 已落地 |

仅建议、未落地：

1. 把"矩阵自检"提升为**全工程通用**的 `ucv` 公共检查（现在只有 LSQ 有；
   其它工程需要各自的 `function_points` 数据）。
2. 在 `ucv report` 里输出矩阵状态汇总，使"有 gap 就不能给硬件 PASS"成为机器门禁，
   而不是靠人读文档。
3. 对"出域"结论增加自动核对：登记承接模块后，检查该模块是否有对应的功能点行，
   防止把缺口推到别处就消失。
4. 给 `skills/design/behavior-equivalence.md` 的矩阵提供模板文件（列名、状态词表），
   减少各工程自定义格式。

## 4. 结论与剩余

- 补上了"指令 → DUT"的映射和"类别 × 结果域"矩阵，并把矩阵做成可执行门禁。
- 修了共享 actor 的同源期望，用同一批种子把 MMIO Store 故障漏检从"不可见"变成 7 条真实 FAIL；
  定向探针另有 2 条独立 FAIL。**没有用豁免、删除用例或放宽断言取得通过。**
- 两次自作修改引入的次生错误已保留记录并作废相应运行，最终以 v2/v2b 为准。
- 仍缺：`GAP-6704`、`GAP-6688`、`GAP-PSQ-CREDIT`、`GAP-AMO-OBLIGATION`、
  `GAP-IO-STORE-TRAP`、`GAP-SEG-VSTORE`；3 条 post-edge credit 残余仍是 FAIL。
- 结论边界：LSQ、DefaultConfig、`public-a0c2a26cb`、seed 1。

机器记录：[功能点补齐](../../../../../../../../docs/history/lsq-function-points-20261103.json)。
