> 迁移前历史说明。当前命令与基线见仓库根 README；以下记录不代表重建版本验收。

# Kunminghu-v3 BPU 验证

使用 picker memory-direct DUT、xreactor 组件和 pytest；完整回归默认多进程并行。

生产入口按“纯控制＋10种DUT”分域调用 xreactor 托管 runner：收集阶段不加载
DUT，执行进程从启动到退出只归属一种DUT；`Finish()` 不代表卸载原生库。
同一种DUT可分给多个worker，`--workers` 是整轮worker总预算，不是每种DUT各用一份。
原生覆盖率由 xreactor 合并并回收输入；功能覆盖通过公开 `CoverageDatabase` 合并。
每个有功能覆盖的域保留一份最终数据库供汇总，不导出逐case或逐周期轨迹。
参见[跨10 DUT串并行验收](results/dut-isolated-production-promotion-20261018-v1/qualification-analysis.json)
与[根生产入口确认](results/dut-isolated-production-promotion-20261018-v1/root-confirmation.json)。

框架使用 xreactor `dev/coverage-v2` 的固定提交，配套 xcomm ABI 3 / coverage 协议 5。
首次运行前参见[依赖安装与迁移说明](docs/xreactor-coverage-v2-migration.md)，旧 ABI 1 DUT 不能混用。

```sh
python3 tests/run_all.py
python3 tests/run_all.py --select tests/tage/testcase
python3 tests/run_all.py --workers=8 --select tests/framework
```

实现位于 `bpuverify/<dut>/<role>/`，公共设施位于 `bpuverify/common/`；
pytest 入口位于 `tests/<dut>/`。

跨DUT回归请使用上述生产入口；直接 `pytest tests/ -n ...` 不提供相同的进程归属保证。
当前完整集合为22343项，**尚无新源码全量结论**；本轮全量输出位于
`results/production-owned-state-semantics-20261018-v1/`。功能点总量与合同以
`verification_plan.json` 为准，历史文档和旧报告不代表当前源码已通过。

- [四类身份与版本语义的正式目录资格](results/owned-state-production-promotion-20261018-v3/qualification-analysis.json)：16个新增DUT场景闭合178项比较义务，串并行574项均为570 PASS／1原FAIL／3 strict XFAIL；另613项完整覆盖门禁控制通过。默认生产集合保留全部旧用例，不增加功能点ID，不枚举bank/set。
- [最近一次旧源码21181项完整诊断](results/production-semantic-lifetimes-20261018-v1/exit.json)：21115 PASS／63 FAIL／3 strict XFAIL；原始判定保留，不用后续定向结果改写
- [历史20209项完整诊断](results/production-confidence-boundary-20261017-v1/README.md)：20169 PASS／37 FAIL／3 XFAIL；6个新DUT程序和47项纯检查，只跑一次全量，原20156判定保持。四个程序闭合76项义务，另两项为原训练历史资格失败，不直接称RTL缺陷；459组／411满，BPU新增1个Main替换行、十DUT无旧命中损失
- [置信度饱和往返与来源存活](docs/tage-confidence-boundaries-20261017.md)：逐笔完整结果、19次实际服务、48个消费者、68笔Main更新接纳和46次历史比较；稳定历史不替代原taken长来源反例
- [前一20156项完整诊断](results/production-direction-turnaround-20261017-v1/README.md)：20118 PASS／35 FAIL／3 XFAIL；6个新DUT场景和50项纯检查，只跑一次全量，原20100判定保持。新增3个原饱和来源漏学习场景使INT-086转FAIL，不扩大XFAIL；447组／403满，十DUT原生集合不变
- [相反方向迟到学习语义及异常](docs/tage-direction-turnaround-20261017.md)：正确旧预测在当前计数改变后回学，三对照闭合45项义务、14次实际服务和36个消费者；三个原饱和场景保留普通FAIL，区分UT合同和FTQ可达性
- [前一20100项完整诊断](results/production-loop-iteration-20261017-v1/README.md)：20065 PASS／32 FAIL／3 XFAIL；6个新DUT场景和59项纯检查，定向验证后只跑一次全量，原20035项判定保持。独立IMLI来源及真实S3修正完成45项配对义务，435组／397满；原生行集合未增长、未回退
- [循环迭代来源与恢复语义](docs/loop-iteration-source-ownership-20261017.md)：年轻255不能污染旧16，四类分支结果及饱和恢复，另用正常Main/TAGE分歧验证真实末级修正和准确的新消费者
- [前一20035项完整诊断](results/production-mixed-visibility-20261017-v1/README.md)：20000 PASS／32 FAIL／3 XFAIL；4个新DUT场景和44项纯检查，622项定向PASS后只跑一次全量。新增7个原生行键、旧命中无损失，423组／385满；两处旧纯断言修复已纳入本次完整验收，原硬件判定保持
- [部分服务后的混合版本语义](docs/tage-mixed-visibility-learning-20261017.md)：48项配对义务、20次实际SDK服务及48个四阶段消费者，区分重新激活、饱和抑制与不同数量服务
- [前一19987项完整诊断](results/production-residency-batch-20261017-v1/README.md)：5个新DUT场景与80项纯检查，新增5个原生行键，415组／377满；该轮原始34 FAIL保留，不用后续专项改写其版本
- [失驻身份与异序服务语义](docs/tage-partial-residency-cases-20261017.md)：新增INT-098，细化INT-089与INT-086；41项配对义务、10次SDK服务和30个消费者闭合
- [前一19902项完整诊断](results/production-common-recovery-20261017-v1/README.md)：4种恢复语义、24项配对义务，405组／367满；十DUT原生命中集合无增无损，原32普通FAIL及3XFAIL保留
- [目录与组件职责](docs/repository-layout.md)
- [UT 语义参考模型与验收缺口](docs/semantic-reference-models.md)
- [事务架构](docs/transaction-architecture.md)与 [Scoreboard 设计](docs/scoreboard-design.md)
- [生产并行入口与验收进展](docs/pytest-parallel-migration-20261009.md)
- [功能点清单](docs/functional-points.md)
- [功能点分域、事件定义与证据缺口](docs/verification-point-semantics.md)
- [从原生行缺口审查功能事件](docs/functional-event-review-20261016.md)
- [缺失要求补全、测试设计及最新替换年龄验证](docs/coverage-gap-completion-20261016.md)
- [UTAGE 替换保护事件要求](docs/utage-usefulness-event-review-20261016.md)与[验证证据](results/utage-usefulness-events-20261016-v1/README.md)
- [UTAGE 旧功能点语义定义与来源边界](docs/utage-functional-definition-review-20261016.md)
- [请求/保存快照场景设计](docs/utage-source-ownership-scenarios-20261016.md)与[阶段证据](results/utage-source-ownership-20261016-v1/README.md)
- [BPU MicroTAGE 来源与并发义务](docs/bpu-microtage-functional-review-20261016.md)及[SC/TAGE/RAS 保留身份合同](docs/retained-state-functional-review-20261016.md)
- [BPU 剩余缺口的来源合同](docs/bpu-gap-owner-functional-review-20261016.md)：当前全部43个缺口关联ID都有明确合同，证据缺口另行保留
- [TAGE 全部36点语义](docs/tage-functional-definition-review-20261016.md)与[SC 全部23点语义](docs/sc-functional-definition-review-20261016.md)：区分方向/保护/偏好/权重/阈值及未闭合边界
- [ITTAGE 19点](docs/ittage-functional-definition-review-20261016.md)、[MicroRAS 16点](docs/micro-ras-functional-definition-review-20261016.md)与[RAS 17点](docs/ras-functional-definition-review-20261016.md)：目标身份、调用年龄、退休/信用和证据范围
- [MicroBTB 17点](docs/micro-btb-functional-definition-review-20261016.md)与[MainBTB 30点](docs/main-btb-functional-definition-review-20261016.md)：可靠性、分支版本、服务/方向及地址适配问题
- [AheadBTB 53点](docs/ahead-btb-functional-definition-review-20261016.md)：保存窗口年龄、分阶段旁带、学习资格及有界服务；九UT的236点均已定义
- [BPU基础64点审查](docs/bpu-integrated-functional-definition-review-20261016.md)：记录基础333个硬件点的语义合同；[定义后的用例顺序](docs/semantic-gap-test-design-20261016.md)先修可信基线，再补效果和消费者
- [完整目标参考与XFAIL范围修复](results/full-target-oracle-repair-20261016-v1/README.md)：纯模型先复现6项漏检，再修参考；DUT的两项已知高位缺陷仍XFAIL，不改RTL
- [MicroBTB字节地址域修复](results/ubtb-byte-address-repair-20261016-v1/README.md)：成套codec/monitor/区域参考、BPU单次复用及六类真实消费者；[18983项完整诊断](results/production-byte-address-20261016-v1/README.md)完成，原25普通FAIL保留
- [产物策略](docs/artifact-policy.md)
- [DUT 构建](docs/dut-rebuild.md)

局部测试通过不等于全量验收通过，功能覆盖率不等于功能点通过率。
