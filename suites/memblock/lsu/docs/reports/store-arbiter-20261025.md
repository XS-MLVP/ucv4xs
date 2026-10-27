# `Arbiter3_StoreStageIO` UT 报告（2026-10-25）

## 1. 结论

| 项 | 值 |
|---|---|
| DUT | `Arbiter3_StoreStageIO`（S0 store 请求源仲裁） |
| 原生构建 | `results/builds/20261025T042333369715Z-store_arbiter`，`NATIVE_SMOKE_PASS` |
| 用例 | **22 passed / 0 failed**（`results/store-arbiter-initial-03`） |
| 功能覆盖 | **3 组 / 100%**，3876 个样本 |
| 行覆盖（DUT-only） | **32/32 = 100%**，过程语句未覆盖 0 |
| 分支覆盖 | **62/62 = 100%** |
| Toggle（DUT-only） | **1126/1128 = 99.82%**，2 点已归因为结构性不可达 |
| 状态 | **PASS**（唯一 toggle 缺口有源码证据，不计分母删除） |

## 2. 真实边界与合同

生成 RTL 与 Scala 意图有两处必须按实际端口描述的差异，已写入
[合同](../contracts/store-arbiter.md)：

1. 第三源（hardware prefetch）在生成的 `StoreUnitS0` 中整源消除：无
   `io_prefetchReq` 端口，`prefetchReq.valid` 被常量折叠为 0，`io_in_2_*`
   消失。它的常量载荷只保留为 bubble 输出
   （`entrance=0x2`、`instrType=4`、`size=4`、`mask=0xFFFF`）。
2. 第一源（unalign tail）没有 `ready`：S1 回注的尾段不能被反压。

这两点不是推断，有生成 RTL 的直接证据：模块只有 `io_in_0`/`io_in_1`，
`io_in_1_ready = ~io_in_0_valid`，`StoreUnitS0.sv` 中 `prefetch` 出现 0 次。

## 3. 功能点与用例映射

| 功能点 | 用例 |
|---|---|
| ARB3-IDLE | `test_idle_outputs_bubble_and_keeps_scalar_ready`（逐字段检查 bubble 常量） |
| ARB3-TAIL-ONLY | `test_unalign_tail_alone_propagates_every_field` |
| ARB3-SCALAR-ONLY | `test_scalar_alone_propagates_every_field`（含 `ssid`/`storeSetHit`） |
| ARB3-PRIORITY | `test_both_valid_selects_tail_and_blocks_scalar` |
| ARB3-NO-DROP | `test_tail_is_never_dropped_for_any_scalar_state[0/1]` |
| ARB3-VALID-GATED | `test_valid_gated_fields_follow_selected_source[4 shapes]` |
| ARB3-EXCV19 | `test_exception_vec_19_comes_only_from_tail` |
| ARB3-SELECT-ISOLATION | `test_non_selected_source_mutation_never_leaks`（4 个隔离情形 × 8 次随机翻转） |
| 合法随机 | `test_seeded_random_traffic_checks_every_beat`（600 拍） |
| 字段组 × 位型 | `test_every_group_is_seen_at_every_shape[3×2]` |
| walking-one | `test_walking_one_payload_still_matches_reference[2]`（首/次/中/末位） |

参考模型是**独立的两路优先级选择器 + 显式 bubble 常量表**，不复用 RTL 的
三元表达式；每个 beat 逐字段比较 22 个输出字段。

## 4. 覆盖闭环过程

| 轮次 | 结果 | 发现与处理 |
|---|---|---|
| `store-arbiter-initial-01` | 22 passed，功能覆盖 **88.72%** | 覆盖定义有缺陷：`valid_class × entrance`、`valid_class × scalar_ready` 两个 cross 里的 8 个 bin 逻辑上不可能（entrance 与 ready 是同一仲裁决定的函数）；另含 `entrance: unknown` 防御分支被当成必需 bin。 |
| 覆盖重设计 | — | 把「谁被选中 + 输出哪个 entrance + 标量是否被反压」合并为 4 个 `beat_kind` bin；删除 `unknown` bin；`shape` 由 4 类（含不可达的 `random`）收敛为 `zero/all_ones/mixed` 3 类。 |
| `store-arbiter-initial-02` | 11 failed / 11 passed | **测试代码缺陷，不是 RTL 失败**：`TAIL_GROUPS` 未导入；walking-one 生成器对多字段做了逐字段置位，得到 2 个 bit 而非 1 个，并且出现负移位。 |
| 修正后 `initial-03` | **22 passed**，功能 **100%**，行 **100%**，分支 **100%** | 见第 1 节。 |

`initial-01`/`initial-02` 的目录保留，不追溯改写；`initial-02` 的 11 个失败是
验证侧错误，已在报告中如实记录，不计为 RTL 缺陷。

## 5. 未覆盖点归因

唯一缺口是 `io_out_bits_entrance[2]` 的两个跳变（0→1、1→0）。归因为
**结构性不可达**：

- `Arbiter3_StoreStageIO.sv:69-70` 的 entrance 只可能来自三个常量
  `4'h1` / `4'h8` / `4'h2`；
- `package.scala:190-201` 中只有 `vectorIssue` 编为 `4'h4`（bit2=1）；
- 本模块没有任何输入能选择 `vectorIssue`，`StoreUnitS0` 在该仲裁点也没有
  向量发射源。

因此该点在本 DUT 的合法域内不可达，不补用例、不删分母。明细见
[gap 分类](gaps/store-arbiter.json)。

## 6. 可复核性

- DUT 构建：`results/builds/20261025T042333369715Z-store_arbiter/report.json`
  （含 picker 命令、`-c`、`-w memory-direct.fst`、无 VPI、`NATIVE_SMOKE_PASS`）。
- 覆盖率原始库：`results/store-arbiter-initial-03/native/*/coverage.dat`，
  SHA-256 见 `coverage-audit.json`。
- 运行策略：`trace-policy.json` 为 PASS（0 波形、0 逐周期 dump）。
- RTL 哈希：`manifest/lsu-rtl.sha256` 中 `Arbiter3_StoreStageIO.sv =
  d5e0a679...`。
