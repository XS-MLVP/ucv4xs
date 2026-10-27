# 失败复核：不能把历史失败计数直接判成 RTL Bug 或误报

**结论：已检查所有保留的失败运行；旧的 17 次 FAIL 观测缺少逐节点日志与当时测试快照，无法逐一作确定性根因裁定。** 撤回旧交付报告“这些失败的根因都是验证侧错误”的笼统结论。本轮补充失败逐节点有日志、JUnit 和修正后复测。

这里“假阳性/误报”指验证环境错误地报告 DUT 失败，不把构建/收集失败当成 DUT 行为错误；“假阴性/漏报”指有错误行为但检查仍通过，见下一份报告。

## 1. 历史失败全清单

清单依据 `results/*/manifest.json` 全量枚举，不依据旧报告挑选。每份历史 manifest 的 SHA-256、日志是否存在及原始测试源码快照见 `review/failure_recheck_20261026/inventory.json`。其中 `before/` 是**本轮开始前**快照，不是历史失败当时的代码版本。

| 历史 run | 原始结果 | 原始证据能证明什么 | 本轮裁定 |
|---|---|---|---|
| `store-arbiter-initial-02` | 11 PASS / 11 FAIL | 测试有11次失败；无 nodeid/traceback | 旧阶段报告提到漏导入 `TAIL_GROUPS`、walking-one 多置位和负移位；**仅为历史文字归因，不足以逐节点确认** |
| `load-s3-initial-01` | 30 PASS / 1 FAIL | 1次测试失败；无 nodeid/traceback | **历史根因未决**；当前 S3 与独立异常/原因检查通过，不等于还原旧失败 |
| `new-load-unit-final-02` | 30 PASS / 1 FAIL | 1次测试失败；无 nodeid/traceback | **历史根因未决** |
| `new-load-unit-final-03` | 30 PASS / 1 FAIL | 1次测试失败；无 nodeid/traceback | **历史根因未决** |
| `new-load-unit-final-05` | 34 PASS / 3 FAIL | 3次测试失败；无 nodeid/traceback | **历史根因未决** |
| `store-delay-shared-ptr-01` | exit 2，state=incomplete | manifest 明确 `collection failed: tests/store_delay/test_store_delay.py`；native_inputs=0 | **收集/环境失败，不是已经进入 DUT 执行的功能失败**；不是凭此能确认的构建根因 |

前5项合计 **17 次 FAIL 观测**，不是17个不同 node、不是17个 RTL Bug；第6项不计入功能失败数。旧文字将其称为“构建失败”也过于具体，现改为有原始证据支持的“测试收集失败”。

`store-delay-initial-01` 实为14 PASS，`store-s3-initial-01` 实为17 PASS，不是失败运行，不拿它们做 Bug 证据。

## 2. 能重新验证什么，不能重新验证什么

当前代码的19 DUT已重跑，并有独立公开引脚检查与每 DUT 一组 readback 故障对照。但**当前 PASS 不能证明旧版本的每个 FAIL 都是假阳性**。缺少当时测试源码与 traceback 时，禁止按失败数编造逐节点归因，也禁止把参考模型对齐 RTL 后的通过当作 RTL 正确性的充分证据。

本轮唯一确认的 RTL 性能缺陷 `LSU-HWPF-MISS-001` 来自新的规范检查，属于旧检查器的漏报，不是强行给这17次历史失败中的某一次补标签。

## 3. 本轮新增失败逐项复核

| 记录 | 失败及原因 | 已执行的处理和复测 |
|---|---|---|
| `review/.../strict-parent-01.log/.xml` | 3 FAIL：2项被新增 schema 错误拒绝 `bypass2.bits.data`；1项测试写了无效 `replay.bits.accessType_pftType` | schema 补齐真实 data 输入；不支持的 replay 字段删去，后又替换为真实软件预取路径；严格父块/全套复测通过相关节点 |
| `review/.../sensitivity-01.log/.xml` | 4 FAIL：2项引用不存在的测试名；1项替换旧 `tail.mask` 引用但检查已转到 `tail_all.mask`；1项错误尝试替换只读 XData 属性 | 修正测试名、故障挂接点及观察代理；`sensitivity-02` **38 PASS**，最终回归再次通过38项 |
| `results/recheck-prefetch-spec-01/` | 1 PASS / 1 FAIL，RTL性能反例；但 native_inputs=0 | DUT 在测试体内由 factory 创建，自动发现未登记；修正 fixture 显式登记，`spec-02` 保留同一真实 FAIL，并有2个 native_inputs、原生覆盖数据库 |
| `results/failure-recheck-final-02/` | 581 PASS / 2 FAIL：1个性能事件真实 FAIL；1个本轮新增软件预取错误预期 | FU=1 在S0设置 noQuery，S1 的 tlbAccessResult=1，S2训练须 bit[1]=1，所以不能期望 train.valid=1；依据三段源码修正，`final-03` 仅余真实性能 FAIL |
| `spec-prefetch-01`、`recheck-prefetch-spec-02`、`final-01/02/03`及两组种子运行 | 同一个 hw-prefetch miss=1 实际0/预期1 | 不当作多个 Bug，不改参考掩盖，不使用 xfail/skip；保留普通 FAIL |

`sensitivity-01` 的“未抛 AssertionError”只证明当次故障没有挂到实际读取路径，**不是**据此又确认一个 RTL Bug。该问题与旧 S1 尾段身份完全未检查的反例不同，后者见 `03-false-negative-review.md`。

## 4. 新增软件预取误报为什么能排除

固定源码/RTL形成独立因果链：

- `NewLoadUnit.scala:208` 与 `rtl/new_load_unit/LoadUnitS0.sv:362`：`fuOpType==1` 设置 noQuery。
- `LoadUnitS1.sv:512`：noQuery 时 `tlbAccessResult=3'h1`，不因额外给一个 TLB response 就变成真实查询命中。
- `LoadUnitS2.sv:1118–1122`：训练要求 `tlbAccessResult[1]`。

因此新增的 train.valid=1 断言本身错误。更正后检查实际 `swInstrPrefetch.valid=1` 且 `prefetchTrain.valid=0`，不放宽硬件预取 miss 的独立断言。修正前失败 run 原样保留。

## 5. 证据保全修正

`tools/run.py` 现在保留 `console.log`、`junit.xml`、`run-provenance.json`（种子、命令、验证源码哈希、退出码）和原生覆盖，仍拒绝复用目录，不开正常运行波形或逐周期 dump。`conftest.py` 在托管运行中显式登记 factory 创建的 DUT，避免最小复现“执行过但覆盖采集为0”。

当时 `results/failure-recheck-final-03/` 为 **583项：582 PASS / 1 FAIL / 0 SKIP / 0 ERROR**（上游核查后当前为 `upstream-review-regression-02`：589项、582 PASS / 7 FAIL），19份原生覆盖数据库。按 JUnit 逐节点统计：普通测试523项（522 PASS / 1 FAIL），独立复核22 PASS，检查器敏感性对照38 PASS；不把这些对照并称为新增硬件功能点。

## 6. 保留的限制

- 无法补造已经没有保存的历史逐节点 traceback。恢复它们需要当时测试版本或外部日志；目前不具备。
- 本轮建立的是有边界的可靠性复核，不是对“所有可能误报/漏报已穷尽消除”的数学证明。
- 结果不能推广到外部 LSQ/DCache/TLB、其他配置、整核或新的上游提交。
