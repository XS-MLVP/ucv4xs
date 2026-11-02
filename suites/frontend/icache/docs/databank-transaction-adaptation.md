# DataBank 事务适配检查点（2026-11-02，未闭合）

适用于完整香山 `public-893e1580b` / DefaultConfig 的 `ICacheDataBank`。
这是当前全仓目标中的逐 DUT 工作，不改写旧 SRAM 覆盖报告或完整 ICache 判定。

## 已实施的输入／快照边界

- 从真实生成端口及 `ICacheDataBank.scala` 的独立四路 SRAM 合同核对：256 set、四 way，
  每 way 数据 64 bit、code 1 bit；读地址为每 way 各一份，现有 `read(set)` 请求全部四路。
- `BankWrite` / `BankRead` 在接触 driver 前拒绝非法类型、负数、超宽值；不依赖 XData
  截断或 model 在输入已经驱动之后才报错。零 waymask 是合法无写入 beat，未禁用。
- `BankReadData` 要求完整四路数据／code，脱离调用方 list 并冻结为 tuple。
- 当前原生 agent 拒绝与固定 DefaultConfig 不符的 `sets` / `ways`；纯
  `DataBankModel` 仍可使用不同几何，不能把纯模型参数当作真实 DUT 配置。

19 条修前纯控制失败（非法域被接受、响应保留可变容器引用），两个合法／已有拒绝控制
通过。修后同一 21 条全部通过，另加六条 agent 预驱动拒绝／几何控制；仓内 27 项及原
21 项合计 48 PASS。均为环境 selftest，不计新增硬件功能点。详见
[机器记录](../../../../docs/history/transaction-goal-icache-databank-domains-20261102.json)。

## 首响应检查点

真实原生探针保留前一个 set 的不同数据，再观察下一次读：rise-write 输入在 tick536
可见，完整新数据在 tick538 响应点出现；这与 `SRAMTemplate(latency=1)` 相符。旧
`read()` 会丢弃第一次错误 sample，随后值相等就返回。该原生错误注入修前为
`DID NOT RAISE AssertionError`，不是 setup 问题。

现 `read()` 在原生发射后的合同响应边界只取样一次，不访问 model 来选择结束时刻。
合法对照保留全部原 13 个原生功能（含 BIST 和既有随机样本）；新增 data/code 首次错误
与“响应选择禁止访问 oracle”三个原生自检。同源码 seed1/seed2 各 **43 PASS**（16 个
原生输入、27 纯控制），source `039192e01de19c493a80e4fadb930820bf2b348c025cf6da3545d15a0ff059f5`，
源码稳定且审计匹配，产物/processor/六个构建文件 hash 核验、构建未改。原40项无删除/
判定变化。原外部首响应错误与相位探针修后亦为2 PASS。

## 持续事务、存储来源与真实阶段

当前生产不再把比较放在可选的`check_read()`里。`read()`和`check_read()`都自动检查；
两个SDK `SamplingMonitor(delivery='lossless', capacity=64)`冻结完整沿前/沿后frame，
checker连续消费并核对相邻tick，无论功能体是否读取返回值。SDK尚无非消费快照/逐沿
跨通道合同检查，故工程只补不可变观察缓存和领域账本，不新建传输/队列框架。

| 事件 | 本机rise-write源对应时窗 | 信用 |
|---|---|---|
| 输入发射 | rising `t`，从驱动前`BankCycle`建立UID | 不是硬件tag；相同payload也不合并 |
| 功能物理消费 | rising `t+2`，使用沿前ready和保存的上一rising输入 | 与本拍新offer分开 |
| 功能响应 | 同一消费边界`t+2`的SRAM完整输出 | 只比较有效way，精确单次样本，不按oracle挑沿 |
| MBIST ack | `t+2` | 仅注册req，不是读响应 |
| MBIST宏操作 | `t+4` | 区分功能fire与被MBIST覆盖的有效写 |
| MBIST完整66-bit读回 | `t+6` | 另按输入UID、选择历史、时窗检查 |

沿前的XData**输入**getter已可看到本次排队意图，不是上一拍RTL消费的输入。两相分别
比较当前计划与实际发射，物理消费身份来自保存的上一rising；沿前**输出**ready才用于
消费判断。曾把两拍输入直接相等当不变量，导致reset setup失败，原12 FAIL/35 ERROR/
27 PASS保留；该guard修正不是放宽硬件合同。关闭采样器或漏沿仍必须失败。

`BankPortRead`完整支持每way独立地址和零mask，`BankCycle`表示单沿offer及同拍读写/
MBIST组合；便利`read/write`串行等待ready，不能用它们的正常完成掩盖显式cycle被拒绝。
`geometry`是固定的物理256×4，不是转发可变oracle状态。功能用例已移除driver/raw dict、
私有edge和`agent.model`，原功能场景/地址/随机数/判定保留。

独立`BankStorage`保存全部66位和每cell的期望输入祖先；功能写是`data<<2|code<<1`，
MBIST可保存包括pad bit0的任意66位。BIST来源由其真实输入消费建立，功能测试不再手改
model。来源是独立期望历史，不冒充wire标签或芯片上游生产者证明。

Single-port的共享MBIST地址实际为`addr_rd[7:0]`，`addr`作为双端口写地址在本宏不适用，
仍完整观测/校验；9-bit地址高位别名合法。依据是独立Scala `SRAMTemplate.ramWaddr`的
singlePort分支和256-row几何，不从返回数据反推。通用`MbitsStandardInterface`注释与该
明确分支不符，不能仅据注释登记新RTL缺陷或禁止两个地址不同。`SramInfo(way=1)`明确
不使用byte mask，故`be=0`的whole-word写合法，控制保留。

连续req每个有效沿有独立UID。注册的select可使先前读结果不再被输出mux选择；只按
明确输入选择历史记`bist-result-unselected`，不凭相同word把它配给新UID。功能ready/fire
也可能被已注册MBIST宏命令覆盖，记`mbist-overridden`而不伪造有效存储祖先。原13功能
用例的BIST读回、全way广播和随机66位数据继续执行。

## 所有权与严格收尾

read/write/MBIST及28个SRAM控制位通过SDK LevelDriver持有，reset通过既有ResetDriver；
共49个非clock输入，不遗漏metadata裁掉的真实addr叶。独立固定ABI校验防止模型/绑定
一起缩错宽度。共享closed-send修复的旧完整327 PASS/3 XFAIL、seed1选测103 PASS/1 XFAIL
保留其源码；随后reset检查点双seed各58 PASS也不重标为后续完整源码。

reset取消真实未完成身份，不改写已经完成的历史；reset-issued仅表示控制日程执行，
不表示宏清扫完毕。`finish()`只在输入已撤销后有界等待自主清扫/管线尾部，核对所有UID
终态和真实比较delivery。它不驱动idle/reset、不补回复清债；仍held的offer在推进任何
tick前失败。`aclose()`只是cleanup；根fixture在正文PASS/缺报告时严格finish，已报告
FAIL/SKIP只cleanup。同错不重复报teardownERROR，独立清理错仍传播。

生产v4完整ICache **401 PASS/3 XFAIL**、同源码seed1选测 **177 PASS/1 XFAIL**，
source`6a5d865...`稳定/逐文件匹配，66/18构建文件和所有产物/processor hash已核验。
旧330项及相对顺序/判定保持，新74项均selftest（包括前次9个reset控制）；DataBank123项
为47 native用例/76纯控制，两条原首错控制各带新独立合法执行，共49 native实例。
原8条运行时red同探针修后8 PASS。实际pytest async-yield/report桥接9控制也通过，不能
用fake资源控制冒领native信用。完整证据见
[持续账本机器记录](../../../../docs/history/transaction-goal-icache-databank-continuous-20261102.json)。

后续v5又补连续不同array相同word、功能fire被MBIST覆盖、ack后reset及三类错MBIST
输入无readback控制，定向22 native PASS、新6项PASS；该v5随后正式完整为
**407 PASS/3 XFAIL**、同源码seed1 DataBank全选 **129 PASS**（53 native用例/76纯控制、
55 native实例），source`4003a071...`，源码/产物/构建已审计，旧项及判定保持。v4更宽
seed1选测仍是前一源码收据，不能拼成v5同源码完整ICache双seed。

随后补的首沿前取消控制揭露新收尾问题：若已经登记read/reset计划但在发射前取消，旧
finish只检查已观察的wire为空，仍先走4/2tick执行了取消计划后才失败。两条原生red在
“finish不得推进任何tick”断言失败，非setup/RTL错误。现额外在首个drain时钟前拒绝
未发射计划及reset日程，不清账/补idle取绿；原22控制和新2控制同源码24 native PASS，
source`11cbc636...`随后取得完整v6 **409 PASS/3 XFAIL**、同源码seed1 DataBank
**131 PASS**（55 native用例/76纯控制、57 native实例）。源码稳定/逐文件匹配、全部
产物和66/6构建文件hash已审计，旧330/410项及相对顺序/判定保持；新2取消控制PASS。
两次回归均已完成，不使用v5数字冒领当前源码。

## 后续协作检查点：非零控制与逐 row 清扫

上述v6完整结果保留原源码意义。之后与MetaBank共用`runtime/array_agent.py`的SDK
装配/生命周期，仍由各DUT的checker/model承担真实领域语义。新增完整严格SRAM控制事务、
持续控制来源和非零hold/bypass等适用性检查；真实native反证发现并修正了停止唯一consumer
仍可finish成功、用本拍释放预览处理上一写入，以及reset时模型瞬时清零的适配问题。
hold只抑制宏写、不抑制握手；reset按声明的自主row清扫更新来源，持有的row可保留旧值。
已知位mask明确区分未初始化内容，不从实际返回值补oracle。

具体依据、阶段与DFT模拟边界见
[MetaBank/SRAM控制合同](metabank-transaction-adaptation.md)。两DUT当前协作收尾定向
305 PASS、原功能项判定保持；完整ICache和同源码第二seed数字见
[协作检查点](../../../../docs/collaboration-checkpoint-20261102.md)，不将v6结果重标为当前源码。

## 仍须继续

- 非零DFT事务、hold/reset/MBIST和模拟宏不适用输入已有生产接入与对照，但不声称硅片
  DFT/timing功能已全验；后续完整API/调度组合仍需系统审计。
- 进一步并发、取消/采样生命周期和最终全仓有序收集仍必需；静态DataBank
  owner命中清零不替代语义审计。MetaBank迁移后，整个ICache其他DUT仍有327处基础设施耦合。

其他十个 ICache DUT 及其他工程仍在全仓范围；本检查点不声称配置、生命周期或覆盖闭环
已经全部完成。保留所有原功能用例、随机种子和 XFAIL，不缩窄合法激励以取得绿色。
