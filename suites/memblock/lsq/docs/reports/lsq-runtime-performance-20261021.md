# LSQ耗时诊断及不减检查的纯编码缓存对照

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


结论：**有用但有限的性能进展，不是功能验收或覆盖率提升。** 默认行为不变，
只新增可关闭插件。完整1457节点没有为性能工作重新运行，原192个FAIL不改。

## 1. 为什么长

`load-response-contributor-regression-02` 24 worker实测37分54秒。最长三个S4
精确用例各约10分35秒，分别连续完成360程序、1734 UID、20515检查周期；
不是无界卡死。另三个S4普通多代例各约6分30秒，也完成300程序并PASS。

两个原混合例确实用尽5000周期公平排空预算，约193.7/181.1秒后FAIL，原义务
未完成；不因“历史FAIL”改成通过，也不为提速缩短预算。

3471份journal摘要累计47,906,108,694字节的序列化/哈希流，保存逐拍trace为0。
这个数说明有处理成本，**不能仅按字节数判定主要热点**。

实际cProfile两个原Wrapper节点，结果与after-02原节点、6份stream全等。普通
混合与strict例分别约1.25/9.55秒的profile call时间，CPU时间近似wall；大量
startswith、编码、native引脚访问。strict例JSON encoder独占约0.136秒，不是
最大项。Profile累计时间会嵌套，不能相加；也不能把插桩占比当整轮未插桩占比。

证据：`results/load-response-contributor-regression-02/runtime-bottleneck-diagnosis-v1.json`。

## 2. 合同、实现与约束

- 先行合同：`docs/contracts/lsq-runtime-summary-performance.md`。
- 观测插件：`lsqverify/runtime_profile.py`，仅显式启用call阶段profile，保留Top
  函数列表，不保留profile二进制、逐拍trace或波形。
- 试验插件：`lsqverify/codec_cache.py`，只缓存Replay/LoadQueue/StoreQueue/
  Wrapper四个**纯接口编码函数**；不缓存参考输出、model.connected、任何模型
  状态、DUT样本或反馈，不修改冻结源文件或工具库。
- 深度不可变输入按完整值缓存，每函数64项、每例清空，返回新dict；非不可变
  输入回到原函数，错误不缓存。Miss仍走原编码的所有形状/位宽/共享字段验证。
- 每例call阶段安装/还原纯函数别名，默认不启用；全部语义参考、before/after
  检查、actor、失败条件、等待预算及完整旧格式JSON摘要都保留。

## 3. 验证与实际收益

`tests/runtime/test_codec_cache.py` 六项纯单测通过：四编码完整值/顺序/返回值
被修改后不污染缓存/非法形状、可变输入不缓存及安装/恢复。单测不代替DUT。

真实对照选择6个原节点：两个普通混合Load/Store、NC/MMIO错误响应各一个、
一个S4尾故障/头重放恢复、一个**原strict-full-pool必保留FAIL**。开关都用原
严格fixture/参考/actor/seed，source聚合相同。次序为baseline→after→after→
baseline，避免只按一次先后差声称提升。

四轮均5 PASS/1 FAIL：全部原结果与strict失败全文相等；18份public/check/actor
摘要的records/bytes/SHA相等；固定build和完整dat字节相等，故三类点全集、每点
计数、命中均不变。两次缓存计数摘要也相等。**动态覆盖新增为0**。

| 运行 | 缓存 | 6例JUnit时间合计 | 实际runner墙钟 |
|---|---|---:|---:|
| baseline-01 | 关闭 | 32.836秒 | 53.719秒 |
| after-01 | 启用 | 31.276秒 | 51.972秒 |
| after-02 | 启用 | 31.065秒 | 51.945秒 |
| baseline-02 | 关闭 | 32.945秒 | 54.040秒 |

平均JUnit合计缩短5.23%；端到端缩短3.57%。前者包含fixture setup/call/teardown，
不是隔离call加速比；后者包含覆盖处理。小样本和机器竞争会影响时间，不承诺
同比加速完整37.9分钟或全部38-DUT。**收益有限，暂不默认采用。**

证据及可重建审计：

- `results/lsq-codec-cache-after-02/runtime-performance-control-v1.json`。
- 同目录`runtime-timing-receipt-v1.json`保留实际四轮runner时间和工具日志SHA。
- `python3 -B tools/audit_runtime_performance_v1.py`。
- 精确原节点及开关命令见四个`lsq-codec-cache-{baseline,after}-0{1,2}/command.json`。

## 4. 未完成范围

这不是所有LSQ参数/恢复/非法输入域的缓存等价证明，更不是38-DUT最终验收。
不修改已完成的1457节点结果，不把性能正例替代两mixed排空FAIL、SID失败或
SQ头许可边界。后续按真实热点再选择优化，避免盲增worker或为了5%收益重复
整轮回归；仍继续原功能缺口闭环及全范围最终审计。
