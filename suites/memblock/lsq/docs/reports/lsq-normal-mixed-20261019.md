# 完整八类型混合：源关系与外部job账本复核

**整体仍为NOT_PASS，未关闭目标。** 本轮按原种子`0x7100..0x7107`、八类型及权重
`(30,12,3,2,36,6,4,7)`运行，每例请求600随机拍，再公平排空/取消同槽新UID完成。
真实原生DUT仍是固定53文件LsqWrapper，不改RTL、149共享参考或旧失败。详细合同见
[`lsq-normal-mixed-source-jobs.md`](../contracts/lsq-normal-mixed-source-jobs.md)。

## 为什么还要新驱动

旧绿色流或旧接口FAIL不能直接充作正常源验收：

1. 普通Load/Store/CBO的`hyper`按UID翻转，并非来自HLV/HSV指令；新profile固定0。
2. 同VA页随机标PBMT-NC/IO/cached而无SFENCE/权限变化历史；新PBMT页分开，但保留
   原PA和cached/Store别名字节冲突，不按失败地址过滤。
3. Cache miss可能被更高Replay原因或fullForward遮蔽；外部请求仍须回包。新增按
   64B line/16个MSHR与VPN/16个hint标签的独立在途所有权，不用UID低位凑身份。
4. S4的Replay cause优先与MSHR来源不同：后者看完整head cause向量的C_DM位，不能
   只看最后one-hot是不是C_DM。新驱动和独立checker分别重建。
5. TLB id/full在S2取自过滤器；`full`还含返回撞拍，不是S0后永远不变的容量标志。
   本轮保留早hint，不用人为延迟回包来回避这个源关系。

独立checker只用事先声明的指令/外部事实和实际公开I/O，不导入控制器的cause/WB
答案、不读DUT或参考私有状态。原全输出fixture仍每拍执行；新增有界失败单边沿
仅供诊断，不是放宽参考的协议探针。

## 已实际结束的运行

| 运行 | 实测结果 | 原生记录 | 启动/结束源 | 自身原DA |
|---|---:|---:|---:|---:|
| `lsq-normal-mixed-source-01` | 0 PASS / 8 FAIL | 6166 | 538一致 | 31245/59602 |
| `lsq-normal-mixed-source-02` | 1 PASS / 7 FAIL | 23981 | 538一致 | 35384/59602 |
| `lsq-normal-mixed-source-03` | 2 PASS / 6 FAIL | 2710 | 541一致 | 36925/59602 |
| `lsq-normal-mixed-source-04` | 2 PASS / 6 FAIL | 4597 | 542一致 | 39695/59602 |

01的恢复后阶段、已释放后ROB取消和重复ROB代际记账有检查器错误；原FAIL原件保留，
未当作RTL缺陷。02只纠正检查器记账并增加有界现场；原8种子和源选择没有重抽，
精确DA新增**4139行、旧命中丢失0**。其中仅seed28929实际完成600随机/公平及旧的
结构释放级复用检查（非fault正常替代门禁是后来新增，见UID-v2拒绝），不能把其余
首失败前缀计成完整程序。

02的7个FAIL已分域：

- 28930/28931/28932：真实CBO Cache corrupt后，WB异常19和Store异常信息19为0而
  参考要求1。原普通全输出FAIL保留，不因修源字段屏蔽。
- 28928/28933/28934/28935：各5000公平拍后有C_TM owner未重放。保留的job历史表明
  对应hint已真实归还；代理却仍使用S0捕获的full=0。固定NewLoadUnit1170-1171、
  Repeater290-291和LQR916-925解释了S2过滤器撞拍的遗漏；尚不当作RTL活性缺陷。

03按同一完整范围重跑S2投影后实际2/6，23个早返回窗口得到独立核对，四个代理
超时全部消失；17个TLB job/hint与14个Cache job/refill实际归零。最新六个FAIL为：
五个CBO denied/corrupt到WB异常7/19丢失，另seed28935在老普通Store仍未Sbuffer
消费时，CBO.zero被老lane0 fire提前推进flush。这与已存在的严格zero-old-buffer
最小例一致：DeqModule388-390用任意lane0 fire推进writeZero，而不是该原CBO的
真实zero16传输；不是要求老Sbuffer必须先空的理由。

03两个原生绿色种子虽均执行完600随机/公平，**UID-v2门禁仍拒绝**：28929有4个、
28933有3个取消槽，只找到异常WB/结构释放的新UID，没有普通完成见证。异常释放
不是普通成功，因此严格终态准入为0，不改写其原生2/6。04仅在原随机之后补强
正常同槽新UID清理，并增加CBO原Cache请求/响应与原字节消费的紧凑见证；保留原
600拍、全部外部早返回和六个严格FAIL前缀，实际结果见下述04核验。

03相对02的自身原DA为**新增2061、丢失520，净增1541**。正常源时序改变了随机
进程，不能把它写成“旧命中0丢失”或把两轮分子相加。22677剩行逐项CSV分类。
Cache/TLB源账本另有2个纯Python支持用例实际通过，不计native LSQ通过数或原生DA。

04已实际结束并通过UID-v2门禁，原生仍为2/6，两个通过种子为28929和28933。它们
原600拍/公平程序之后补200个正常清理UID，合计441个UID分别为：

| 互斥终态 | 原UID数 |
|---|---:|
| 正常LSQ完成 | 327 |
| 正常LSQ完成后被ROB取消 | 6 |
| 异常WB且真正ROB头trap | 12 |
| 异常WB后被其他恢复取消 | 1 |
| 结构取消 | 95 |

95个结构取消UID全部有非fault新UID同物理槽实际完成见证，不再把异常释放当正常
替代。六个原FAIL的完整实际input/pre/post/check流SHA与03全部相等；控制器原11个
方法、149共享参考和继承源共212文件一致，仅新增随机后清理方法。对两个PASS，
核验原UID前缀和未改动的源方法；**没有冒称保存了或观察到逐拍前缀SHA**。

04全部八例实际源检查包括23个S2早hint窗口、17个TLB job/hint、14个Load Cache
job/refill、80笔Uncache请求/真实返回，以及28笔CBO Cache请求/响应。五个真实
zero16和166个普通Store片段按原PA/mask/字节消费另计，不把CBO Cache job和Load
Cache MSHR job混成同一身份。仍保留五个WB错误和一个zero归属FAIL，未过滤错误
响应或增加“老Sbuffer先空”限制。首次vector-QB源路由仍有55个包单列未证明。

04相对03自身原DA**新增2770、丢失0**：VLQ1194、VSQ714、PSQ455、RAR271、RAR
CAM50、RAR FreeList86。19907剩行逐条分类；这200个清理UID及覆盖增量是已有
正常同槽复用关系的缺情形补充，不是以窄绿色流替代六个失败种子。

## 可复核证据与逐行缺口

四个已结束目录均有：

- `pytest.xml`、命令、冻结`verification-source/`和`end-source-check.json`；
- 每例`normal-mixed-summary.json`、实际完整检查流SHA、必要有界失败现场；
- `normal-mixed-summary-audit-v1.json`：真实结果、请求连续窗口、UID/job守恒交叉核验；
- `normal-mixed-uncovered-v1.csv`及`normal-mixed-coverage-audit-v1.json`：每条原
  source/line绑定理由字典和功能点，不复制大量重复source上下文。

03另保留`normal-mixed-UID-audit-v2.json`的实际非零退出拒绝，明确原生PASS不自动
通过普通终态/正常同槽复用审计；v1的结构释放计数仍原样保留为较窄历史。

01剩28357行、02剩24218行、03剩22677行、04剩19907行均已逐项分类为已有功能的具体slot/lane/cause/release/
flow/宽度/恢复情形；不把未覆盖自动判不可达。普通元信息、外部Cache/TLB所有权与
精确ROB头恢复是**跨块整关系**，与这些保存/选择情形分开说明；仅有合同或失败前缀
不代表它们已完全验证。原59602分母保持，不并入历史59595、S4/local-reset或叶子分子。

收整后只保留04为当前原生基线；01..03的三个大native.dat已实际删除
**246486930字节，未归档**。其FAIL/JUnit/源/摘要/UID拒绝/LCOV/CSV均保持，163份
元数据SHA复核未变。04的唯一native压缩为1715108字节；四份大line-audit原
33057175字节压缩为719449字节。清理后已实际临时展开并重跑04语义、UID及自身DA
三门禁，全部exit0，临时副本0遗留；没有再归档每轮全部原件。

审计点`results/`唯一分配866037760字节（约825.9MiB），磁盘可用400414130176字节。
索引为`results/lsq-normal-mixed-source-04-storage-v1.json`。01..03原artifact门禁
依赖已删除的native，不能直接重跑并声称原件仍在；需要时按冻结源/种子重新运行。

04按需复核命令（第二条比较需要一并展开03的大行报告，不需要其已删除native）：

```sh
python3 -B tools/lsq_evidence_archive_v1.py audit lsq-normal-mixed-source-04 -- python3 -B tools/audit_lsq_normal_mixed_uids_v2.py lsq-normal-mixed-source-04
python3 -B tools/lsq_evidence_archive_v1.py audit lsq-normal-mixed-source-04 lsq-normal-mixed-source-03 -- python3 -B tools/audit_lsq_normal_mixed_coverage_v1.py lsq-normal-mixed-source-04 --prior lsq-normal-mixed-source-03
```

## 明确不越界的结论

- 旧size4首次输入的`isvec/vecWen`与当前NewLoadUnit scalar首次入口路由尚未闭环，
  **正常上游准入未证明**。这些原16B用例未删除、未改成8B；其接口结果及独立检查
  保留，报告单独计数。不能因种子PASS就声称完整正常producer已验收。
- Store Uncache方向生成端口只保留ack/resp.valid，不保留该方向denied/corrupt；
  不拿共享Load错误pin冒充Store错误传播。CBO真实Cache错误pin继续严格检查。
- 新目录原82功能点注册表仍为**0/82 checked**，新增源关系/UID检查另列，不冒填
  整表。最终完整统一回归、其他128/旧代、late-ack/serial-local-reset及全请求审计
  仍必需，所有历史FAIL均保留。
- 默认**0逐拍JSON、0波形**，运行时检查不减少。SHA是完整检查流摘要，不是未保存
  新raw的离线逐拍重放证明；不再每轮归档全部覆盖中间物。

## 扩大统一回归的保留方式

实际collection为2312节点：原2203全部保留，新增精确S4 84、本地reset 15、原混合
8和纯源账本2；collection不计为运行结果。最初包含全量源路径/哈希清单的启动
命令被工具审查拒绝，**未执行、没有启动回归13**。后续改为`tools/run_summary.py`
摘要入口，只记录源码数量和启动/结束聚合指纹，不创建全量新源码副本或逐文件
清单；全量native/语义/FAIL/覆盖范围不变。新v15门禁核对旧基线及真实结果，不再
要求或伪造新`source-evidence.json`/`end-source-check.json`。结果仍须等待实际结束。
