# FTQ backend redirect 后的年轻项训练泄漏

2026-10-10：在隔离的真实 BPU＋Ftq＋ResolveQueue＋CommitQueue 包中，
两次原生实验复现同样的五个普通 pytest FAIL。未修改 RTL，未改成
XFAIL，未将失败用例的 native 覆盖计入正式行增量。

问题标识：`FTQ-BACKEND-REDIRECT-YOUNG-TRAIN-001`。

## 场景与边界

先通过真实取指接口取得 FTQ 0、1、2、3，再暂停 fetch 接受。backend
反馈旧项 0、误预测项 2，并对项 2 发出真实 flush-after redirect；项 3
的已发射分支反馈分别落在 effective redirect 当拍、下一拍、下两拍。
输入 predictor metadata 不由测试提供，而由真实 BPU 写入 FTQ。

`ResolveQueue.scala:51` 的设计说明明确考虑 redirect 后仍返回的已发射
分支，并用三拍 redirect 窗口防止过期 metadata 参与训练。因此这里的
预期是：0、2 各训练一次，3 不训练；不是要求所有 backend 反馈瞬时消失。

| ahead index | 当拍反馈 | 下一拍反馈 | 下两拍反馈 |
| --- | --- | --- | --- |
| absent | PASS | FAIL | FAIL |
| match | PASS | PASS | FAIL |
| mismatch | PASS | FAIL | FAIL |

配置为该隔离包的 MinimalConfig：FTQ 8、ResolveQueue 16、backend
resolve 三路。结论针对这个实际配置及精确源码／二进制，不冒称已经完成
默认整核配置、所有 FTQ 生命周期、全部环回／覆盖写组合的验证。

## 原生只读证据

`probe-v16`：62 PASS、5 FAIL；`probe-v17` 增加两项诊断工具契约，
64 PASS、5 FAIL。原有 49 项全部保留并通过。两次实验的真实输入、
输出、metadata 与有效 redirect tick 完全相同，限窗观察没有扰动行为。

观察全部经 memory-direct；VPI、内部写入、波形运行时导出均关闭。
普通场景不启用状态诊断，只为这次定位显式记录有限窗口内的状态变化，
最多 96 次采样，不导出整场景逐周期轨迹。

以 `absent / 下一拍反馈` 为例，tick 是框架事件编号，不是直接的周期数：

| tick / 相位 | 实际状态 |
| --- | --- |
| 295 / DriveStable | effective backend redirect 有效 |
| 297 / DriveStable | 年轻项 3 的真实 resolve 输入有效；redirect 延迟一级有效 |
| 298 / post-rising | 项 3 已在队列中，valid=1、flushed=0 |
| 299 / DriveStable | 延迟二级仍有效；项 3 的 queue valid/ready=1；trainCache redirect 保护已无效 |
| 300 / post-rising | 项 3 进入 trainCache，cache valid=1；队列项已出队 |
| 302 / rising acceptance | 公开 BPU train 接口接受了项 3 的旧分支训练 |

相比之下，`match / 下一拍反馈` 中队头还被项 2 占据，项 3 多等了一拍，
flushed 实际变为 1 后被丢弃，所以通过。不能用这个通过组合外推完整窗口。

## 对应 RTL 逻辑

- `XiangShan/src/main/scala/xiangshan/frontend/ftq/ResolveQueue.scala:56`：
  redirect 延长到三拍。
- 同文件 `:157`：只对时钟前已经 valid 的条目设置 flushed；当拍新入队
  的条目不能在同一判断中被标记。
- 同文件 `:162`、`:166`：出队资格检查旧 flushed 位，没有直接排除当前
  redirect 窗口内的年轻项。
- 同文件 `:169`：出队同时清理条目，不能用这一拍计划设置的 flushed
  阻止已经成立的 queue handshake。
- `XiangShan/src/main/scala/xiangshan/frontend/ftq/Ftq.scala:419`：
  trainCache 的 needFlush 只保护当前及上一拍 backend redirect。

两种已观察路径：下一拍返回的年轻项可在队列第三拍 flush 标志提交前
出队；下两拍返回的年轻项直到窗口结束才成为 valid，随后也未被标记。
trainCache 的较短保护未阻止这两种实际出队，最终发生公开训练。

这是当前配置下的缺陷定位，不包含 RTL 修复授权或修复完成声明。

## 复现与证据检查

保留位置：`results/line-gap-probes/ftq-memory-direct-v5/probe-v16/`、
`probe-v17/`，包含实验源码归档、预启动源码哈希、pytest 收据和紧凑结果。

独立检查命令：

```sh
python3 results/line-gap-probes/ftq-memory-direct-v5/diagnose_backend_v17.py
cd results/line-gap-probes/ftq-memory-direct-v5
python3 -m pytest -q -c /dev/null -p no:cacheprovider test_backend_diagnosis.py
```

18 项检查覆盖九格真实证据，以及有效相位、输入相位、queue guard、
flushed、cache 身份、train 身份、PASS 状态、metadata、旧项完整载荷的
篡改拒绝。检查器通过不意味着被测 RTL 通过；缺陷摘要明确保留五项 FAIL。
