# LSU Bug复核报告：先看现象，再看代码

本包按已有 **LSQ Bug报告** 的“一句话理解—正常行为—固定源码—怎样激励—为什么是真Bug—影响边界—复现证据”风格整理。分别报告真正的RTL缺陷、验证侧误报/漏报与覆盖论证错误，不把它们混算成一批RTL Bug。日期：**2026-10-26**。

## 1. 结论先读

- **确认7个独立RTL Bug**：原有 `LSU-HWPF-MISS-001`，加上游核查新增6个（Store故障tval、CBO NC误报AF、S3 kill仍写回、matchInvalid残留cause、prefetch.w读意图、StdExe性能计数器）。详见[05](05-upstream-review-20261026.md)。
- **当前回归：582 PASS / 7普通FAIL**，共589项，19 DUT。7个FAIL对应7个已确认RTL根因；未用xfail/skip/waiver，未修改RTL。
- **上游核查**：固定提交仍含 #6742/#6060/#6154/#5810/#6158/#6653 六个问题；#6525是维护者说明的设计选择，#6002路径在本版本不存在。
- **已修正可定位的验证缺陷**：3处恒真断言、S1尾段身份未检查、静默忽略的错误输入键、未对齐datapath激励/预期不充分、factory DUT覆盖采集遗漏，以及失败日志不保留。
- **撤回22点不可达结论**：父块cause/身份复制点21个与RR下降沿1个，合法新用例已经命中；父块toggle提升为 **39686/40024**，分母未改。
- **历史17次FAIL无法完整逐节点追溯**：5个run只有计数，没有原始traceback和测试版本；另1个run是收集失败。撤回“历史失败全是误报”的笼统结论。
- **不承诺所有假阳性/假阴性已穷尽消除**：逐bin独立reached/checked、全局合法随机约束和初始化盲区的完整证明仍有限制。证据一致性审计PASS，**当前交付验收为FAIL**，不能再称整体关闭。

> 验证踩坑与防复发 skill：[`CARD.md`](../../../../skills/rtl-verification-soundness/CARD.md)（速查卡）、[`SKILL.md`](../../../../skills/rtl-verification-soundness/SKILL.md)（实际问题、修正办法与成对回归）
>
> 跨模块假阴性总结（LSQ、Sbuffer、DCache、ICache、MMU、VAGQ 经验）：[`../../../../KMH-V3-VERIFICATION-FALSE-NEGATIVE-LESSONS-20261026.md`](../../../../KMH-V3-VERIFICATION-FALSE-NEGATIVE-LESSONS-20261026.md)

## 2. 每类问题一个入口

| 报告 | 类型 | 一句话说明 |
|---|---|---|
| [01：硬件预取miss事件恒0](01-LSU-HWPF-MISS-001.md) | **确认的RTL性能Bug** | 预取与普通Load重放原因互斥，miss事件却同时要求二者 |
| [02：全部历史与本轮失败复核](02-false-positive-review.md) | 误报裁定/证据不足 | 哪些已证实是验证错误，哪些因缺原始日志只能未决 |
| [03：为什么全绿仍会漏报](03-false-negative-review.md) | 检查器/模型缺陷 | 恒真断言、尾段身份漏检、无效驱动、同源预期与有界故障对照 |
| [04：覆盖及交付结论撤回](04-coverage-and-evidence-review.md) | 覆盖/流程缺陷 | 22点可达反证、残余分母、100%功能bin的实际含义 |
| [05：上游核查](05-upstream-review-20261026.md) | 上游比对/新增6个RTL Bug | 固定提交仍含Store tval、CBO NC、S3 kill、matchInvalid、prefetch.w、StdExe计数器问题 |
| [06：为什么没检查到](06-why-missed.md) | 验证盲区复盘 | 同源模型、检查点选错、组合缺失、bin只记录采样；加断言仍会漏 |

**Bug数量为7**：同一失败在多个run、种子、层次的静态传播及同一根因的多个上游编号不重复计数。验证侧问题另列，不把它们计入RTL Bug。

## 3. 版本、范围与工具

| 项目 | 本报告的口径 |
|---|---|
| 固定源码 | `OpenXiangShan/XiangShan`，`kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e` |
| RTL | 原soc-split生成文件；逐文件核对 `manifest/lsu-rtl.sha256`，未修改/重生成目标RTL |
| 范围 | NewStoreUnit族9 DUT、NewLoadUnit族9 DUT、StdExeUnit 1 DUT；父块使用真实子模块 |
| 排除 | AtomicsUnit、跨族联合harness、LSU/MemBlock整体及整核集成 |
| 外部环境 | LSQ/DCache/Uncache/TLB/PMP/Sbuffer/Backend/ROB仅为协议代理，不宣称这些子系统已验证 |
| Picker / Verilator | `2.0.0-HEAD-4dd442c-2026-10-12` / `5.052`，绑定既有原生构建 |
| Python环境 | `/home/xyl/xreactor/output/toffee-migration/venv/bin/python`，pytest 9.1.1 |
| toffee | 工具锁包版本 `2.0.0.dev12+g3017293a7`；checkout分支 `migration/toffee`，不伪写main；本地HEAD与本地origin/main同为 `4a09d21a89d2a8367efd56cbd440575edbe646d3`，未联网确认远端最新状态 |
| 修复/外部提交 | RTL未修；未查询GitHub重复报告，未提交Issue/PR或推送本地文件 |

## 4. 实际执行结果，不跨run合并通过率

| 运行/分组 | PASS | FAIL | 解释 |
|---|---:|---:|---|
| `upstream-review-regression-02` 全套 | **582** | **7** | 589项、19份原生coverage数据库、0 SKIP/ERROR |
| 其中普通 `tests/` | 522 | 7 | 含1个性能规范反例、5个上游原生端口反例、1个StdExe源码检查 |
| 其中独立复核 | 22 | 0 | 原始引脚、字节级预期、无prime首访问等 |
| 其中检查器敏感性对照 | 38 | 0 | 19 baseline+19故障应被拒绝的元测试，不是19个RTL变异已验证 |
| `recheck-prefetch-spec-02`，seed1 | 1 | 1 | 命中负对照PASS，miss反例FAIL，单DUT原生数据库齐备 |
| `recheck-prefetch-seed-17-01` | 1 | 1 | seed17重复根因 |
| `recheck-prefetch-seed-123-01` | 1 | 1 | seed123重复根因 |

早期 `failure-recheck-regression-01` 的580 PASS是在加入规范断言前，**不是最终全绿结果**。中间新增断言错误、灵敏度脚本挂接错误及修正前后证据均保留，详见02。

## 5. 每DUT原始分母

以下来自当前 `results/upstream-review-regression-02/coverage-audit.json`；与上一轮覆盖率相同。父块计入真实子模块闭包；不与叶子UT合并分母。行分母0的S4是纯连续assign，不伪写成若干“已覆盖行”。

| DUT key | 行 | branch | toggle |
|---|---:|---:|---:|
| store_arbiter | 32/32 | 62/62 | 1126/1128 |
| store_trigger | 48/48 | 16/16 | 762/762 |
| store_delay | 29/29 | 5/6 | 978/978 |
| store_s0 | 83/83 | 67/68 | 3090/3100 |
| store_s1 | 86/86 | 30/31 | 3836/3872 |
| store_s2 | 32/32 | 5/6 | 1042/1042 |
| store_s3 | 51/51 | 10/12 | 2502/2506 |
| store_s4 | 0/0 | 0/0 | 572/572 |
| new_store_unit | 242/257 | 111/119 | 13231/13964 |
| std_exe_unit | 11/11 | 12/12 | 1058/1058 |
| load_arbiter | 195/195 | 346/346 | 3702/3702 |
| load_trigger | 33/33 | 10/10 | 762/762 |
| load_datapath | 122/122 | 17/18 | 3928/3928 |
| load_s0 | 285/285 | 387/388 | 8546/8582 |
| load_s1 | 128/128 | 33/34 | 6338/6376 |
| load_s2 | 108/108 | 5/6 | 4234/4280 |
| load_s3 | 84/84 | 55/56 | 5400/5408 |
| load_s4 | 0/0 | 0/0 | 1168/1168 |
| new_load_unit | 762/762 | 502/508 | **39686/40024** |

所有原始分母相对旧统一回归逐DUT核对不变。功能工具仍报告21组100%，只表示声明bin采样，不是独立语义检查完成率，也不能使真实性能FAIL变PASS。

## 6. 如何追到测试与原始证据

路径均相对 `memblock-hash/lsu/`：

- [上一轮证据一致性审计](../../review/failure_recheck_20261026/final-audit.json)：`evidence_consistency=PASS`、`acceptance_passed=false`、逐失败节点、每DUT覆盖差分、历史manifest哈希、RTL/构建/执行源码核对。
- [上游核查审计](../../review/upstream_check_20261026_01/audit.json)：6个新增Bug、Issue状态、原始API响应、RTL/源码哈希与7个失败节点。
- [当前运行manifest](../../results/upstream-review-regression-02/manifest.json)、[JUnit](../../results/upstream-review-regression-02/junit.xml)、[console](../../results/upstream-review-regression-02/console.log)、[provenance](../../results/upstream-review-regression-02/run-provenance.json)。
- [逐DUT覆盖审计](../../results/upstream-review-regression-02/coverage-audit.json)、`native/<build-id>/coverage.dat`及LCOV；正常运行无波形/逐周期dump。
- [最小反例console](../../results/recheck-prefetch-spec-02/console.log)及同目录manifest/JUnit/native。
- [22点覆盖差分](../../review/failure_recheck_20261026/coverage-delta.json)、[旧源码/历史清单](../../review/failure_recheck_20261026/inventory.json)与`before/`快照。
- [当前交付门禁](../../results/upstream-review-regression-02/delivery-recheck-audit.json)：**FAIL**，明确列出已知RTL缺陷、历史证据不足和独立reached/checked未闭环。旧 `unified-regression-02` 原证据不改写。
- 新回归：[manifest](../../results/upstream-review-regression-02/manifest.json)、[JUnit](../../results/upstream-review-regression-02/junit.xml)、[console](../../results/upstream-review-regression-02/console.log)。

复核证据一致性（不重新仿真、不把它当设计PASS）：

```sh
python3 -B tools/review_failure_evidence.py
python3 -B tools/verify_delivery.py
```

第一条应返回0且证据一致；第二条应返回1并报告交付FAIL。真实性能反例复现命令见01；所有仿真run名必须全新。

## 7. 还不能宣称完成什么

本轮完成了现存失败证据盘点、可定位误报修正、具体漏检路径补强及Bug报告，但**不能补造旧失败的逐节点证据，也不能保证不存在其他未建模Bug**。不以“高覆盖+检查脚本PASS”代替语义验收，不以父块静态连接代替不存在入口的动态复现。
