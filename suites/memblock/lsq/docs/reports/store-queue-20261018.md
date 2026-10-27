# StoreQueue：真实VSQ/PSQ闭环验证与未验收项

## 结论

**已完成首轮、两次逐行补例、完整公开阶段参考/外部UID代理及独立历史审计，仍NOT_PASS。** 最新`sq-expanded-03`为**79例55 PASS/24 FAIL、51 reached/43 checked**；本体26/26、真实七文件闭包8968/8968 DA。八项严格失败语义保留，不将本体连接层行满或子块通过当作父级验收。

原样Picker构建/实例化/走钟：`results/builds/20261018T120338587691Z-store_queue/report.json`，StoreQueue SHA `de7c7b075e7b557cc0fb874d34f4b1c593144efe0093b402647e239a0501578e`；182实际输入、338输出，真实VSQ/PSQ及Forward/Deq/ESB/UQ全部保留。用例前[合同](../contracts/store-queue.md)定义虚拟uop与物理flow分离、真实ROB许可、释放反馈、恢复与字节来源，不直驱隐藏committed或内部VSQ指针。

## 覆盖闭环

| 运行 | 原生结果 | 本体DA | 七文件闭包DA | 功能checked |
|---|---:|---:|---:|---:|
| sq-initial-01 | 9 PASS | 26/26 | 5504/8968 | 11/50 |
| sq-expanded-01 | 44 PASS/22 FAIL | 26/26 | 8716/8968 | 36/51 |
| sq-expanded-02 | 55 PASS/24 FAIL | 26/26 | 8968/8968 | 43/51，取消绑定仍过宽 |
| sq-expanded-03 | **55 PASS/24 FAIL** | **26/26** | **8968/8968** | **43/51，v2绑定已核验** |

首轮3464条缺口逐source/line分类：VSQ1822、PSQ1601、Deq12、ESB11、Forward3、UQ15，均为合同既有功能的缺失情形，无行排除。第二轮余252条是PSQ246（高槽/另一STA lane CBO保存）和VSQ6（lane4/6为最后有效dispatch的tail选择），再经128个逐head CBO、64slot×两STA lane和稀疏dispatch真实WB/zero写/完成补齐。

补例还包括：物理64项×四代完成；8虚拟uop×16flow占用128并公平排空；全部size×16偏移；真实跨line/非连续第二页及分段消费不早credit；ready洞/TLB重试、三lane youngest/wait/kill/deq窗口；普通先退休但物理仍驻留；异常取消、release/walk、跨flags恢复和合法前拍dispatch在途取消。参考用旧状态建立双向连接后同时推进，不偷用一方新状态作同拍旁路。

## 独立完成证据

`sq-expanded-03/lifecycle-audit.json`和`reuse-audit-v2.json`核验：

- **7114**条连续公开记录；**6552**条完整阶段参考记录（6537条完整检查、15条严格失败停点）；575个定向比较；253份启动源结束SHA一致和全部artifact/build哈希通过。
- 外部actor部分独立重放**1556 flow UID=1259完成+10取消+4 reset中止+1错误提前释放+282失败保留**，不把提前释放UID算正常完成。1436虚拟uop与flow分列。
- 1295次实际Sbuffer fire、82次WB、40次Cache请求、66次Uncache请求、22次NC确认、19次UQ接受。统计仅为actor重放范围，不混入其他probe。
- 另有128个全槽CBO owner实际完成：96次Cache req/resp、128次WB、32次自己的zero写；再另有首批16个普通flow和24个forward响应的独立raw replay，不重复计数。
- **全部10个取消UID及4个reset UID都有同物理槽新UID实际完成**。被取消UQ的slot1/old UID2由同槽new UID4经真实新第二页接受(tick58)并完成(tick70)。旧expanded-02只有7/10绑定，保留旧结果，不能用“新任意事务”替代。

审计范围诚实分列：所有公开历史/比较和失败都审计，但并非每个定向probe都有第二套UID模型；actual VSQ/PSQ是原生RTL，审计/actor不读内部寄存器。DA满不意味着分支/表达式/任意配置或形式穷尽。

## 七类失败与更高层边界

| 问题 | 本层失败数 | 实际证据 |
|---|---:|---|
| FWD-ALIAS-001 | 3 | 三lane经真实dispatch/STA/STD返回更老PA字节，无重放 |
| FWD-RANGE-001 | 6 | 两段×三lane mask标记无store来源的字节 |
| FWD-SQID-001 | 4 | 三个最小裁剪身份及一个完整域随机 |
| DEQ-WB-001 | 3 | 真正Cache req/resp后，实际WB fire丢错误7/19 |
| DEQ-SPLIT-WLINE-001 | 3 | 两个实际尾段fire、一个随机valid污染；普通执行完成后ROB才前进到zero头并发射zero |
| DEQ-ZERO-001 | 1 | 旧普通项驻留下级，真实ROB头zero自己的零写0次却实际WB并释放/全空 |
| DEQ-FINISH-ORDER-001 | 4 | 三类NC/IO最小反例旧普通项消费0次却释放；一个随机提前credit |

新FINISH-ORDER来自`NewStoreQueue.scala:1318-1324`无年龄身份的finish/credit求和。源码1301注释声称特殊项rdata==deq，但真实PSQ与VSQ并不保证它；旧Deq外部代理曾额外强制该条件而漏掉问题，现已收紧参考并移除过窄刺激限制，需新统一回归验证，不改写旧89例或旧1075例回归04。

八项未checked为`SQ-CONCURRENT.seeded`、`SQ-CREDIT.special_order`、`SQ-FORWARD.alias/clipped/range`和`SQ-SPECIAL.error_held/split_wline/zero_owner`，均有真实FAIL；一个240 UID必要条件随机完整排空通过，另一个仍因完成顺序失败，不缩小完整域来通过。

以上已证明**真实StoreQueue公开边界**可达，不再只是外部VSQ代理。但完整LSQ、LoadUnit、Backend的发行/仲裁/恢复约束和体系结构后果仍待上级验证，不能提前声称系统整line破坏或全部接口可达。原始RTL/Chisel未改，问题表不作oracle或豁免，无xfail/skip，未commit/push。

## 后续

保留本层八项未验收语义；先运行包含共享Deq参考域纠正的新版本统一回归并审计，再推进真实LoadQueue及LsqWrapper，不以局部失败把完整目标标unmet或删减组合层。
