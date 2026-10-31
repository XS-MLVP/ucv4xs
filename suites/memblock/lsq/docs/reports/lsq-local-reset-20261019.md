# LSQ本地reset保留旧外部请求：15 PASS，原DA新增3502

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


## 本轮结论与边界

真实53文件LsqWrapper、Picker＋xreactor新增独立`tests/local_reset/`。首轮12 PASS，
逐行缺口后补16池情况，最终**15 PASS**、528份启动/结束源一致；原12实际主流SHA/
字节和语义事件见证全部保持。共享149份`lsqverify/`参考文件未改，仍用完整输出
WrapperEnv而不是probe；只在显式opt-in参考中跨本地reset保留已ack外部NC job账本。

这证明声明的“本地LSQ reset、外部Uncache保留已接受请求”profile。它**不是**原生
MemBlock/Uncache/TileLink reset域集成UT，亦不证明迟到旧ack或Store串行reset安全。
旧共同系统reset的external-reset-aborted用例保持，不能混用两个合同。

用例前合同：[保留外部响应](../contracts/lsq-local-reset-retained-uncache.md)、
[全部16 SID在途时补例](../contracts/lsq-local-reset-full16.md)。

## 微架构关系和实际检查

1. 原Load真实dispatch/S0 Forward/S1 PA/S2 RAR/RAW/S3首次NC，正常operation6、hyper0/
   nonleaf0；首次需要Uncache而没有Backend WB，`updateAddrValid=0`。
2. 原NC请求真实fire/ack，旧SID已在外部占用。只reset本地LSQ六拍：原Load本地中止，
   外部请求仍在途，不能抹账或伪称返回。旧SID真实resp前不能复用，新MID/LQ槽可复用。
3. 旧响应覆盖四个真实时点：reset后无新Load、新MID复用但新响应未到、新响应已到
   而bypass未消费、新bypass S1之后同拍旧回包。旧响应不能唤醒新owner或污染新数据/
   错误；新owner须原grant、原slot反馈、NC bypass和真实S3/VLQ deq完成。
4. 三lane各一条16池程序：16旧SID全占用并跨reset保留，没有另一个空闲SID可借。
   每次先真实返回一个旧SID，再给新请求使用；新16 MID/LQ0..15全部实际复用。按
   公开可见PA认请求UID，按实际可见Replay候选公平消费，VLQ只释放真实完成前缀。
5. 原旧UID终态是local-reset-aborted，外部job为actually-returned-and-discarded，
   不是年轻取消、普通成功或异常WB/精确trap。每个原LQ槽都有新UID正常完成见证。
   旧denied/corrupt遵循Uncache源码互斥，新数据和错误独立保持，不读DUT内部作答案。

## 实际证据

| 项目 | 首轮01（12例） | 补例02（15例） |
|---|---:|---:|
| 原UID | 36 | 132 |
| 正常完成 / 本地reset中止 | 24 / 12 | 72 / 60 |
| 外部req / ack / 真实返回 | 36 / 36 / 36 | 132 / 132 / 132 |
| 旧响应真实返回丢弃 / 外部abort | 12 / 0 | 60 / 0 |
| 原grant / bypass数据 / S3反馈 / VLQ deq | 各24 | 各72 |
| reset槽同物理LQ新UID正常完成 | 12 | 60 |
| Native记录 / 独立checker请求 | 1236 / 1104 | 2751 / 2586 |
| 自身原DA | 26573/59602 | 30075/59602 |

02新增**3502行、旧命中丢失0**，原分母不变，29527剩行逐项分类。14个此前未激活
UncacheEntry各新增56行；全部16 entry各余6行，不把它们判不可达。LQU新增454、
Replay新增1488、RAR新增434、VLQ新增173等均来自本目录真实运行，不借S4或叶子分子。

[首轮v1语义门禁](../../results/lsq-local-reset-retained-01/local-reset-audit-v1.json)、
[首轮逐行缺口](../../results/lsq-local-reset-retained-01/local-reset-coverage-audit-v1.json)、
[02 v2语义/影响门禁](../../results/lsq-local-reset-retained-02/local-reset-audit-v2.json)、
[02逐行CSV](../../results/lsq-local-reset-retained-02/local-reset-uncovered-v1.csv)、
[02 DA增/失及理由字典](../../results/lsq-local-reset-retained-02/local-reset-coverage-audit-v1.json)。

```sh
python3 -B tools/run.py --name lsq-local-reset-retained-02 --workers 4 -- tests/local_reset --tb=short
python3 -B tools/capture_end_sources.py lsq-local-reset-retained-02
python3 -B tools/coverage_audit.py lsq-local-reset-retained-02
python3 -B tools/audit_lsq_local_reset_v2.py lsq-local-reset-retained-02
python3 -B tools/audit_lsq_local_reset_coverage_v1.py lsq-local-reset-retained-02
```

## 证据大小与未验范围

02实际0逐拍JSON/0wave，15例关键事件/终态合计202923字节。每个事件是原UID的req/
ack/实际resp/grant/bypass/完成等有界语义见证，不是每拍日志。主fixture继续每拍
比较所有定义输出、完整流哈希，独立checker同时核公开输入/实际输出；事件门禁不
冒称未保存raw的离线重放。原82点功能注册表本批0/82，新增关系检查单独列，不冒填。

剩余DA有具体源/原行/理由，不删分母。主归一化随机、其他128/旧代、迟到旧ack、
serial Store局部reset以及真实系统reset/drain合同和最终完整请求审计仍必需。
原SID合法复用数据污染、RAR、strict、WB/zero/完成顺序等普通FAIL不因本批全PASS
消失；本地reset已清除slaveAccept的正条件不能代替旧数据仍待消费的SID失败域。
