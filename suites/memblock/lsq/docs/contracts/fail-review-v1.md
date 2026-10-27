# FAIL复核合同：先判证据，不把红色改成绿色

本合同先于新复核探针。用户要求复核真实问题和误报；本轮不继续覆盖补例目标，
不修改固定`893e1580b705d81f113c30c7a05734e09a08050e` RTL/Chisel、旧参考、
旧fixture或旧测试，不恢复/重设已取消的目标。只新建短复现和独立分类证据。

## 判定对象与分类

以当前实际JUnit为准：统一2330节点/227FAIL，最新九build1765节点/196FAIL；
分别保存，不跨范围比较失败数量。问题登记表只是检索索引，不能充当oracle。
每个失败按“首次违约→相同根因候选→复核证据”归类，随机停止后的未执行阶段
不作为新bug，父级/多lane重复也不重复计算独立bug。

- `RTL_INTERFACE_CONFIRMED`：合法的模块接口历史，在已定义输出/真实握手时违约，
  独立可观察检查复现、必要条件对照通过，且固定源/生成件能解释机制。
- `VERIFICATION_ERROR_CONFIRMED`：能指出错误的激励/相位/参考规则，并通过独立
  依据证明它错误；不得仅因为改了预期后通过就归为误报。
- `PRODUCER_DOMAIN_BOUNDARY`：单元接口观察真实，但普通producer不能或尚不能产生
  该历史；不可升级为完整核bug，也不可删除原接口FAIL。
- `UNRESOLVED`：证据不足、最小化未完成或合法性/契约存在争议。不是默认误报。

另列`integrated_reachability`与`architecture_consequence`，不把单元接口确认等同
完整Backend/ISA确认。部分历史逐拍数据已按保留政策清理；旧SHA不是现存轨迹，
需要补证时只新跑代表用例，保存compact事件和失败，不重建完整历史或全量波形。

## 首批行为义务（探针前定义）

| ID | 微架构语义和检查 |
|---|---|
| FR-SID | A的总线请求实际被接受、绑定SID、响应返回后，A的数据尚未被消费；B合法重用外部已归还SID，不得改变A后续有效bypass的原数据/错误。不同SID及A先消费是必要条件对照。 |
| FR-WB | 一个真实接受的CBO Cache响应携带的denied/corrupt属于原head；writeBack背压提前建立，等待期间以及最终实际fire均须保留错误。不比较valid=0载荷。立即消费和三拍背压对照。 |
| FR-RAR | 年轻cacheable Load得到数据时，与当前/前一拍同line release建立关联；随后老Load同PA查询应发现冲突。固定配置距离0/1/2/3、dataValid真假成对比较，区分漏报与保守过期重放，后者单独不能证明ISA错误。 |
| FR-STRICT | 原strict Load等待SQ7且没有执行wakeup/连续ready指针越过时，单独ready位不能放行；任意valid=0 feedback字段不应改变其有效输出。三lane、指向活动/其他slot、ready位真假对照；正确解除后真实grant/原slot反馈释放。 |
| FR-DOMAIN | VSQ dispatch+redirect、MMIO pending跨未完成项、Forward孔洞mask分别审普通producer域。单元接口FAIL保留，不把所有边界一律归为RTL错误或误报。 |
| FR-ORACLE | 复核异步reset采样、无效输出payload、PA/beat宽等验证侧假设；把历史误报和当前227FAIL分开，不能用历史修正冒充当前FAIL已消除。 |

新探针直接用Picker真实DUT和X Reactor时钟/监视器，不使用旧领域模型提供预期，
不读内部状态选择刺激。可复用纯类型/编码适配，但必须核验实际输入pin集合。
LQU规范化VA/fullVA、mask、FTQ结束半字；Replay为普通LD、8B对齐、不刷任意opcode。
lastBeat使用固定256bit总线→32B拍→PA[5]；不复用已撤回的PA[6]来源推导。

首批四build各自保存native产物；只报告本次探针覆盖，不回填任何完整回归分子。
复核探针可以在固定、有界的单个事务内记录多个失配，再统一报普通FAIL，以观测
实际消费；每个失配都保留，不能吞掉/转为PASS，也不宣称它是一般全输出参考。

## 工作顺序与交付

1. 冻结旧JUnit、manifest、四索引、问题登记和旧验证源码聚合指纹，建立逐FAIL库存。
2. 新四build短复现及正反对照；输出仅compact协议事件、断言结果、原件SHA。
3. 对照固定git对象与原生成RTL，复核参数、valid门控、真实握手、错误传播和域。
4. 输出`FAIL→候选根因→实际复核→结论/置信度→剩余证明`台账和中文报告。
5. 审核旧产物/源码保持、无skip/xfail/RTL修改；未审定节点继续UNRESOLVED。

本轮不先做整轮回归或追逐覆盖率；完成首批不代表全部227/196FAIL审定，更不代表
完整LSQ验收。icache方法可借鉴，xfail做法和叶子覆盖替代父级的做法不移植。
