# RAW exclusive128：75例实际PASS、覆盖闭环及S3生产者准入纠正

**`lsq-raw-exclusive-06`实际75 PASS，452份启动/结束源全部一致。** 包含RAW叶子21例、
Replay叶子48例、保留53份真实RTL的Wrapper六例。不是LSQ整体验收，既有RAR、strict
disabled、SID、WB/zero/释放顺序普通FAIL不抵消，完整目标仍active。

## 1. 功能先行、原拒绝与窄域参考

先定义[RAW/容量Replay端点](../contracts/lsq-raw-exclusive-endpoint.md)：Load SQ是128个
较老Store之后的exclusive边界。RAW相对address-ready可领先128，不应漏记录、提前回收
或让cause10提前grant。保留127对照、三lane、跨SQ flags、56池新代身份与真实128 Store/
57 Load原义务；不是第129个Store，不一般性放宽半环年龄。

02先用原参考实际运行**63例27 PASS/36 FAIL**；全部36失败为RAW首查或Replay cause10
更新的半环ValueError，不计RTL反例，原件保留。新[显式opt-in参考](../../lsqverify/sq_endpoint/model.py)
仅接受Load-exclusive向前差128，并仅对Replay cause10扩展比较；shared参考、RTL、
knownness、比较mask和物理PA字节安全检查不变。普通`sq_after`仍拒绝半环。

[模型影响v3](../../results/lsq-raw-exclusive-02/exclusive-reference-impact-v3.json)核验精确
AST差异及256个通用半环拒绝；旧32份RAW/11301周期、131份Replay/20954周期在新旧
模型间pre/post和语义变化全部一致。**这是旧输入模型影响检查，不是新原生运行或独立
语义oracle**；不能扩到任意已落后128的Load、取消旧代等全局歧义域。

## 2. 绿色也会被拒绝：S3更新不是Replay完成

04实际63 PASS，但源门禁拦下六Wrapper的默认S3字段：alignedType应为3，last_beat取
PA bit6，无异常/别名的Replay应`updateAddrValid=0`。固定源码及新用例前合同见
[S3写回](../contracts/lsq-ldu-s3-writeback.md)。05只改这三项，重跑相同63节点仍全PASS；
六Wrapper所有公开before/after与04逐bit相等，说明严格RTL比较不能替代生产者准入。

[S3源关系审计](../../results/lsq-raw-exclusive-05/ldu-s3-source-audit-v1.json)进一步限定旧报告：

| 冻结流 | 实际S3 | 独立拒绝 | 原结果如何保留 |
|---|---:|---|---|
| `ldu-rar-routing-03` | 324 | size324、lastBeat177、明确aligned Replay更新6 | 18例15/3、原路由/UID/DA真实，但非完整正常生产者 |
| `ldu-mixed-02` | 438 | 明确aligned Replay更新171 | 原2/6及148取消同槽见证真实，仅接口效应PASS |
| `raw-exclusive-04` | 348 | size348、lastBeat168、Replay更新6 | 六Wrapper绿色被拒绝，旧63结果不改 |
| `raw-exclusive-05` | 348 | 本对齐cached hit/cause10域三项违例0 | 不追溯提升其他旧流或全混合域 |

旧mixed pipeline-v1误要求所有S3 update_address为真；旧审计保留，以上新证据优先限定
范围。这是**生产者功能关系/审计遗漏**，不是RTL新失败或仅少一种lane枚举。完整混合
的NC/MMIO、异常、别名及S4写回合并仍须按真实源码修复重跑。

## 3. 独立原UID与真实完成

[05历史v2](../../results/lsq-raw-exclusive-05/exclusive-history-audit-v2.json)和
[06扩展](../../results/lsq-raw-exclusive-06/exclusive-pool-audit-v1.json)仅用公开输入、原响应
和真实fire/credit，不读DUT/参考内部状态、actor结果或known-issue答案：

- RAW354原记录逐个产生原身份恢复后由地址前缀释放，其中345个exact128；378次延迟
  rollback、378次负查询。56池两代共六个满池epoch，第57条拒绝六次。无公开RAW slot，
  不虚构逐原UID→新UID物理槽映射；两代全56记录都逐个检查。
- 小Replay端点36原owner，504阻塞边沿，18次信用源/18次地址前缀源解除，36次真实
  grant与36次原slot反馈；重新rawFull不会锁回已解除owner。
- 六Wrapper各**128原Store+57原Load=185 UID**，共**1110 UID全部完成**。前56占RAW，
  第57真实拒绝、下一拍同lane cause10及revoke。只执行当前64窗口，首64片段消费/
  释放后才STA/STD第二窗口，ROB没有越过未执行Store。
- pool_credit三例tick898 grant、末STA tick900；address_prefix三例末STA tick1056、
  grant tick1068。Load反馈均先于第二64 Store的Sbuffer消费，没有人为“SQ必须空”；
  随后全部128 Store片段/SQ释放和57 Load/VLQ credit偿还。

57份早期叶子日志无nodeid，按完整公开输入signature/多重集合核对，不伪称逐pytest
映射；六Wrapper有精确nodeid。06保持旧63份完整raw历史，六Wrapper逐节点精确相等。

## 4. 剩余DA驱动12个满Replay池补例

05尚缺大量Replay slot/入口的exclusive blockSqIdx与选择情形。先定义
[120池合同](../contracts/lsq-raw-exclusive-pool.md)，再增12例：两个SQ起点、三入口、两
解除源；每例120个不同ROB/LQ/checkpoint一直等待，全部实际grant后逐原slot反馈释放，
不填池后reset替代。06实测12新增例/3816记录，**1440原owner=1440 grant=1440反馈**，
三个bank各480。它们是独立Replay外部RAW-full合同，不冒称Wrapper所有池联合满/CBO。

| 本独立端点自身DA | 02旧参考 | 05相同63例修正 | 06补到75例 | 旧命中丢失 |
|---|---:|---:|---:|---:|
| RAW闭包 | 2113/5139 | 4845/5139（+2732） | 4845/5139 | 0 |
| Replay闭包 | 13412/30500 | 13412/30500 | 27831/30500（+14419） | 0 |
| Wrapper闭包 | 25918/59602 | 32818/59602（+6900） | 32818/59602 | 0 |

[完整分类/精确增量](../../results/lsq-raw-exclusive-06/exclusive-coverage-audit-v1.json)及
[分类器v4](../../results/lsq-raw-exclusive-06/exclusive-coverage-classifier-v4.json)逐行保存
原文/上下文/既有功能映射，未跨DUT拼分子或删分母。剩RAW294、Replay2669、Wrapper
26784均保留；Wrapper本体5行是Uncache串行状态缺情形，不是不可达。Wrapper仍0/82
checked，不勾STRESS。既有功能缺少情形与S3整体生产者关系遗漏明确分开。

## 5. 失败、完整性与未完范围

01 collection导入路径错误，无原生功能结果，436源一致；02为27/36、438源；03为42
PASS/21 RAW fixture TypeError（额外coverage参数）、439源；04为63 PASS/441源但准入
拒绝；05为63 PASS/444源；06为75 PASS/452源。全部旧原件保留。模型审计v1/v2导入/
嵌套closure清单错误、历史v1 Wrapper schema错误，以及覆盖v1/v2/v3漏列RAW STA-RVC/
FTQ index/offset三拍变体的拒绝也保留，修正版未删行或放宽功能门禁。

[四负对照](../../results/lsq-raw-exclusive-06/exclusive-negative-controls-v1.json)拒绝size0、
错lastBeat、Replay伪更新和未解阻塞假grant；只是内存副本审计器测试，不是四次原生
DUT执行/RTL失败/新增功能覆盖。开源893e1580b tracked树干净，53原RTL及Wrapper副本
SHA一致，原146 shared参考文件冻结，见[完整性](../../results/lsq-raw-exclusive-06/rtl-reference-integrity-v1.json)。
未使用内部源码，验证工程未commit/push。

请求→证据对应：用例前行为合同→三新合同；真实分层UT→75个native artifact；实际检查
→原UID/slot/PA字节/副作用/credit及S3源门禁；覆盖缺口→全原DA分类与12补例重跑；
失败/边界→旧36参考FAIL、设施错误、旧普通RTL FAIL和新S3拒绝全部保留。未证明的正常
八类型全随机、联合容量/CBO分阶段、其余exact128/恢复及最终全请求审计仍未完成。

回归10尚未收到结束通知，**没有最终结果**。[430启动源核验](../../results/lsq-progress-regression-10/source-freeze-at-raw-exclusive06.json)
不是结束源/最终门禁，1908冻结范围不含本75例。后台结束会自动捕获源、coverage/v11，
不能报预期为实测。README/旧合同在其启动冻结集合内，本轮没有为同步索引破坏运行源；
结束后须补入S3纠正。目标active，不缩小到本75例。

```sh
python3 -B tools/run.py --name <新目录> --workers 4 -- tests/sq_endpoint --tb=short
python3 -B tools/audit_sq_exclusive_model_v3.py lsq-raw-exclusive-02
python3 -B tools/audit_sq_exclusive_history_v2.py lsq-raw-exclusive-05
python3 -B tools/audit_lsq_s3_source_v1.py
python3 -B tools/audit_sq_exclusive_pool_v1.py lsq-raw-exclusive-06
python3 -B tools/audit_sq_exclusive_coverage_v4.py lsq-raw-exclusive-06
python3 -B tools/audit_sq_exclusive_negative_v1.py
```
