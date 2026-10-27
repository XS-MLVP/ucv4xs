# 原8种子全类型LDU混合：2个完整PASS、6个严格FAIL，原UID与边界独立核验

> **后续源复核限定，原结果不改**：两个PASS是真实接口/原UID效应，但固定LoadUnit
> 要求普通Replay不写回更新地址；本驱动171次明确aligned Replay仍updateAddrValid=1，
> 旧pipeline-v1还误将总为1当门禁。因此不是完整正常LDU准入，见
> [S3纠正与端点补例](lsq-raw-exclusive-20261019.md)。原2/6、148同槽见证及全部FAIL
> 保留，须全域修复重跑。

**`lsq-ldu-mixed-02`实际2 PASS / 6 FAIL，424份启动/结束源一致。** 保留原8种子、
八类型权重、sticky CBO、别名/Store split、SID真实resp后立即复用、错误、背压和恢复。
没有删失败流量，没有改目标RTL、参考或比较掩码。两个种子成功不等于八种子/STRESS验收。

## 1. 用例前合同与新驱动

[合同](../contracts/lsq-ldu-mixed.md)先于[驱动](../../tests/lsq_wrapper/ldu_mixed_owners.py)
和[测试](../../tests/lsq_wrapper/test_ldu_mixed.py)建立：固定S0/S1/S2/S3、NC首次与
NC/MMIO replay不同查询/dataValid、原STA-nuke与RAR flushAfter分离、matchInvalid
flush、Load head/tail S4及精确revoke。这是纠正遗漏/错误的生产者功能关系，不只是lane枚举。

单一绝对ROB/SQ/LQ/外部job账本保留；复用旧actor的是Store/总线效应核算，**不复用旧
Load规划器**。跨16B几何没有删除或只截低mask完成。固定LDU C_WF/C_MF为false，原
WAY_PREDICTION意图显式记录、不重抽、不伪造正常cause7；独立Replay接口cause7范围保留。

首轮`lsq-ldu-mixed-01`的8 FAIL全是新emit重复传tick的TypeError，**不是RTL失败**；
原424源/记录保留。02只删两处重复日志keyword，AST门禁证明其余代码一致，所有01
实际公开轨迹都是02相同节点精确前缀，不改旧结果或减少种子。

## 2. 实际执行与原UID效应

[独立审计](../../results/lsq-ldu-mixed-02/ldu-mixed-audit-v1.json)仅用公开dispatch、
input/pins/pre/post、原响应与真实fire/recover/dequeue，不读DUT/参考内部状态或actor
结果作语义答案。**3397条记录，746原UID = 359完成 + 374取消 + 13失败保留**。

- 111个总线接受（81 Load/30 Store）=111方向ack=111真实SID响应；外部待响应0。
- 73次原bypass消费，71次原错误随后进入S3；8笔已回未消费仍单列。
- 160次Replay grant/154次原slot反馈；取消/失败在途差额不伪造反馈。
- 66次shared恢复均核对两分支响应，137个原Store片段实际Sbuffer消费。
- 41 CBO owner/45次STA含retry，QB4/FFFF/wline/对齐与603实驱pin一致，NoSpec/BlockBack违例0。

| 种子 | 实际结果/终点 | 观察范围 |
|---|---|---|
| 28928 | FAIL，tick772 | 原Cache denied在valid、ready=false的WB保持阶段变0 |
| 28929 | **PASS，tick1416** | 600随机后fair/cleanup，150 UID=95完成+55取消，55取消者均同槽新UID完成 |
| 28930 | FAIL，tick248 | flush相位失配，仅停止前缀，不虚构随后zero/WB |
| 28931 | FAIL，tick866 | 原Cache denied/corrupt在valid、ready=false的WB保持阶段变0 |
| 28932 | FAIL，tick464 | 原Cache corrupt在valid、ready=false的WB保持阶段变0 |
| 28933 | **PASS，tick1418** | 600随机后fair/cleanup，158 UID=65完成+93取消，93取消者均同槽新UID完成 |
| 28934 | FAIL，tick816 | flush相位失配，仅停止前缀 |
| 28935 | FAIL，tick794 | UID104义务未完却实际SQ释放，不把该credit记成语义完成 |

两个PASS共**148组取消同物理槽新UID完成**，不是仅恢复指针、空队列或新请求。
其他失败前缀另有141组同槽完成，但85取消者仍无后续完成见证，全部保留。三个WB错误
是保持阶段，不虚构后来WB.fire；实际fire反例仍由孤立串行CBO定向证明。

## 3. 动态LDU合同及边界

独立门禁核对488次S0/S1 PA、444对S2 RAR/RAW、438次同lane下一拍S3/revoke，
**18次完整Load head/tail/S4撤销**、25次MMIO replay实际不发RAR/RAW、3次C_NK均绑定
真实STA。RAR flushAfter和matchInvalid flush按原ROB跟踪到共享恢复，不走旧错误路径。

这是Wrapper保留接口的**必要生产者合同检查**：DCache/TLB事件位不在本DUT，检查其
合法可见后果及静态映射，不冒称原生LoadUnit/DCache/Backend仿真。取消且身份尚未在
S2可见的17个ticket单列。两个PASS终点无活动pipeline ticket、原LDU rollback或待响应job。

## 4. 自身覆盖及缺口分类

本体114/114，53份闭包**38769/59602**；[逐行分类v2](../../results/lsq-ldu-mixed-02/ldu-mixed-coverage-audit-v2.json)
保存全部20833条原DA缺口的源/行/原文/上下文/已有功能映射，不删分母、不借旧317例或
叶子分子。主要缺口为Replay12580、VLQ3112、RAW1145、VSQ1064及RAR796等，属于既有
池容量、记录/入口、标签/选择、回绕和恢复的缺少情形。

相对旧串行混合，精确集合为新独有3872、旧独有1840、净+2032。生产者/随机交错已变，
**不宣称单调覆盖提升**；旧36737分子和8 FAIL不改。此前正常LDU定向的3335单调增量
仍是独立补例闭环。v1错误复用“RAR缺口全是uop写入”的假设，在行9172的matchMask
捕获路径拒绝；v1保留，v2明确映射既有coherence release情形，未删除行或放宽功能门禁。
本目录**0/82 checked**，不通过汇总追溯勾STRESS；完整八种子和联合容量尚未完成。

```sh
python3 -B tools/run.py --name <新目录> --workers 4 -- tests/lsq_wrapper/test_ldu_mixed.py --tb=short
python3 -B tools/capture_end_sources.py <新目录>
python3 -B tools/coverage_audit.py lsq-ldu-mixed-02
python3 -B tools/audit_lsq_ldu_mixed_v1.py lsq-ldu-mixed-02
python3 -B tools/audit_lsq_ldu_mixed_coverage_v2.py lsq-ldu-mixed-02
```

统一回归09已1882例1691/191及v10门禁，见[09报告](lsq-progress-regression-09-20261019.md)。
新增8例及正常LDU定向18例不在09冻结范围，须扩大新回归。合法联合容量/CBO分阶段、
RAW/Replay RAW_CAPACITY等exclusive128合同/最小例、其余恢复/fair及最终全请求审计仍必需。
