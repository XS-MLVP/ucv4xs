# LSU 三模块族独立 UT 交付报告（2026-10-26）

> **同日失败复核更正：以下主体为历史交付口径，不再作为当前验收结论。** 增强回归
> `failure-recheck-final-03` 为 **582 PASS / 1 FAIL**，确认RTL性能缺陷
> `LSU-HWPF-MISS-001`；22个旧不可达toggle已被合法用例命中；历史17次FAIL缺少
> 原始逐节点证据，不能一概归为验证侧误报；声明bin的100%不是独立reached/checked
> 证明。整体关闭结论撤回，当前交付门禁FAIL。见 `../bug-reports-20261026/README.md`。

## 1. 结论

在固定基线 `XiangShan@893e1580b705d81f113c30c7a05734e09a08050e`（kunminghu-v3，
soc-split/firtool-1.149.0 生成 RTL）上，**19 个独立 DUT 全部完成**：

- Picker 原生构建 + 实例化走钟（19 份 build report，`ok=true`、native smoke PASS）；
- 语义功能点文档（19 份合同）、参考模型/检查器、定向与随机用例；
- 行/toggle/branch 三类覆盖审计（逐 DUT 原始分母）、缺口逐项归因、补例重跑；
- 统一回归 **518 PASS / 0 FAIL**，功能覆盖 **19/19 100%**。

交付审计脚本 `tools/verify_delivery.py` 对上述事实做独立复核并输出
`results/unified-regression-02/delivery-audit.json`，状态 **PASS**。

**验收边界**：本目标只覆盖 NewStoreUnit、NewLoadUnit、StdExeUnit 三个模块族的独立 UT
与族内真实子模块组合；不包含跨模块联合 harness、LSU 整体、MemBlock 顶层或整核集成。
外部 LSQ/DCache/Uncache/TLB/PMP/Sbuffer/Backend/ROB 均由协议代理提供，其行为不作为
对应子系统已验证的证据。AtomicsUnit 不在范围内。

## 2. 绑定信息

| 项 | 值 |
|---|---|
| 源码提交 | `893e1580b705d81f113c30c7a05734e09a08050e`（2026-10-16，kunminghu-v3） |
| RTL | `/home/xyl/kmh-v3-test/soc-split/rtl`，19 DUT 闭包哈希见 `manifest/lsu-rtl.sha256` |
| Picker | `2.0.0-HEAD-4dd442c-2026-10-12`（commit `4dd442c4a80c92549381e417c608836e3b78a8e9`） |
| Verilator | `5.052`（`/opt/verilator-5.052`） |
| toffee | `2.0.0.dev12+g3017293a7`（`migration/toffee`） |
| 运行器 | `/home/xyl/xreactor/output/toffee-migration/venv/bin/python` + pytest 9.1.1 |
| 统一回归 | `results/unified-regression-02`（种子 1，2 workers） |
| 构建记录 | `results/builds/`（每个 DUT 一份 report.json，含命令、版本、闭包哈希、smoke） |
| 覆盖汇总 | `manifest/coverage-summary.json`（逐 DUT 原始分母 + 展示合计） |

## 3. 总表（按 DUT 独立分母）

| DUT | 族 | 层 | 用例 | 功能 | 行 | 分支 | toggle |
|---|---|---|---:|---:|---:|---:|---:|
| `Arbiter3_StoreStageIO` | store | leaf | 22 | 100% | 32/32 | 62/62 | 1126/1128 |
| `MemTrigger_3` | store | leaf | 32 | 100% | 48/48 | 16/16 | 762/762 |
| `DelayPipeline` | store | leaf | 14 | 100% | 29/29 | 5/6 | 978/978 |
| `StoreUnitS0` | store | stage | 57 | 100% | 83/83 | 67/68 | 3090/3100 |
| `StoreUnitS1` | store | stage | 41 | 100% | 86/86 | 30/31 | 3836/3872 |
| `StoreUnitS2` | store | stage | 22 | 100% | 32/32 | 5/6 | 1042/1042 |
| `StoreUnitS3` | store | stage | 17 | 100% | 51/51 | 10/12 | 2502/2506 |
| `StoreUnitS4` | store | stage | 6 | 100% | 0/0 | 0/0 | 572/572 |
| `NewStoreUnit` | store | parent | 26 | 100% | 242/257 | 111/119 | 13231/13964 |
| `Arbiter7_LoadStageIO` | load | leaf | 21 | 100% | 195/195 | 346/346 | 3702/3702 |
| `MemTrigger`（load） | load | leaf | 21 | 100% | 33/33 | 10/10 | 762/762 |
| `LoadUnitDataPath` | load | leaf | 24 | 100% | 122/122 | 17/18 | 3928/3928 |
| `LoadUnitS0` | load | stage | 38 | 100% | 285/285 | 387/388 | 8546/8582 |
| `LoadUnitS1` | load | stage | 35 | 100% | 128/128 | 33/34 | 6338/6376 |
| `LoadUnitS2` | load | stage | 46 | 100% | 108/108 | 5/6 | 4234/4280 |
| `LoadUnitS3` | load | stage | 32 | 100% | 84/84 | 55/56 | 5400/5408 |
| `LoadUnitS4` | load | stage | 7 | 100% | 0/0 | 0/0 | 1168/1168 |
| `NewLoadUnit` | load | parent | 40 | 100% | 762/762 | 502/508 | 39664/40024 |
| `StdExeUnit` | std | unit | 17 | 100% | 11/11 | 12/12 | 1058/1058 |

展示合计（**不作为任何 DUT 的分母**）：行 **2331/2346**、分支 **1673/1698**、
toggle **101939/103212**、过程语句未覆盖 **0**。分母为 0 的 `StoreUnitS4`/`LoadUnitS4`
是纯连续 assign 模块，Verilator 只对过程语句计行覆盖。

## 4. 缺口归因汇总

剩余未覆盖点全部为以下四类之一，逐点证据在各 `docs/gaps/<dut>.json`：

1. **结构常量**：生成 RTL 中的字面零/一、被常量折叠的端口、single-bit 恒值。
   例：`io_dcacheReq cmd/instrtype` 高位、perf 计数器高 5 位、被消除的 prefetch lane
   的 entrance 码（`0x10`/`0x20`/`0x80`）、tail 地址低 4 位、LQ cause bit 7/12。
2. **结构互斥导致的死逻辑**：`LoadUnitS2` 的 `perf_3`（`isHwPrefetch` 与 `troubleMaker`
   互斥）、`NewLoadUnit` 的 `perf_7`。
3. **旧“子实例端口复制”归因已撤回21点**：不能从端口声明行或叶子UT已覆盖推导
   父块不可达。新用例实际命中21个cause/身份点，另命中RR下降沿1点，详见复核报告04。
4. **工具边界**：`ENABLE_INITIAL_REG_` 的 `if (reset)` 分支（每个含寄存器的 DUT 一条，
   父块 6 条）；reset 本身在用例中被驱动并检查了 valid/寄存器清零。

**没有**用 xfail/skip/waiver 消除任何失败。仍保留在结果目录中的真实 FAIL run 有：
`store-arbiter-initial-02`（11 PASS / 11 FAIL）、`load-s3-initial-01`（30/1）、
`new-load-unit-final-02` 与 `new-load-unit-final-03`（各 30/1）、
`new-load-unit-final-05`（34/3），以及测试收集失败的 `store-delay-shared-ptr-01`。
**更正**：前五组合计17次FAIL观测没有保存原始nodeid/traceback及当时验证源码，
不能逐一确认根因，撤回“全部是验证侧错误”的原结论。后者只证实collection失败，
不能细化为某个构建问题。所有旧run保留原样；当前补强通过不构成旧失败误报的证明。

## 5. 资源与可复现性

- 正常运行不调用 `SetWaveform`，不产生逐周期信号/事务 dump；
  `trace-policy.json` 记录 `runtime_set_waveform=false`、`stray_waveforms=[]`。
- Picker 默认 `$dumpfile` 被隔离到 `/tmp/opencode` 的临时 cwd，运行结束即删除。
- 每个 run 目录含：`manifest.json`（PASS 计数、worker receipt、coverage_complete）、
  `coverage-audit.json`/`.md`、`functional-coverage.json`、`coverage.html`、
  `trace-policy.json`；本次另含 `delivery-audit.json`。
- 复现：

```
cd memblock-hash/lsu
python3 tools/run.py --name <fresh> --workers 2 tests
python3 tools/coverage_audit.py <fresh>
python3 tools/verify_delivery.py
```

## 6. 交付清单

| 类别 | 证据 |
|---|---|
| 19 DUT 原生构建 | `results/builds/*/report.json`（ok/smoke），`dut/<key>/` |
| 19 份功能点合同 | `docs/contracts/*.md` |
| 19 份覆盖缺口归因 | `docs/gaps/*.json` |
| 用例 | `tests/<key>/test_*.py`，518 例 |
| 统一回归 | `results/unified-regression-02`（518 PASS / 0 FAIL） |
| 覆盖汇总 | `manifest/coverage-summary.json` |
| 交付审计 | `results/unified-regression-02/delivery-audit.json`（PASS） |
| 族报告 | `docs/reports/store-family-20261025.md`、`load-family-20261026.md`、本报告 |

## 7. 未完成/未声明的内容

- 不做 LSU 整体、MemBlock 顶层、整核集成；
- 不把外部代理行为（LSQ/DCache/TLB/PMP/Sbuffer/ROB）当作对应子系统已验证；
- 不覆盖 AtomicsUnit；
- 剩余结构常量/工具边界点已在 gap 文件中逐项声明，未删除点、未改分母、未跨 DUT 合并。
