# DeqModule阶段报告：真实写出credit与CBO错误丢失

## 当前状态

**两类严格失败未验收，接续真实PSQ。** 已按用例前合同建立61输入/55输出适配、被动完整引脚历史、公开分阶段参考和PSQ外部代理，保留真实EnterSbufferQueue。旧定向probe保留，不将Python代理等同真实PSQ；不得以本体及闭包DA满提前验收。

| 运行 | 结果 | 本体DA | 真实两文件闭包DA | checked |
|---|---:|---:|---:|---:|
| `deq-initial-01` | 13 PASS/3 FAIL | 34/46 | 101/124 | 17/44 |
| `deq-fault-consumption-01` | 13 PASS/6 FAIL | 单独故障补例轮 | 未用于闭包验收 | 未用于整体验收 |
| `deq-expanded-01` | 22 PASS/6 FAIL | 46/46 | 124/124 | 25/44 |
| `deq-lifecycle-calibration-01` | 10 PASS | 34/46 | 子集校准，不替代全量 | 16/44 |
| `deq-lifecycle-expanded-01` | 57 PASS/13 FAIL | 46/46 | 124/124 | 42/44 |
| `deq-lifecycle-expanded-02` | 71 PASS/14 FAIL | 46/46 | 124/124 | 44/46 |
| `deq-lifecycle-expanded-03` | **71 PASS/18 FAIL** | **46/46** | **124/124** | **44/46** |

原样构建/原生实例化走钟PASS：`results/builds/20261018T094224992374Z-deq_module/report.json`。本体SHA为`bdc38e317b1abbb6425441fd3081622d6203cab56b7ff17203a51c83e9555946`。静态codec/独立公开解码核验256样本、8个非法拒绝，见`results/deq-codec-static-01/static-audit.json`；它不是功能通过。

## 已执行的功能与逐行闭环

[用例前合同](../contracts/deq-module.md)先定义15组行为及合法域；无redirect/WFI/ROB许可输入，不虚构删除的Uncache错误/ID响应字段。rdata读取移动和SQ完成credit分开，真实下级Sbuffer输出fire才贡献普通store credit。

首轮实际检查单/双cacheable store、字节偏移、背压和压紧、同页跨16B与非连续第二页、一个split store只得一次credit、forceWrite的60/55滞回、CBO flush与Cache请求/响应、回写身份与错误。

`audit_deq_initial.py`独立重建211条公开记录、280个有效字节观察、10个真实Sbuffer fire与8个SQ credit（split两段只一credit），并核对全部显式检查journal。此审计明确仅首轮定向范围。

首轮未覆盖的本体12行（422、424～426、428～430、432～434、436～437）属于合同已定义但整条尚未实现的NC/MMIO用例路径，不是未定义的新功能；真实下级11行（131～136、155～159）属于奇数尾位置的保存/复用情形。全部23行分类另存`deq-initial-01/line-audit-classified.json`，原needs_review文件不覆盖。

随后补memory/device NC、PBMT/device IO、两种64位数据半部、请求背压、idResp方向正反、NC确认与最终PSQ消费分离、MMIO实际resp/WB以及下级先单项消费再双入的奇数尾位置；9个新增正常用例全部通过，真实闭包提升到124/124，无行排除。

## DEQ-WB-001：错误在实际writeBack消费前丢失

Cache响应的denied/corrupt先正确出现在writeBack和exceptionInfo。writeBack.ready保持0一个周期后，异常7/19即变0，而valid仍为1。源码`NewStoreQueue.scala:1082-1095`在writeback状态无条件清错误寄存器，并未等fire；原SV395～415一致。

保留原3个等待期间失败，另加3个**真正ready/valid消费**的用例，分别denied、corrupt、两者同时。后者保持同一合法已提交CBO head、Cache真实req/resp握手，等待后令ready=1；实际`writeBack.valid=1 && ready=1`、`rdataPtrMoveCnt=1`时错误位仍为0。避免仅凭对Decoupled稳定性的过强假设判断故障。四个无等待错误组合及一个无错误等待对照、原单元字节流程仍运行，没有改RTL、xfail或放宽预期。

`audit_deq_faults.py`不导入参考模型，独立核对已接受Cache响应、head保持、等待与三个实际WB fire，见`deq-expanded-01/fault-audit.json`。这是独立Deq合法接口背压证据；真实PSQ/SQ/LSQ组合可达性与架构后果仍未运行复现，不扩大结论。

## 生命周期参考、覆盖补例与独立审计

原剩19项中18项已补真实完成检查：5种长度×16偏移、满池及同拍出入、CBO四类/zero信用、inactive单/双/混合、队列活动/Cache响应/Uncache响应/WB等待reset、SQ四圈和ROB former/latter、高位VA零扩展、跨line及完整UQ双flag等。`DeqModel`按原字节地址与有序两项账本检查所有有效输出；`PsqAgent`分开维护rdata读取和deq释放，不能以接受代替完成。

首轮新参考错把split的两个片段当两个SQ读取位，造成3个随机moveCnt假失败；依据1334–1345校正后加2个split后接inactive的正常完成对照，旧首轮实现/失败快照不重写。另复核1548/1619纠正validCnt来自虚拟enq-deq，增加0..128全部129值原生滞回检查；早期codec拒绝65是合同错误，`audit_deq_codec_v2.py`补4个域外拒绝，保留v1及其历史产物。

完整混合随机4种子保留，1种子400 UID公平排空通过，3种子触发下面的新wline失败；另4个不含zero的必要条件对照各400 UID排空通过，单列新bin，不取代原随机。

独立`audit_deq_lifecycle.py`不导入参考，审计结果`deq-lifecycle-expanded-03/lifecycle-audit.json`：

- 9746条连续公开记录，3035 UID=2835实际完成+4 reset中止+196失败停留；未把停留或reset当通过。
- 2547次Sbuffer实际消费，452次WB、220次NC确认，14次zero写出；44622个有效字节观察。
- 全部256 SQ编码、274个ROB完整身份；4次reset后同物理槽新UID完成见证。
- 201份启动源码结束SHA、原生artifact/build哈希一致；44/46 checked，未通过held与zero_neighbor。

## DEQ-SPLIT-WLINE-001：尾段错误继承相邻zero整line控制

随机首先发现普通跨16B头store的尾段`wline=1`，而其地址/data/mask仍来自普通头store；源`NewStoreQueue.scala:1272`按每lane原ctrl/data生成wline，第二lane在split复用时却没有改用head的控制。相邻CBO.zero即使未committed仍会污染尾段。

加入相邻inval/clean/flush的6个正常完成对照、2个zero已/未committed最小失败，以及4个**真实Sbuffer fire**失败（无等待/3拍背压×已/未committed）。实际消费时普通8B头store尾段mask0xF/data0x88776655/正确PA，唯独wline=1而严格应0。9个普通失败保留，不掩掉整line控制。此项是原逐字节检查之外遗漏的控制所有权功能，新增语义点而非伪造DA缺行；原44项分母不改，新目录46项单列。

仅证明独立Deq接口和外部PSQ代理流量反例；真实PSQ/StoreQueue/上游CBO发射约束尚需实际验证，不能声称已证实架构整line破坏。保持严格失败，继续真实PSQ，原9个WB错误同样不豁免。

## 下一层与未完成范围

Deq未通过的两项阻止叶子验收，但不阻止真实PSQ的其他有意义验证。PSQ必须保留真实ForwardModule/DeqModule/UnalignQueue，检查真实STA/STD→控制/数据→写出/转发/完成，以及两个Deq反例的父级可达性；WFI端口已优化删除/常真不能伪造动态覆盖。StoreQueue、LoadQueue与LsqWrapper仍完整待验证。

1075例/33DUT回归04不含本目录，不追溯混入Deq新增失败；未来加入Deq应新增回归版本和门禁，旧证据保持不变。
# 新增：真实父级许可域与回归06（旧证据不重写）

最新92例为**67 PASS/25 FAIL、47 reached/43 checked、闭包124/124**，见
`results/lsq-progress-regression-06/lifecycle-audit-v2.json`。6246公开记录、2452 UID
=1990完成+4reset+458失败保留，全部4旧槽由新UID完成；WB9、wline7、zero2、
完成顺序7有独立公开历史反例。旧89例的代理曾在read!=head时压制特殊committed，
其通过数不能代表真实PSQ全部许可域。已移除此过窄限制；新参考的post-edge旧
窗口相位误报另行纠正，回归05及旧89例快照/审计器全部保留。详见
[回归06](lsq-progress-regression-06-20261018.md)，本模块仍未验收。
