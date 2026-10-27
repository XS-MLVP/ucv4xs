# LSQ阶段回归04：1075例、33个独立DUT

## 结论与真实范围

**1035 PASS / 40 FAIL，严格NOT_PASS。** 这是阶段回归，不是完整LSQ验收。相比回归03增加ForwardModule的184例和VirtualStoreQueue的42例，旧849例/31DUT运行、门禁及源码快照全部保留，不覆盖或缩小。

回归命令通过`tools/run.py --name lsq-progress-regression-04 --workers 1`运行13个明确目录：age、cam、freelist、rar、raw、vlq、uncache_entry、load_uncache、replay、enter_sbuffer、unalign、forward、vsq。共1075个唯一case，未用-k/deselect/skip；实际pytest运行1079.33秒。

| 家族 | 例数 | 结果 |
|---|---:|---:|
| 既有11家族/31DUT | 849 | 830 PASS/19 FAIL |
| ForwardModule | 184 | 165 PASS/19 FAIL |
| VirtualStoreQueue | 42 | 40 PASS/2接口FAIL |
| 合计 | 1075 | 1035 PASS/40 FAIL |

该运行**不含DeqModule新功能用例**；Deq在此轮期间使用新文件和独立目录实施，不能把其新增6个失败追溯加入1075例结果。真实Deq/PSQ/StoreQueue/LoadQueue/LsqWrapper完整验收均未达成。

## 失败与域分类

| 问题 | FAIL数 | 域 |
|---|---:|---|
| RAR-REL-001 | 7 | release时序严格失败 |
| LQU-SID-001 | 7 | 合法SID复用污染旧数据/错误 |
| LQU-MMIO-IF-001 | 1 | 仅接口多MMIO selector边界 |
| LRQ-STRICT-001 | 4 | strict容量/无效feedback清除 |
| FWD-ALIAS-001 | 3 | 跨word物理别名返回老值 |
| FWD-SQID-001 | 6 | 裁剪后完整SQ依赖身份错误 |
| FWD-RANGE-001 | 10 | 8个生产者域及2个接口mask压力 |
| VSQ-REDIR-IF-001 | 2 | 仅接口同拍dispatch/redirect边界 |

共35个生产者域失败、5个仅接口边界失败。门禁逐个匹配节点和实际失败签名，不把known-issues当oracle/豁免；所有仍为普通FAIL。

## 覆盖与证据门禁

33份独立native build、66个功能覆盖组、180份冻结启动文件及全部artifact/build SHA核验通过，180份文件在运行结束时仍与启动快照完全一致。已运行`tools/audit_progress_run_v4.py lsq-progress-regression-04`，证据在`results/lsq-progress-regression-04/evidence-check.json`。

除LQU固定六条guarded mux defaults外，各独立DUT本体及有DA的真实依赖闭包全部命中。LQU保留原分母1120/1126、本体真实闭包3169/3175；本轮重新执行`audit_lqu_static.py`，仅对这六行证明写default条件矛盾，不删行、不扩大为全DUT形式化证明。RAR零延迟辅助模块的无原生DA边界继续保留。

未checked语义仅存在于RAR 52/55、LQU 40/42、Replay 82/84、Forward 61/64、VSQ 54/55；缺口逐项等于被冻结问题对应的严格语义，不拿行覆盖满抵消功能失败。

此门禁核验范围、覆盖、失败与证据完整性；各模块的详细历史审计仍以独立结果目录为准。后续加入Deq或更多用例需另开版本，不能修改本1075例门禁或旧回归结果。
