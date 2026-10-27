# LSQ统一回归08：38个原生DUT / 1828例，保留170个普通失败

**结论：NOT_PASS。** 冻结的完整已实施范围已统一重跑，实际为**1658 PASS / 170 FAIL**，
没有skip/xfail。历史、失败签名、产物与逐DUT覆盖门禁已完成，不等于整个目标通过。
本次**不包含**随后新增的正常CBO包用例、SQ端点最小例或其参考端点修正。

## 1. 原生命令及冻结范围

```sh
python3 -B tools/run.py --name lsq-progress-regression-08 --workers 4 -- tests --tb=short
python3 -B tools/capture_end_sources.py lsq-progress-regression-08
python3 -B tools/coverage_audit.py lsq-progress-regression-08
python3 -B tools/audit_progress_run_v9.py lsq-progress-regression-08
```

实际pytest持续2220.05秒，退出码1；结束立即捕获**371份启动文件SHA全部一致**。
v9首次前台审计被300秒shell超时中止，确认无遗留进程后原样无超时后台重做，
已收到完成通知并产生`evidence-check-v9.json`。超时不冒充审计通过，也未改门禁。

| 家族 | 本次例数 | PASS | FAIL | 持久原始记录 |
|---|---:|---:|---:|---:|
| AgeDetector | 11 | 11 | 0 | 无持久逐拍JSON |
| 三CAM | 24 | 24 | 0 | 无持久逐拍JSON |
| 四FreeList | 52 | 52 | 0 | 无持久逐拍JSON |
| RAR | 54 | 47 | 7 | 8491 |
| RAW | 32 | 32 | 0 | 11301 |
| VLQ | 22 | 22 | 0 | 4881 |
| 16个UncacheEntry | 384 | 384 | 0 | 86129 |
| LoadQueueUncache | 72 | 64 | 8 | 9163 |
| Replay | 131 | 127 | 4 | 20954 |
| EnterSbufferQueue | 26 | 26 | 0 | 4582 |
| UnalignQueue | 41 | 41 | 0 | 5947 |
| ForwardModule | 184 | 165 | 19 | 5599 |
| VSQ | 42 | 40 | 2 | 4531 |
| DeqModule | 92 | 67 | 25 | 6246 |
| PhysicalStoreQueue | 66 | 45 | 21 | 7489 |
| StoreQueue | 79 | 55 | 24 | 7114 |
| LoadQueue | 199 | 187 | 12 | 28820 |
| LsqWrapper | 317 | 269 | 48 | 72918 |
| **总计** | **1828** | **1658** | **170** | **284165** |

## 2. 实际请求→证据门禁

- 全部1828个JUnit节点/结果等于冻结基线的精确并集：其他36DUT使用
  `lsq-progress-regression-06`的1312例，LoadQueue用`lq-joint-impact-02`的199例，
  Wrapper用`lsq-expanded-16`的317例。没有追溯扩大旧回归07的1808例。
- **170个失败的原主断言保持**，只归一化Python对象进程地址，不归一化真实data、
  tick、UID、指针或异常位。普通RTL/接口失败没有变成PASS。
- **1741份原始日志 / 284165条公开采样**的完整SHA多重集合相等，其中保留nodeid
  的**979份**另逐节点精确匹配。基础87例只有连续运行时检查/节点/结果/native/
  功能与源码证据，没有持久逐拍JSON，明确不虚构其逐节点原始轨迹。
- **38份实际native build / 76个功能组**及manifest、artifact、build文件SHA核验。
  每个独立DUT按自身LCOV的原DA源/行全集、命中集合、未命中集合逐项比较，均与
  各自冻结基线相同；不拼其他DUT的命中到父块中。
- Wrapper本体114/114、真实53文件闭包**59595/59602**；LoadQueue本体57/57、
  真实45文件闭包**50513/50520**。两层剩7行仍留在原分母，本层窄证明不是动态命中。
- Wrapper维持**76/82 checked**。缺SID复用、前拍RAR release、disabled strict，
  以及三个STRESS总项；其局部PASS或满DA不能抵消必需FAIL。

证据：`results/lsq-progress-regression-08/{pytest.xml,end-source-check.json,line-audit.json,`
`evidence-check-v9.json,execution/manifest.json,execution/functional-coverage.json}`。

## 3. 必须同时阅读的正常CBO准入更正

v9证明的是**原始公开接口执行历史可重复**，并没有检查每个生产者的全部真实
StoreUnit字段。回归运行期间进一步源码审计发现旧CBO刺激为size3/mask255/wline0，
真实`NewStoreUnit`则为**QB4/maskFFFF/wline1/16B对齐**。

因此，尽管本次与expanded16的实际历史全部相等，原8个混合/6个联合例仍不能
被提升为正常CBO流量证明；原512个槽×CBO×STA也是旧接口证据，须正常包重做。
原全部FAIL、UID守恒及实际容量快照保留，不把旧size3 CBO范围现象当普通程序
缺陷。详见[CBO生产者复核](lsq-cbo-producer-review-20261019.md)与
[新正常CBO合同](../contracts/lsq-normal-cbo.md)。

后续新正常域14例在独立目录`lsq-normal-cbo-01`实际6 PASS / 8 FAIL，197次CBO STA
元信息准入、6联合例完整原UID/16B zero及8混合失败前缀分别审计；它们不在本次
1828例范围，也不能给此回归追溯改名或扩大结果。

## 4. 仍未达成的完整目标

完整目标依然是全部层次的人类可读功能、真实Picker+xreactor检查、逐行分类和
补例重跑，并保留跨块顺序/字节/背压/恢复/重放/路由证据。此回归只是当前冻结
范围的统一复核。正常CBO缺失情形、exact128参考端点、全域混合/公平恢复交错、
新增范围影响回归和最终请求→证据/未验证边界审计仍需完成，目标保持active。
