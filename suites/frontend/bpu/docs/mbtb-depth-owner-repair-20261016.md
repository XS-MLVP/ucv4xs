# MainBTB保留深度：记录归属与可定义观察

依据MBTB-025既有“保留深度不改变原分支owner”要求，本阶段先补明确义务、
再改参考/用例，不改RTL。旧辅助模型将两个请求way的方向都设为2，并拒绝
非弱或命中邻居；这描述请求侧实现，却不足以验证逻辑记录归属。

## 要求与观察边界

1. 两个不同键正常占用同一保留owner的前后服务深度。后键的完整目标修正
   必须落在它自己的保留版本，不能因请求way变化而改变owner或污染前键。
2. 后键同窗口若有独立、有效且已学到非弱值的条件分支，该邻居的计数、方向、
   目标和身份保持。这里明确补入“两键/第二深度+有效非弱邻居”的组合义务；
   不能用旧弱值2恰好不变或拒绝该前态获得假PASS。当前与陈旧metadata分别
   作为控制和判别上下文，不是bank/set/way枚举。
3. `prediction.valid=0`的payload不作架构golden，但valid本身始终比较。
   `rawHit=0`的counter/位置/属性也不是该来源的有效义务；rawHit仍始终比较。
   若分支仅被窗口过滤而rawHit=1，其完整metadata仍是训练来源，必须检查，
不能因为预测valid=0就把有效计数抹掉。
4. 只在旧depth用例的公共结果比较引入这一定义投影，不改通用`frozen_check`、
   全量独立MbtbReference、实际请求/服务、原生shadow深度或known-FAIL检查。
   预期在冻结时复制；实际错误不得回填参考，异常要包含原要求与观察状态。

自定义消费者比较只增加约束，不能绕过同拍被动独立模型已捕获的第一处错误。
agent应先传递并标记该错误，避免它在用例失败后又被teardown重复抛成ERROR；
不放宽JUnit唯一性门禁，也不清除未观察到的后台失败。

## 判别设计（本文件先于实现）

| 义务 | 前态与判别 | 应观察什么 |
| --- | --- | --- |
| 不从request way发明方向初态 | 保留间接owner方向2，邻槽不命中，分别给两种请求次序 | 只改保留记录目标/初态，未知邻payload不被人为改成taken/2；两个源快照不可变 |
| 有效非弱邻居完整保持 | 原保留间接分支旁有负条件0/1或强正3 | 参考接受该前态并保留全部邻居字段，而非拒绝输入或重置邻居 |
| 过滤不等于无来源 | 邻分支prediction无效但rawHit=1 | 其counter/位置/属性损坏必须普通失败 |
| 无效数据不升级为功能 | 两边valid/rawHit均0，裸payload任意改变 | 忽略裸payload，但任何valid/rawHit翻转、有效邻居字段改变仍立即失败 |
| 真实第二深度归属 | 两个真实间接键先正常服务，后键保留在第二深度；后键同窗口条件邻居老化至0 | 实际shadow前态按独立计划核对，fresh来源纠正应PASS；真实旧cold来源提名另一way后，仍需保留后键owner及负邻居 |

真实末次反馈保留可执行顺序：较早条件not-taken，较晚间接taken且目标需纠正。
陈旧来源来自第一次真实cold读取，不伪造counter、rawHit或way。两份分配在
最小四笔普通读取中重叠，读取数量用于实际占用资源，不是等待固定周期判成功。

纯比较须有错目标、错方向、错计数、错属性/位置、错valid/rawHit、参考被外部
修改等负对照。DUT只用正常driver训练和已有只读memory-direct monitor观察，
不写内部状态、不fabricate metadata、不用固定周期或任务编排掩盖服务。

## 旧反例的真实归属

以`production-byte-address-20261016-v1/feature-points.json`与当前源码为准：

- **MBTB-027**：`test_unhit_feedback_preserves_foreign_tag_direction`，同位置
  未命中反馈普通FAIL，另一位置控制PASS。
- **MBTB-028**：`test_coalesced_entry_reset_preserves_negative_conditional_peer`
  的stale-metadata普通FAIL，current控制PASS；集成Main服务也有同类普通FAIL。
- **MBTB-029**：`test_duplicate_clear_owns_destination_not_zero_payload_key`
  的联合零键普通FAIL，非零控制PASS。

前轮审查稿把025的非弱邻居反例指到027，是追踪文字错误；保留其历史来源，
当前以028作保留owner反例，同时保留027/029全部检查，绝不通过ID调整清掉FAIL。

旧测试名称中的“initializes request counters”和“rejects nonweak neighbor”
与修正后的要求相反，将明确更名/替换对应纯规则，保留迁移记录；这不是删除
真实RTL反例。MBTB-025新组合义务若FAIL，按普通失败报告，不继承旧弱态PASS。

## 实现与已完成的专项（不等于全量验收）

逻辑效果在 `model/depth.py::expected_depth_target_state`：只修改第二键保留
间接记录的完整目标及其方向初态。旧两次请求程序另验证两种物理提名各一次，
再调用这一效果；新单次纠正不伪造两次请求来满足旧辅助函数的参数。
公共前态由独立 `MbtbReference` 持续检查，局部快照只是额外保持检查，不能
播种或同步完整模型。`checker/depth.py` 只忽略无定义payload；通用比较和
完整模型不放宽。纯负对照保留有效字段、过滤命中的metadata和冻结期望损坏。

`case/depth_owner.py` 正常驱动两个真实键、负条件伙伴和末次合法完整反馈。
独立编码预期在发送前冻结；monitor核对实际反馈、提名、保留服务及只读
shadow深度。pytest入口只有语义参数和场景调用，没有边沿、get/set、任务编排。
新 `depth-owner.reached/checked` 各两个语义bin；旧96个depth交叉bin仍记录，
但不能代替新的非弱邻居义务，因此计划单列旧组为历史覆盖。

修正前的7项参考判别全部FAIL；修正后的首批514项纯检查全PASS。最终专项
`mbtb-depth-final-pure-20261016-v2` 是 **849项纯检查+1项已有DUT流水契约，
850 PASS**，不是850个新功能或纯模型测试。1项DUT来自既有
`test_pipeline_contract.py`，其原生789/1056只是该专项集合的命中，不是全量
丢失，也不是纯模型测试产生的DUT覆盖。

首次第二深度试点有重复teardown ERROR，JUnit唯一性门禁正确拒绝提交完整
测试判定（`tests=null`）；它仅保留诊断，不作资格或覆盖增量证据。原因是
自定义期望绕过了后台已捕获的独立错误。agent现在先传递并标记第一错误，
既不清除错误，也不以自定义断言或teardown重复覆盖它。三项纯负对照检查
第一异常身份、未调用后续比较、错误未清除及普通比较仍有效；JUnit门禁未改。

修正后的 `mbtb-second-depth-owner-checked-20261016-v1` 完整记录12节点：
**8 PASS /4普通FAIL，无ERROR/SKIP/XFAIL**，来源冻结不变、覆盖提交完成。
新fresh控制通过，真实旧cold用例失败，旧027/028/029的三个FAIL与三个控制
保持。新组reached=100%、checked=50%：说明两种前提均到达，只有fresh
完成完整比较，不是说功能点通过率50%。新失败期望peer=0、间接owner=2，
实际peer=2、owner=0，两个分支方向也随之错误。记录目标/服务正确不豁免方向。

显式节点迁移（原参数和值均保留）如下，资格比较必须应用映射而非称原名全同：

- `test_shadow_depth.py`：`test_depth_one_retains_owner_and_initializes_request_counters`
  → `test_depth_one_retains_record_owner_and_defined_neighbor_state`（1节点）。
- `test_depth_model.py`：`test_request_counters_and_retained_entry_are_independent`
  → `test_request_way_does_not_redefine_retained_entry_or_unmatched_payload`（16节点）。
- 同文件：`test_nonweak_or_matched_opposite_way_is_rejected`
  → `test_neighbor_presentation_does_not_need_a_weak_counter_or_empty_hit`（3节点）；
  原规则与合法非弱邻居要求相反，现比较完整保持，不再拒绝该前态。

完整[生产复验](../results/production-depth-owner-20261016-v1/qualification.json)现已
完成：19025项，18996 PASS/26普通FAIL/3 strict XFAIL，64进程owner605.15秒。
旧18983判定经上述20节点更名映射保持；新增40纯检查PASS，新2DUT各PASS/FAIL。
仅025从PASS变FAIL，硬件点313 PASS/18 FAIL/2 XFAIL，环境10 PASS。
367功能组/335满，旧365组比例不变，新reached100/checked50；不是验收通过。
十DUT原生命中集合与分母均无增减，17372零键及49组职责关联保持。
2171冻结源码与所有21项覆盖产物核验，提交及worker回收完成，正式报告不改。
未更改RTL、DUT或SDK，未扩bank/set坐标，未授权的RTL修复仍不进行。

### 失败原因定位（不替用户修RTL）

`MainBtbAlignBank.scala:259` 的条件方向匹配仅要求位置相同，未要求来源
rawHit/条件身份；真实旧cold的两way位置均为0，可被合法较早not-taken分支
同时选中。`MainBtbAlignBank.scala:264` 又以请求的 `t1_entryWayMask`
决定方向初始化，而记录缓冲可将相同完整键合并到原保留owner。
`MainBtbInternalBank.scala:122` 的entry缓冲与128行的独立方向队列不会自动
替彼此重定向所有权。新场景的实际完整输入和提名/服务分别确认了这两个边界。

| 分支 | 本应发生 | 实际消费者 |
| --- | --- | --- |
| 较早条件peer0 | 既有负计数0保持，目标/身份保持 | 请求提名way0触发初始化为2，方向误变taken |
| 第二深度间接owner1 | 完整目标更新，计数保持规定初态2 | 记录目标在owner1正确更新，但旧cold位置0使其计数变0，方向误变not-taken |

这与027未匹配资格及028初始化owner分别相关；025补充的是真实第二深度
和非弱有效邻居组合，不重复登记两个新ID。实际第一处差异包含完整独立状态、
期望/实际计数、方向和完整记录，普通FAIL直接交给pytest。功能检查能发现
同一已执行赋值落到错误身份，故不能只看“行是否命中”判断此要求已满足。
