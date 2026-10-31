# S4精确ROB头恢复：84 PASS、5592 UID与原DA新增22888

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


**结论：本轮补齐所声明普通LD profile的精确异常恢复和Cache job闭环，并完成实际
代际覆盖迭代；不是整个LSQ通过，也不替代原八类型随机/所有普通FAIL。**

## 先定义源关系，再实际运行

合同：[异常WB/结构释放/ROB头trap](../contracts/lsq-s4-precise-rob-head.md)、
[稳定TLB情况域](../contracts/lsq-s4-precise-cases.md)、
[两段Cache job义务](../contracts/lsq-s4-cache-obligations.md)、
[真实代际和miss后异常](../contracts/lsq-s4-precise-epochs.md)。

旧“年轻fault WB后马上flushSelf”遗漏的是**完整较老前缀→ROB头精确trap关系**；
遗漏tail miss实际回包则是另一个外部所有权关系，不是只少几个bit组合。新程序：

1. 派发较老Store、blocker Load、S4目标、真实年轻Load；同lane的head/tail各有实际
   S0 Forward、S1 PA、S2 RAR/RAW和正确S3/S4 revoke，普通operation6/hyper0/nonleaf0。
2. head/tail PF或AF按源码分别推导异常优先、WB与Replay、fullva/gpaddr和MSHR。
   稳定同4KiB页PF一致；不同PF权限只用跨页。准确S3 DCache错误配置关闭，不伪造。
3. 没有WB时，先偿还每个真实选择的Cache miss job，实际grant/原slot反馈后才WB；
   tail/无关MSHR9真实回包不能解除head MSHR3。外部prefetch job明示为边界假设。
4. 实际执行较老Store STA/STD/S2、blocker S0→S3并完成，再把pending停在fault ROB，
   此时才flushSelf。老Store已经退休但未被Sbuffer消费合法，不加SQ必须先空的限制。
5. fault已释放LQ时不伪称被取消；仍有Replay时才计其结构取消。年轻victim和fault
   trap分列，每个真正取消槽的新UID必须同物理槽正常完成，老Store原字节必须消费。

## 首轮→检查器修正→真实代际补例

| 运行目录 | 实际结果 | 自身DA（原分母59602） | 核验范围 |
|---|---:|---:|---|
| `lsq-s4-precise-01` | 61 PASS / 5 FAIL | 26994 | 66定向，5个无效payload检查器错误原件保留 |
| `lsq-s4-precise-02` | 72 PASS | 26994 | 原66 + both-miss6，源/Cache job闭环；DA新增0/丢失0 |
| `lsq-s4-precise-03` | 84 PASS | 49882 | 保留72 + miss/tail-fault9 + 三条360真实程序流 |

01五个失败先确认Forward valid=0，又错误要求无效mask=0；仅把payload断言限制到
valid1后重跑，不修改DUT、公共比较mask或旧FAIL。02/03的149份`lsqverify/`文件与
回归12冻结版全部一致。03有515份启动/结束源一致，全部native/build产物SHA已核。
固定53份原RTL SHA一致，开源HEAD为893e1580b且tracked树干净；未修改目标RTL。

03的实际命令：

```sh
python3 -B tools/run.py --name lsq-s4-precise-03 --workers 4 -- \
  tests/lsq_wrapper/test_ldu_s4_precise.py tests/lsq_wrapper/test_ldu_s4_precise_epochs.py --tb=short
python3 -B tools/capture_end_sources.py lsq-s4-precise-03
python3 -B tools/coverage_audit.py lsq-s4-precise-03
python3 -B tools/audit_lsq_s4_precise_summary_v3.py lsq-s4-precise-03
python3 -B tools/audit_lsq_s4_precise_coverage_v2.py lsq-s4-precise-03
```

## 独立在线检查和可核对终态

[v3门禁](../../results/lsq-s4-precise-03/s4-precise-summary-audit-v3.json)核验：

| 实际关系 | 数量 |
|---|---:|
| 完整程序（含三条360长流） | 1161 |
| Native采样 / 独立checker程序请求 | 67044 / 66120 |
| S4 join / 真实S2查询对 | 2967 / 5934 |
| 原UID | 5592 = 3966普通完成 + 813异常WB并ROB头trap + 813纯年轻取消 |
| 真正结构取消槽→新UID正常完成见证 | 942 |
| 原Replay grant / 原slot反馈 | 516 / 516 |
| 原Cache job / 真实refill | 474 / 474 |
| 外部独立prefetch假设job / 真实refill | 213 / 213 |
| tail或无关refill未解除原head miss | 300 |
| 老Store实际Sbuffer消费 / SQ释放 | 1161 / 1161 |

每条长流连续360程序，不reset、不预置指针；真实Store到SQ360、LQ到1082、ROB绝对
序到3610。两笔真实aligned filler改变3步进余数，目标实际覆盖全部240 LQ编码与
256 SQ编码，三种lane轮换都真实执行。不是所有ROB码的所有功能覆盖声明。

checker不读DUT内部或model答案；逐请求窗口first/last tick及+2连续性核对。每个
case在fixture启动10样本之外还有首dispatch前1个自主idle，由核心fixture检查；
不能虚称额外checker读到了该idle或把924额外样本当成程序请求。

## 逐行缺口与覆盖提升

自身原DA精确 **26994→49882/59602，新增22888、丢失0**。
[逐行CSV](../../results/lsq-s4-precise-03/s4-precise-uncovered-v2.csv)和
[原文/SHA/理由字典门禁](../../results/lsq-s4-precise-03/s4-precise-coverage-audit-v2.json)
保留全部9720缺行，不删除分母、不并入旧59595或叶子分子。主要剩余：

- RAR292：coherence release匹配向量及两拍PA；本批无release，不再误称物理槽没访问。
- RAW224：正违例rollback最老选择与元信息；负查询/flags遍历不是正冲突检查。
- Replay3510：具体slot/入口的MSHR、TLB、strict、blockSq、wake/hint和special计时情况。
- VLQ1805：完成宽度3..8、稀疏八入口/多flow和分配/取消相邻时序。
- VSQ31：真实取消Store后缀的退休前缀walk及其他dispatch入口exclusive-end选择。
- PSQ320：全64普通Store槽已消费，剩CBO类型保存/选择，不能用普通Store抵消CBO FAIL。
- Uncache/FreeList等其他每行同样有原功能映射，不判不可达；local-only reset另补。

本批旧82点功能注册表为0/82 checked，新增源关系/终态检查单列上述证据；不把局部
新测试成功冒填成82/82。其目标是补真实缺关系和自身DA，不替代原完整功能注册。

## 日志策略与未验证边界

03实际0逐拍JSON/0wave；84例UID/窗口终态小报告合计4121403字节，主/检查/actor
journal摘要160050字节。完整native主流7428424660字节仅在线检查/哈希，没有落成
逐拍JSON。汇总和SHA不是对未保存新raw的独立离线重放。

TLB/Cache/LDU/ROB是已声明生产者边界，不是本轮native上游DUT。原八种子全权重随机、
其他128/旧代、local-only reset完整边界及新的全范围统一回归/最终请求审计仍必需。
旧S4和ordinary接口证据/FAIL不追溯提升正常准入，局部通过不关闭整体目标。
