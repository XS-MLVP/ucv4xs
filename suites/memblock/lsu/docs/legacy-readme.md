> 迁移前历史说明。当前命令与基线见仓库根 README；以下记录不代表重建版本验收。

# LSU 执行流水线独立 UT

XiangShan `kunminghu-v3` 访存执行流水线（LSU）的独立单元测试工程。
本工程只验证 `NewStoreUnit`、`NewLoadUnit`、`StdExeUnit` 三个模块族，**不做跨模块
联合 harness，不做 LSU 整体、MemBlock 顶层或整核集成**。

`AtomicsUnit` 不属于本工程范围。

## 1. 基线与范围

| 项 | 值 |
|---|---|
| 源码 | `../../XiangShan/`，分支 `kunminghu-v3`，提交 `893e1580b705d81f113c30c7a05734e09a08050e` |
| RTL | `../../soc-split/rtl/`（firtool 1.149.0 拆分产物），逐文件哈希 `manifest/lsu-rtl.sha256` |
| 验证框架 | Picker + `toffee run`；安装包/checkout见 `manifest/toolchain.json` 与当前复核报告，不声称已确认远端最新main |
| 构建 | `--rw mem_direct -w memory-direct.fst -c --vflag=--no-coverage-expr --no-coverage-fsm` |
| 覆盖率 | 行 / toggle / branch，保留每个 DUT 独立分母 |
| 运行 | 正常运行不打开波形、不产生逐周期 dump |

外部环境（LSQ、DCache/Uncache、TLB、PMP、Sbuffer、Backend/ROB）由协议代理或激励
模型提供。代理行为不是相应子系统已验证的证据。

## 2. 真实层次与验证顺序

```text
NewStoreUnit
├── StoreUnitS0
│   └── Arbiter3_StoreStageIO
├── StoreUnitS1
│   └── MemTrigger_3
├── StoreUnitS2
├── StoreUnitS3
│   └── DelayPipeline
├── StoreUnitS4
└── NewStoreUnit

NewLoadUnit
├── LoadUnitS0
│   └── Arbiter7_LoadStageIO
├── LoadUnitS1
│   └── MemTrigger
├── LoadUnitS2
├── LoadUnitS3
├── LoadUnitS4
├── LoadUnitDataPath
└── NewLoadUnit

StdExeUnit（无内部子模块）
```

验证顺序严格自底向上，先独立 UT 内部子模块，再做上级模块：

| 阶段 | DUT | key |
|---|---|---|
| 1 | `Arbiter3_StoreStageIO` | `store_arbiter` |
| 2 | `MemTrigger_3` | `store_trigger` |
| 3 | `DelayPipeline` | `store_delay` |
| 4 | `StoreUnitS0` | `store_s0` |
| 5 | `StoreUnitS1` | `store_s1` |
| 6 | `StoreUnitS2` | `store_s2` |
| 7 | `StoreUnitS3` | `store_s3` |
| 8 | `StoreUnitS4` | `store_s4` |
| 9 | `NewStoreUnit` | `new_store_unit` |
| 10 | `StdExeUnit` | `std_exe_unit` |
| 11 | `Arbiter7_LoadStageIO` | `load_arbiter` |
| 12 | `MemTrigger` | `load_trigger` |
| 13 | `LoadUnitDataPath` | `load_datapath` |
| 14 | `LoadUnitS0` | `load_s0` |
| 15 | `LoadUnitS1` | `load_s1` |
| 16 | `LoadUnitS2` | `load_s2` |
| 17 | `LoadUnitS3` | `load_s3` |
| 18 | `LoadUnitS4` | `load_s4` |
| 19 | `NewLoadUnit` | `new_load_unit` |

父块 DUT 必须保留真实下级 RTL；不能用 Python 模型替换子模块后宣称硬件组合通过。

## 3. 每个 DUT 的固定闭环

1. 先写人类可读的微架构语义功能点与接口合同
   （`docs/contracts/<dut>.md`），说明职责、输入合法域、握手/背压/取消/异常/reset、
   关键时序和可观察结果。
2. 建立独立参考模型/检查器与功能覆盖 schema，区分 reached（激励到达）和
   checked（结果被检查）。
3. 运行原生 DUT；真实失败保留为普通 FAIL，不用 xfail/skip/waiver。
4. 分析行 / toggle / branch 覆盖率，保留原始分母。
5. 逐项定位未覆盖行：已有功能点缺失的情形枚举、整体功能点缺失、或不可达/工具
   边界（给出源码或结构证据）。
6. 补功能点或情况枚举 → 补用例 → 重跑，直到功能点全部 reached+checked、
   行覆盖缺口逐项有归因。

## 4. 目录

```text
lsu/
├── README.md
├── conftest.py / pytest.ini
├── docs/
│   ├── contracts/              # 每个 DUT 的用例前合同
│   └── reports/                # 阶段报告、覆盖率审计、交付报告
├── manifest/
│   ├── baseline.json
│   ├── lsu-rtl.sha256          # 19 个源文件哈希
│   ├── closure.json            # 每个 top 的静态闭包
│   ├── duts.json               # 生成清单
│   └── toolchain.json
├── rtl/<key>/                  # 原样 RTL 最小闭包 + filelist.f + source.json
├── dut/<key>/                  # Picker 生成的 DUT
├── lsuverify/
│   ├── common/                 # DUT 加载、reset/时钟、通用核对
│   └── <block>/                # 每个 DUT 的 driver/monitor/model/checker/coverage
├── tests/<block>/
├── tools/                      # prepare/build/run/coverage/delivery
└── results/<unique-run>/       # 种子、coverage、功能覆盖、报告；不含波形
```

## 5. 运行

```sh
python3 tools/prepare_rtl.py store_arbiter
python3 tools/build_dut.py store_arbiter --jobs 8
python3 tools/run.py --name store-arbiter-initial-01 --workers 1 tests/store_arbiter
python3 tools/coverage_audit.py store-arbiter-initial-01
python3 tools/verify_delivery.py
```

运行名必须是全新目录；已存在的 DUT/运行目录拒绝覆盖。

> 验证踩坑与防复发 skill：[`CARD.md`](../../../../skills/rtl-verification-soundness/CARD.md)（速查卡）、[`SKILL.md`](../../../../skills/rtl-verification-soundness/SKILL.md)（实际问题、修正办法与成对回归）
>
> 跨模块假阴性经验总结（LSU + LSQ/Sbuffer/DCache/ICache/MMU/VAGQ）：[跨模块假阴性总结](../../../../docs/lessons/false-negatives-20261026.md)

## 6. 当前状态（2026-10-26失败复核更正）

19个原生DUT构建保留，RTL未改。当前回归 `results/upstream-review-regression-02`：
**582 PASS / 7普通FAIL**，确认7个独立RTL缺陷（含上游 #6742/#6060/#6154/#5810/#6158/#6653）；
已补强恒真断言、S1尾段身份、输入键校验、datapath独立预期和DUT覆盖登记。
父块22个原称不可达的toggle已实际覆盖：**39686/40024**，原分母不变。

历史17次FAIL缺少原始逐节点日志，无法完整归因；声明式功能bin的100%不能证明
独立reached/checked全部完成。**撤回整体关闭/无缺陷结论，当前交付门禁为FAIL。**
旧 `unified-regression-02` 的518 PASS与历史审计保留为旧记录，不是本轮结论。

首读 **`docs/bug-reports-20261026/README.md`**，含7个RTL根因、上游核查、误报/漏报复核、
逐DUT分母及复现命令；机器审计：`review/failure_recheck_20261026/final-audit.json`
（证据一致PASS，不等于设计PASS）。`tools/verify_delivery.py` 当前应返回1。

覆盖率/功能分组/是非判定全表：`docs/reports/coverage-functional-decisions-20261026.md`；
全量548个普通bin、39个交叉bin及逐项命中数：
`review/failure_recheck_20261026/coverage-functional/all-functional-bins.md`（同目录含CSV/JSON）。

逐 DUT 数字、缺口分类、复现命令与验收边界见：

- `docs/bug-reports-20261026/README.md`（当前复核结论，优先于旧交付报告）
- `docs/reports/delivery-status-20261026.md`（历史交付报告，含更正提示）
- `docs/reports/store-family-20261025.md`、`docs/reports/load-family-20261026.md`
- `manifest/coverage-summary.json`、`results/upstream-review-regression-02/delivery-recheck-audit.json`

不声称整个 LSU、MemBlock 或全核已验收；外部代理行为不作为对应子系统已验证的证据。
