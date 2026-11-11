# BPU 新基线验证适配（2026-11-03，实施与回归交付）

本轮六阶段适配、完整 seed1 和关键链双 seed 已执行，交付审计见文末。**硬件结果仍为
FAIL，migration_acceptance 为 NOT_CERTIFIED**；这不是全 BPU 功能或完整 FTQ 签核。

> 2026-11-08后续实施单独记在[收口检查点](closeout-20261108.md)：owner严格审计24→0，
> 原25节点定向前后判定0变化；INT041/059第一层适配后仍遇下一阻挡。下文所有完整/双seed
> 数字仍属于11月3日冻结源码，不重标为11月8日覆盖或功能签核。

## 版本与范围

- 目标：`public-a0c2a26cb`，XiangShan `a0c2a26cbe3c862175174bad03a1a23c406315ed`。
- 对照：`public-893e1580b`。旧合同、MinimalConfig 和旧结果均保持原版本含义。
- 配置保持完整香山 `DefaultConfig`，从完整 RTL 提取十个真实 DUT 闭包；不修改 RTL、
  不增加 BPU 专用生成器或单 DUT override，不更改 Toffee/工具锁。
- 只更新本工程验证；FTQ/IFU 源码仅作 producer 合同核对。预测错误不自动等于架构错误。

## 变更到验证的追溯

对保存的旧 build/signals 与新版实际产物逐项比较，
`per-dut-old-new-abi-rtl-delta.json` 确认：只有 Bpu/Ras 的 `cfiPc_addr` 从49到50位，
以及 MainBTB 新增两 align × 第五槽 `rawHit/position` 四个训练输入；没有端口删除或
其他宽度/方向变化。其余七 DUT 的完整闭包文件名及每份 RTL 哈希与旧构建完全一致。
这不能把旧功能 PASS 自动继承给新运行，也不能消除旧证据的源码稳定性限制；本轮
仍重新构建、冒烟并执行它们的定向/全量验证。

| 上游依据 | 行为合同 | 验证入口 | 用例/范围 |
|---|---|---|---|
| `b716aade5`；`BpuRedirect.cfiPc: GuardedPc` | 实际 guard 不能按 virtual sign 重建或截掉 | `bpu/transaction/types.py`、`ras/driver/encoding.py`、`ras/monitor/semantic.py` | `BPU-RAS-018`、`BPU-INT-113`；guard 与 sign 的反向组合是端口边界压力，不计 FTQ 可达信用 |
| 同提交；`Ras.scala` 恢复地址 | guarded 指令末字节地址 + 2，以 51 位回绕 | `ras/model/semantic.py`、`ras/case/redirect_redo_scenario.py` | 公开 top、正常 checkpoint、年轻错误路径和回绕；独立字节算术，不读取实际 top 作期望 |
| 同提交；`Phr.scala`/`Bpu.scala` 的 `unGuard` | 对外保留 guard，内部历史仅消费虚拟 PC | `bpu/model/pipeline.py`、`bpu/monitor/guarded_redirect.py`、原 PHR checker/monitor | 动态比较公开/PHR 输入 50 位与 CommonHR 输入 49 位；PHR 的内部 unGuard 结合源码低位 hash 与独立物理 cell/fold 检查，不冒称所有高位或已裁公开 target 已验证 |
| `05f65879a`；MainBTB 完整预测 metadata 回传 | 第五槽原预测身份进入训练 | `mbtb/bundle/abi.py`、`transaction/metadata.py`、`driver/feedback.py`、`monitor/semantic.py`、`agent/main.py` | 两 align 的 `rawHit/position`；训练端没有第五槽 counter/attribute，不补造字段；不再接受缺失第五槽的反馈 |
| 同提交；隐藏 VBTB 分支可分配 Main | 物理驻留不等于曾向原预测暴露；真实暴露且仍驻留才就地修正 | `mbtb/model/semantic.py`、`mbtb/model/victim.py`；顶层复用同一自主 Main 模型 | `BPU-MBTB-031`；正常六分支前史及早 conditional NT，offset 新消费者分别区分 Main 和 VBTB |
| 同提交；conditional NT 不写 entry | resolve target 为顺序下一 PC，不能替代 branch target | `mbtb/model/semantic.py` | `BPU-MBTB-032`；冷 NT 不分配、暖 NT 方向减弱且 target 不变；None/NT 假命中纠正仍可失效 |

主模型仍由 reset、输入历史与独立存储维护 expected。Main 的更新按语义分步判断
payload 是否存在、原暴露身份与当前自主驻留是否一致；不复制 RTL 的合并布尔表达式。
原 semantic checker 对 tag-qualified 方向学习、retained owner 等承诺保持，不为兼容新 RTL
改成实现现状。来自真实 lookup 的第五槽与 UID/epoch 一并对账，诊断 deepcopy 不改变祖先。

### 独立的 producer 依据

这些语义不仅来自待验证 MainBTB 的新条件表达式。固定目标 commit 下另沿 producer 追溯：

- `backend/fu/wrapper/BranchUnit.scala:26-29,73-81`：不跳转分支选择顺序
  `pcExtend + nextPcOffset`，同一结果进入 `toFrontendBJUResolve.bits.target`；故 NT 的
  target 不是分支 taken target，不能用于覆盖持久预测记录。NT 样本采用明确的 RVC
  顺序后继（半字 CFI 位置 +1），并与正常 taken 分配/再学习对照。
- `frontend/ftq/ResolveQueue.scala:76-79,142-145` 和
  `frontend/bpu/Bundles.scala:242-248`：resolve 的 target/taken/attribute 继续传递，
  不会在入 BPU 前把 NT 的顺序结果重建成旧 taken target。
- `frontend/ifu/PredChecker.scala:179` 与 `Ifu.scala:742-745`：无 CFI 却预测 taken 的
  纠正仍可携带 `None` 属性并获得 canTrain，不能把所有 not-taken 统一禁用 entry 修正；
  `ftq/IfuRedirectReceiver.scala:49-56` 保留相应 resolve。
- `frontend/ftq/Ftq.scala:387-392`：CFI PC 由 `GuardedPcInit(redirect.bits.pc)` 和真实
  offset 计算后传给 BPU，meta 来自原 redirect FTQ 索引。新编码需保留 producer 的
  guard，而不是重新按符号位构造。端口高 guard 压力仍不自动证明完整 FTQ 事件链可达。

所有行号仅定位上述固定 commit，不作为其他版本的合同；原生动态结果仍须另行核验。

## 地址和 metadata 合同变化

- `BpuRedirect` 的 `pc` 和 `cfi_pc` 为 50-bit **guarded 半字**地址。省略 `cfi_pc`
  的旧便利形式仍取 target，但不再截为 49-bit；显式来源的调用应继续传真实 CFI PC。
- RAS 恢复 API 的 `cfi_pc` 为偶数 51-bit **guarded 字节**地址；编码仅去 bit0。
  原 `call-distinct-negative` 准备常量从 `2^50-offset` 明确迁为 `2^51-offset`，保持原
  “canonical 负地址”语义，不声称该物理激励字节不变。
- MainBTB 保存完整 `2×5` 预测快照，训练仅投影第五槽的 `rawHit/position`。
  快照中的第五槽 counter 仍是输出观察，不成为新的训练输入。
- 四槽旧快照不再可发射；旧四槽构造自检保留 nodeid、改为验证明确拒绝。
  其他宽度、稀疏八槽 resolve、唯一 mispredict、PC 单位和来源合同不放宽。

## 成对控制与证据边界

实施起点保存在 `results/bpu-a0c2a26cb-before-20261103`：42,576 个 nodeid，源码身份
`6137b83c5ccd2043ab0384806cc49927250b1045bdbde8387c7a6aafcf9744f9`。
collection 的 run 状态 PASS、源码前后稳定；CLI exit1 不作为硬件结果。

外部执行证据目录为 `/tmp/opencode/bpu-upgrade-a0c2a26cb-20261103/`，最终以机器索引
记录其收据/日志 hash；完整 RTL/native/结果不进入 Git。
已核验阶段的[机器索引](../../../../../../../../docs/history/bpu-baseline-update-a0c2a26cb-20261103.json)
保留每次运行的范围与失败，不将候选或未完成尝试标为最终验收。

标准命令 `.venv/bin/ucv build bpu --require-unified-baseline --jobs 32` 已正常结束，
`build.log` 为 **10/10 BUILT + SMOKE PASS**。`build-audit-ten.json` 逐 DUT 核对完整
基线、工具锁、活动链接、闭包收据及全部 RTL/native 输出哈希，并保存独立 smoke
日志哈希；每个 smoke 都在独立 Python 子进程和临时 cwd 中实际 reset/step/finish。
这是新版构建与加载证据，**不是十 DUT 功能全 PASS**。

旧对照另存为该目录的 `historical-cases.json`：逐 DUT 保留原 selection、seed、源码身份、
基线、原始判定和 cases 哈希，不合成一个“旧全量总数”。Bpu 的旧 33 项仅是已审计的
敏感链子集；不是整个顶层的旧完整结果。所选 ABTB/TAGE 旧运行未满足
`source_after == source.sha256` 的本次严格判据，保留为历史线索，不能用来认证严格
新旧回归或直接给“新版引入缺陷”的结论；其余比较也仍受原源码和 selection 限制。

- `abi-red.xml`：旧实现 7 FAIL / 8 PASS，失败分别为高 guard 截断、RAS 拒绝真实 guard、
  第五槽丢失、缺失槽未拒绝和旧固定 ABI。不是 RTL mutation。
- `semantics-red.xml`：旧模型 3 FAIL / 3 PASS，隐藏 VBTB 分配及两个 conditional NT
  payload 控制失败；就地训练、None 失效及无驻留对照仍通过。
- `pure-green-v1.xml`：同一控制修后及现有相关自检 **199 PASS**，不计硬件信用。
- `results/bpu-a0c2a26cb-leaf-probe-v1-20261103`：已审计的 MainBTB/RAS 新构建分别
  **7 PASS / 6 PASS**。包括隐藏/暴露 VBTB、NT/None 三种场景及两个真实第五槽 wire
  注错控制；RAS 包括五种 guard/sign/回绕场景与旧截断 codec 注错。两个 manifest 均为
  committed，coverage_complete/cleanup_complete 为 true，源码与 build/native 前后稳定。
  该批沿既有 Toffee managed 分区提前验证叶模块，不是完整 `ucv` BPU 回归。
- `pure-broad-v1.xml`：纯文件扩展诊断 **39733 PASS / 170 FAIL / 7 SKIP**；未选择混有
  native 用例的文件，不作为完整 BPU/RTL 判定。定位后补齐 shared-service 自检的第五槽
  与仅两字段的训练 wire 夹具；功能点精确计数更新为初始 364 + 新增 4 = 368
  （358 hardware / 10 environment），没有删除旧 ID，未放宽为不等式。
- `initial-selected-replay.xml`：隔离 Git 初始 HEAD 的纯诊断 **163 PASS / 77 FAIL**，
  重现 65 个 short-competition、旧 PHR flag/metadata-ready、旧 mock 等失败。它不含 DUT，
  只帮助区分既有验证债务，不是一次旧硬件回归。新引入的第五槽夹具失败没有因此豁免，
  修后定向 `pure-adapter-fixes-v1.xml` 已通过。
- 后续对上述全部 170 个失败节点逐项重放初始 HEAD，
  `initial-all-failing-pure-replay.xml` 为 **75 PASS / 95 FAIL**。75 项 PASS 全是本轮
  第五槽夹具遗漏；95 项 FAIL 在初始代码已存在，其中 16 项旧功能点计数已随新增点
  一起精确更新，其余验证债务仍须按最终完整回归分类。初始快照不含原生 DUT，不能将
  这份重放解释为旧版硬件结果或整个旧验证集全量回归。
- 当前冻结源码对同一 170 节点的定向复验
  `pure-failing-nodes-after-adapter-fixes.xml` 为 **91 PASS / 79 FAIL**，源码前后稳定。
  91 项修复为 75 个本轮第五槽夹具遗漏与 16 个既有功能点计数滞后；剩余 79 项全部在
  初始代码已 FAIL（65 个 short-competition helper 前提、旧 PHR/mock/shape、两项旧
  runtime 检查等），没有借此关闭旧验证债务，也不把它们归为新版 RTL 功能失败。
- 第一份 `ucv` directed-v1 只是在构建锁处排队。为修复扩展检查发现的问题，核实无
  partition、tasks 为空、尚未执行测试后，仅向精确队列 PID 发送 SIGINT。最终 run 为
  ERROR、源码仍稳定；取消收据和日志保留。构建未中断，此未运行尝试不给任何覆盖信用。
- 最新 `results/bpu-a0c2a26cb-collection-v1-20261103/audit.json`：**42576 → 42619**，
  新增 43、删除 0，原 nodeid 相对顺序全部保持。collection 不计硬件通过。
- 标准 `results/bpu-a0c2a26cb-directed-v2-20261103`：**820 PASS / 1 FAIL**，
  分区为 Bpu 35/1、pure 772、MainBTB 7、RAS 6；源码 `6121cb37...` 前后稳定且全部
  源文件逐 hash 匹配。原已审计 Bpu 敏感链 33 项逐项判定不变，包括 PHR、背压、reset、
  short/entry/positive 的现有检查。九份覆盖产物、49 个原生输入及所有构建/处理器哈希
  已核对，四个 manifest 都 committed / coverage_complete / cleanup_complete。
  唯一新增高 guard 场景在公开/PHR 50 位和 CommonHR 49 位断言、PHR drain 后，因
  `PipelineReference.lookup_history()` 仍把未去 guard 的 CFI 交给严格 49 位历史算法而
  FAIL。这是明确的验证模型漏适配，不冒称 RTL 缺陷；外部 `guarded-lookup-red.xml`
  为 **7 PASS / 2 FAIL**，分别区分 taken/NT、guard 和 virtual sign。保留失败与
  标准报告的 exit1，待当前 seed2 冻结运行结束后修复并用新目录重跑。
- `results/bpu-a0c2a26cb-critical-seed2-v1-20261103`：真实 seed2 为 **814 PASS / 1 FAIL**，
  重现同一 lookup preview 漏适配；源码/构建/九份合并覆盖产物及处理器哈希稳定。
  该次启动脚本误按 argv 固定下标截取选择，实际漏掉 `test_semantic_pipeline.py` 和
  `test_entry_protection.py` 的六个原生节点。审计保留真实选择和缺项清单，已执行的旧
  27 个敏感链节点判定保持；不能沿用命令索引中的“同一关键链”意图标签，也不计作
  完整关键链 seed2 验收。修后重跑须按 `--` 的实际位置解析完整选择。
- `results/bpu-a0c2a26cb-leaf-seed2-v1-20261103`：完整所选 MainBTB/RAS 加生命周期控制
  的真实 seed2 为 **3448 PASS / 14 FAIL / 1 XFAIL**，其中 pure3253 PASS、
  MainBTB166 PASS/9 FAIL、RAS29 PASS/5 FAIL/1 XFAIL。初始 MainBTB168 个和 RAS29 个
  历史节点均执行且判定逐项不变；新 guard/victim 功能和错误控制通过。源码前后为
  `6121cb37...`，210 个原生输入、六份覆盖产物、native 与 processor 哈希及进程
  单 DUT 隔离均审计。此批完整的是叶模块选择，不是全部 BPU；与旧结果 seed/验证
  源码不同，比较不外推成严格双基线同 seed 等价。
- 为保持上述运行冻结，guard lookup preview 单行修复先在逐文件复制的隔离候选中
  验证：`guard-preview-candidate-pure.xml` **197 PASS**，包含同一九条 red 控制及现有
  pipeline/域检查；`guard-preview-candidate-native` **3 PASS**（顶层两功能、一截断
  输入错误控制），源码和三份覆盖/native/处理器哈希稳定。候选没有修改生产源码，
  不算已合入或最终验收；生产仍需合入后重新冻结与标准回归。
- `results/bpu-a0c2a26cb-other-directed-v1-20261103` 已完成：七 DUT 共 **14 PASS /
  43 FAIL / 2 XFAIL**，59 个预选节点全部与历史判定相同，59 原生输入的进程隔离、
  源码、十构建和覆盖产物哈希审计通过。ABTB/TAGE 的旧源码稳定性限制仍不撤回。
- 2026-11-03 后续：上述冻结运行全部结束后已合入 guard lookup preview 修复及九条纯
  控制，并补第二 physical alignment 的真实 victim 身份/目的地与 wire 注错控制。
  首个隔离候选 **9 PASS/2 FAIL** 是准备激励混淆 physical bank 与 fetch-window ordinal；
  依据 `window()` 合同修正实际位置编码后 **11 PASS**。保留失败候选，不放宽模型、
  祖先或 RTL 断言，不把“不满足准备条件”称硬件错误。
- 合入后所有运行源文件与通过的候选逐字节一致，新冻结身份为 `18a8e5d2...`。生产
  相关纯控制 **197 PASS**。标准 directed-v3 seed1、完整 critical-seed2-v2 已安排；两者
  必须原始判定 PASS 且 source/build/manifest/覆盖哈希审计通过，随后才自动启动无任何
  pytest 选择的完整 BPU seed1-v1（32 workers）。这一排程不计执行或通过信用；期间
  Python/JSON 源码继续冻结。
- 修后正式 `results/bpu-a0c2a26cb-directed-v3-20261103` 已结束：**834 PASS**
  （Bpu36/pure781/MainBTB11/RAS6），53 原生输入；源码、十构建、覆盖/处理器及单 DUT
  进程隔离独立审计通过。旧33个敏感链节点判定保持，高 guard 的新 FAIL 已修成 PASS。
  raw run.status 为 PASS，但 CLI exit1 / hardware_verdict INCOMPLETE 来自三项开放残余，
  不把“执行用例全 PASS”改写成完整硬件或生产者可达性验收。
- 修后 `critical-seed2-v2` 也为 **834 PASS**，真实 seed2、同一源码，partition 的全部
  case 条目与 seed1 完全相同；53 原生输入及所有产物已独立审计，旧33个敏感节点均在。
  首次漏六项的 seed2-v1 仍单独保留，不把它重标为本次完整选择。
- 无显式路径的完整 seed1-v1 在 collection42632 后，11 个执行分区都因 pytest 未发现
  BPU conftest 的分区选项而 exit4/ERROR，**无 cases.json、零用例执行**。已逐日志
  保存启动错误，不给硬件判定或完整回归信用；没有为绕过它修改公共编排或工具锁。
  新 `full-seed1-v2` 显式使用 `-- tests` 整个既有根，不传 -k/-m/子目录/nodeid，实际
  partition42632条及顺序与最终 collection-v2 完全相同。这不是缩小测试范围；实际完整
  终态与产物审计见下节，首尝试的 ERROR 不据此重标。
- 同源码完整 collection-v2 为 **42632 项**，相对初始新增56/删除0、相对42619新增13/
  删除0，两个旧集合的相对顺序都保持。修后根测试 **268 PASS / 64.51秒**，常规结构、
  资产与锁定框架检查通过；严格事务门禁旧exit1独立保留。
- 叶模块 seed2 的覆盖另按既有 `coverage/rtl.py` 口径审计：MainBTB source lines
  **4008/12118**、branch arms **1720/2654**；RAS **804/838**、branch arms **282/316**。
  不混 Picker wrapper 或 toggle 计数到行命中，原生汇总包含失败与错误控制，只给
  运行测量信用，不给功能点 PASS 或覆盖闭环。完整 seed1 的覆盖另外列示，不拼成同次运行。

## 完整 seed1 的实际结果

命令（仓库根）：

```sh
.venv/bin/ucv run bpu --require-unified-baseline --workers 32 --seed 1 \
  --output results/bpu-a0c2a26cb-full-seed1-v2-20261103 -- tests
```

同一冻结源码 `18a8e5d29233d719e844e57a1ac90ee27ae22b2d736a568f1eb4cc3435d4f3f0`
运行前后不变，完整 **42632 项**与 collection-v2 的条目和顺序完全一致，判定无缺项。
CLI exit1，raw run.status / hardware_verdict 为 FAIL，migration_acceptance 为 NOT_CERTIFIED。

| 分区 | PASS | FAIL | ERROR | SKIP | XFAIL |
|---|---:|---:|---:|---:|---:|
| Bpu | 101 | 1550 | 5 | 0 | 0 |
| 纯自检 | 39863 | 79 | 0 | 7 | 0 |
| MicroTAGE | 235 | 35 | 0 | 0 | 1 |
| AheadBTB | 94 | 1 | 0 | 0 | 0 |
| MicroRAS | 33 | 5 | 0 | 0 | 0 |
| ITTAGE | 43 | 3 | 0 | 0 | 0 |
| MainBTB | 171 | 9 | 0 | 0 | 0 |
| RAS | 30 | 5 | 0 | 0 | 1 |
| SC | 62 | 0 | 0 | 0 | 0 |
| TAGE | 248 | 0 | 0 | 0 | 1 |
| MicroBTB | 50 | 0 | 0 | 0 | 0 |
| **合计** | **40930** | **1687** | **5** | **7** | **3** |

`integrity-audit.json` 逐项核验全部 case、十个当前构建、原生 processor、合并产物、
manifest committed / coverage_complete / cleanup_complete，以及单进程单 DUT owner。
共 **2683 个原生实例输入**，不是 42632 个硬件用例；纯自检不计硬件信用。
相对初始 collection 新增的 **56 个 nodeid 全部 PASS**，旧 nodeid 无删除、相对顺序保持。
原生硬件功能点绑定为358点全部执行：234 PASS / 119 FAIL / 4 ERROR / 1 XFAIL；环境点
8 PASS / 2 FAIL。四个新增点均 PASS。绑定失败包含观察/适配债务，不自动等于 RTL 缺陷。

全部1702个非 PASS 已建立逐 nodeid 索引，包含失败阶段与第一错。初始源码同 runtime
重放确认79个纯 FAIL 已存在；七个纯 SKIP 是缺少冻结 ABTB 旧覆盖报告，并非新增豁免。
MainBTB/RAS/MicroTAGE/ITTAGE 的52个 FAIL 与既有日志首错一致，三个 XFAIL 原因不变；
ABTB 的1个 FAIL 首错也一致，但旧 ABTB/TAGE 源码稳定性限制仍保留。

### 旧版真实重放与逐项分类

`results/bpu-old-initial-replay-v2-20261103` 使用隔离的初始验证源码，仅将隔离目录根
基线显式设为 `public-893e1580b`，链接已逐哈希核验的旧 native/RTL；未改生产工程配置
或活动 native 链接。完整初始 collection42576条及顺序复现后，只实际执行 Bpu1653项
和 MicroRAS38项，真实 seed1 / 24 workers。隔离源码身份 `18067310...` 前后稳定，旧
构建、manifest、覆盖产物、processor 及单 DUT 进程隔离均核验。

| 实际旧版分区 | 旧版结果 | 新版在原节点上的结果 | 判定变化 |
|---|---|---|---:|
| Bpu，1653项 | 98 PASS / 1550 FAIL / 5 ERROR | 完全相同 | 0 |
| MicroRAS，38项 | 33 PASS / 5 FAIL | 完全相同 | 0 |

旧版与新版的1560个非 PASS，不仅判定相同，所有失败 phase 的第一处错误也一致
（去除无语义的 Python 对象内存地址；保留 expected/actual、PC、字段和 metadata 值）。
五个 ERROR 的 call 原错与 teardown 次生错误均分别匹配，未用 teardown 错掩盖首错。
这份实际重放补足原 Bpu 仅33敏感链的证据，**不是合成的旧版全部 BPU 回归**。
首次重放 collection 因只读旧 RTL 链接不全而 exit2、零 native 执行，单独保留在
`results/bpu-old-initial-replay-20261103`；补齐链接后新目录重试，不改首尝试结果。

最终 `nonpass-final-classification.json` 精确覆盖1702个非 PASS：

| 证据分类 | 节点数 | 结论边界 |
|---|---:|---|
| 初始验证源码 + 旧 native 实际复现 | 1560 | Bpu1555、MicroRAS5；判定及全部失败phase首错一致，非所有根因认证 |
| 初始源码同 runtime 复现的纯 FAIL | 79 | 验证技术债，不计 RTL 反例 |
| 原稳定历史模块的同首错 FAIL | 52 | MainBTB9/RAS5/MicroTAGE35/ITTAGE3；保留各原seed/源码/选择 |
| 原 ABTB 同首错 FAIL | 1 | 旧source-after不稳定，只给历史诊断佐证 |
| 原 strict XFAIL、原因未变 | 3 | RAS/MicroTAGE/TAGE各一，不计PASS |
| 原缺失冻结 ABTB 报告的 SKIP | 7 | 原测试源码及skip条件未变，不扩豁免 |

Bpu的1555个非 PASS 又按首错标注：906个缺旧内部观察叶、267个旧52-cell PHR形状、
92个旧字段适配、3个旧TAGE数组形状、13个旧helper/finish/producer前提，12个涉及
公开投影边界；其余262个为断言、比较、超时、域检查或对象可用性错误，根因仍需独立
审查。所有分类均有原nodeid、日志行、原始消息及来源，不将“旧版也失败”写成“全部
旧 RTL 缺陷”，不将目标不可观察写成 target 功能通过。

本轮明确修正的验证滞后是 guard/第五槽编码、学习模型、lookup preview 消费投影、
75个第五槽夹具和16个旧点数断言。现有可比硬件旧节点没有 FAIL→PASS 或 PASS→非PASS，
故不凭节点计数声称上游修复数；上游两类行为变更由独立合同、定向正负控制及源码差分
证明。没有新出现的原节点判定变化，不代表已排除所有潜在新 RTL 问题或后续被首错挡住
的行为。历史反例与未确认根因继续归 `BPU-UPGRADE-SEM-01`，不在本轮改 RTL 或豁免。

### 原生覆盖测量与分析限制

完整运行的 `native-coverage-measurement.json` 从已核哈希的十份原生合并产物，用既有
`v_line + v_branch` LCOV `DA/S` 跨行展开算法计算 source lines，另外统计 branch arms
和 toggle points；不将 wrapper/toggle 并入 RTL 行命中。`coverage-audit-v2/` 保留每 DUT
过滤后的 LCOV 与未覆盖行/点清单。

| DUT | RTL source lines 命中/总数 | branch arms 命中/总数 | toggle points 命中/总数 |
|---|---:|---:|---:|
| Bpu | 43349/85838 | 10378/19856 | 135617/459298 |
| MicroTAGE | 11279/11286 | 3725/3734 | 8758/11384 |
| AheadBTB | 13256/13326 | 2768/2840 | 16956/21642 |
| MicroRAS | 72/73 | 25/26 | 878/880 |
| ITTAGE | 2126/2190 | 1218/1670 | 18964/212758 |
| MainBTB | 3986/12118 | 1698/2654 | 22723/54496 |
| RAS | 804/838 | 282/316 | 3918/7222 |
| SC | 4556/5245 | 1878/2256 | 29135/41226 |
| TAGE | 4978/5308 | 2841/3154 | 27837/66424 |
| MicroBTB | 862/867 | 176/180 | 5012/5868 |

原 `report_native_coverage.py` 通过工程 `_summarize` 进行附加 ABTB counter 坐标注释时，
真实报 `ABTB increment assignment missing (0,0,0)`；错误日志保留，不能把该辅助分析
冒称通过。后续离线脚本跳过的仅是旧赋值源码形状注释，用同一 native LCOV 算法完成
上述测量，未改 RTL、生产分析器或原始运行产物。没有给未覆盖点增加“结构不可达”豁免。
这些数据包含失败用例及注错控制的命中，只是测量，不签核功能点或覆盖闭环；runner
清理过的逐用例 raw 输入不可再逐份复查，现有合并字节与 manifest 仍可审计。

## 退出和残余

叶模块 seed2 的 `known-leaf-nonpass-attribution.json` 已逐 nodeid 保存第一处真实错误与
日志 hash，当前范围为14 FAIL/1 XFAIL，不能外推为最终完整 BPU 非 PASS 总数：

| 反例族 | 该批数量 | 当前核对边界 |
|---|---:|---|
| 同位置满组新分支计数污染 | 4 FAIL | fresh counter 期望2、实际1；与下项共用缺少原hit资格的方向路径，原对照不变 |
| foreign-tag 同位置方向污染 | 1 FAIL | 期望2、实际1；`MainBtbAlignBank.scala:320-330` 的原条件计数代码在两commit间逐字节相同，仍不核对 meta.rawHit |
| retained-owner 第二深度计数复位 | 1 FAIL | 原owner计数期望2、实际0；不将原提名way重命名成实际owner |
| 联合zero-key清理目的地 | 1 FAIL | 原应保留owner丢失、应清owner仍在；保留以前的归因及producer限制，不因节点同名就当独立重证根因 |
| retained-owner纠正请求缺失 | 2 FAIL | 所需owner3第二笔请求实际MISSING，ordinary/tag0各一条；未以缺样本次生错误掩盖第一错 |
| RAS PopAndPush | 4 FAIL | spec/recovery/两种commit见证；`Ras.scala:66-67,99-100,109-110` 译码在两commit间相同，仍仅识别isCall/isReturn |
| RAS enable行为（coverage功能体内） | 1 FAIL | 禁用后的top改变；是功能断言失败，不是仅覆盖百分比不满 |
| RAS已有strict XFAIL | 1 XFAIL | 独立保留，不计PASS，不凭本轮guard控制关闭 |

仅明确核过源码片段的条目给出该层根因信用，其余保留原诊断限制；这些都是模块/
有界预测合同反例，不能自动升级成完整 FTQ 或整机可达缺陷。最终仍以完整seed1的
实际节点、第一失败和独立producer依据逐项分类。

完整回归前冻结全部 Python/JSON 验证源码，运行期间不改；新结果目录、真实选择/seed、
源码/RTL/build/原生工具和覆盖产物分别审计。逐 nodeid 区分上游修复、模型滞后、旧缺陷
仍在和新待确认问题。仅端口表未变化的七个 DUT 仍必须执行，不继承旧 PASS。

原 MainBTB shared-service/retained owner/foreign-tag、RAS enable/PopAndPush 等失败
不自动关闭；short/entry/positive 及完整 FTQ 的原限制也不被本轮新增控制关闭。
公开 BPU target/perfMeta 仍被裁，本轮不改该投影或借内部 target 作公开输出验收。
适配交付、构建冒烟、功能判定、自检与覆盖各自说明；真实非 PASS 保留，不扩大 XFAIL。

## 交付审计清单（未完成项不计达成）

| 明确要求 | 当前证据 | 验收边界/待办 |
|---|---|---|
| 固定新旧基线、DefaultConfig、十 DUT 范围 | before/prepared/build-audit-ten/fixed-inputs；完整运行有效基线再次核对 | 无 RTL/配置/锁改动，不给未执行工程信用 |
| 十闭包、十新原生构建、独立冒烟 | 标准 build，逐 RTL/native 哈希与十 smoke 日志；full integrity-audit | 完整 SoC 缓存复用，不冒称空缓存新生成 |
| 第五槽严格 ABI、不可变来源、仅两字段训练投影 | 纯 red/green；两 physical alignment 功能及四 wire 注错共11 PASS，双 seed关键链和完整 seed1覆盖 | 不给不存在的第五槽 counter/attribute 训练字段补值 |
| 隐藏/暴露 VBTB、conditional NT、None 纠正 | 独立 producer、旧模型 red、七真实功能；完整 MainBTB seed1为171/9，叶seed2为166/9 | 九条旧 FAIL 与首错保留，叶seed2早于最后四项alignment补充 |
| 实际 guard、RAS 恢复、PHR/CommonHR 去 guard | RAS六项、Bpu两功能/截断wire控制；lookup preview red→修复；同源码双seed关键链 | 高guard端口压力不等于完整FTQ可达 |
| UID/epoch、背压/同拍/reset/disable/取消、有界收尾 | directed-v3/critical-seed2-v2各834 PASS；原33敏感链节点逐项保持 | 只签核既有有界链和新边界，不清除其他历史组合失败 |
| 原用例不静默删除、非 PASS 不豁免 | 42576→42632，新增56全部PASS、删除0、原顺序保持；waiver AST不变；全部1702非PASS穷尽分类 | 1691旧native重放节点0判定变化；未确认根因不伪称已解决 |
| 完整 BPU seed1、真实关键链 seed2 | full42632/2683native；critical同一834选择/真实seed2；manifest/覆盖/工具hash/隔离审计 | 真实1687FAIL/5ERROR/7SKIP/3XFAIL；首启动ERROR另列，不混算 |
| 合同、计划、差分、状态与机器索引 | 三合同增补、四新点/三开放残余；最终根268PASS/65.79秒，结构/资产/框架通过 | 严格事务门禁真实exit1（含BPU24项）保留，不称全仓事务适配完成 |

前文逐时记录中的“已安排”只代表当时启动或排队，后续真实结果另列，不据此重标失败
尝试。最终 `delivery-audit.json` 核对本清单到实际源码/运行/日志/链接/锁定配置；
未变的历史技术债和未证明的完整 FTQ 可达性不因本轮适配关闭。

三项持续开放的残余在 `verification_plan.json` 有 owner 与关闭动作：公开 target/perfMeta
消费观察、历史功能/验证债务、完整 producer/FTQ 可达性。覆盖缺口清单、旧 ABTB 覆盖
注释分析错误及无路径启动参数问题另外保留，均不宣称已修。未发布或推送，完整结果和
native/RTL只在忽略目录，Git交付仅为验证代码、合同、差分及简短证据索引。
