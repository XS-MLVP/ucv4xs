# UQ 两槽第二页 PA：真实跨页 Store、消费与 Wrapper 闭环

**结果：UQ→PSQ→StoreQueue→LsqWrapper 的第二页成对生命周期补例通过；完整
五-build 贡献范围实际运行 1119 节点，950 PASS / 169 FAIL，0 ERROR/SKIP。
原 1113 节点结果和 169 个失败全文保持，新增 6 个节点全部 PASS；当前覆盖
单调性门禁 PASS、未豁免。整体仍为 `ACTIVE_NOT_ACCEPTED`。**

## 1. 合同和真实功能检查

实现前建立 [UQ 第二页合同](../contracts/uq-second-page-pairs.md)，固定源为
`kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e`，不修改目标 RTL、
Chisel、Picker/X Reactor 或共享参考模型。

| 层次 | 人类可读功能点 | 实际 witness |
|---|---|---|
| UnalignQueue | 两个第二页请求同时占有两个公开槽；背压保持 head、SQ 身份和页 PA；第三个有效请求不能偷接，消费一个后才真实接受并复用槽 | 8 组 profile、24 个 page UID、每组 3 次真实 page 完成；旧 41 节点全部保留 |
| PhysicalStoreQueue | 真实 STA/STD 形成两个 offset=4092 的普通 8B Store；第二页 valid/ready 后才发尾 STA；两段 PA/mask/原字节真实 Sbuffer 消费，单 UID 正常完成 | 8 组、16 个跨页 Store、32 个跨页片段及 256 个总 Store 完成 |
| StoreQueue | VSQ→PSQ 真实连接保留，ROB/许可后才消费；四圈 SQ flag 复用不串旧页身份 | 8 组，256 个 Store、272 个真实 Sbuffer 片段、正常出队 |
| LsqWrapper | 三个真实 Load lane 分别读取第一页最后 4B；原 LQ/ROB/SQ/uop 经 S3 完成；Store 的第二段仍由 UQ/Sbuffer 真实消费 | 3 个 lane witness，各 256 Store、16 个跨页 Store、16 个原 Load、272 个 Store 片段 |

第二页 PA 交替使用合法高/低 profile：偶数 profile 为 `((1<<36)-1-owner)<<12`，
奇数 profile 为 `owner<<12`。page offset 保持 0，第一页 VA/PA offset 为4092；
低 12 位的常零是合法页对齐约束，不被伪装成动态覆盖。所有输入均通过公开
接口进入，只有真实 page fire 后才更新外部 UID 台账。

## 2. Directed baseline/after

| DUT | PASS 前→后 | toggle 前→后 / 分母 | branch 前→后 / 分母 | 高36位页 PA目标 |
|---|---:|---:|---:|---:|
| UnalignQueue | 41→42 | 836→836 / 908 | 17→17 / 18 | 144/144 |
| PhysicalStoreQueue | 5→6 | 30884→54955 / 86318 | 1022→1718 / 1834 | 144/144 |
| StoreQueue | 4→5 | 63291→65569 / 102374 | 1938→2015 / 2198 | 144/144 |
| LsqWrapper | 5→8 | 85598→121275 / 322010 | 6206→7079 / 18670 | 144/144 |

每组 baseline/after 使用同一 native build、同一点全集，旧命中无丢失。UQ 的
`UQ-PAGE.paired_lifetimes` bin 为 **0→16**；PSQ/SQ bin 为 **0→1**；Wrapper
沿用原 `LSQ-FORWARD.page`，checked 计数由 3 增至 6。UQ 原有 toggle/branch
库存已经被历史用例命中，因此新情形的功能检查完成不等于 native 计数必须增加。

以实际 manifest/JUnit 纠正早先口头摘要：首次 `uq-page-pairs-probe-01` 为 **6 PASS**，
PSQ 正式组为 **5→6 PASS**。校准用例自身有参数化，不能按命令里的 selector
数当节点数。专项报告现从真实节点表计算 baseline/after 数，不以 outcome 类别
数（例如字典中仅有一个 `PASS` key）代替节点数量。

另保留两项未采用的启动结果：`uq-page-pairs-baseline-01/after-01` 均实际执行
42 节点，前者的目录选择已包含新用例，不能作 before；正式对比改为明确的旧
`test_basic.py + test_extended.py` 与 after 再加 `test_page_pairs.py`。
`sq-page-pairs-baseline-01` 为参数 ID 不完整导致的 **0 节点/exit5/incomplete**，
也不作验证证据；正式 SQ 基线为已执行 4 PASS 的 `sq-page-pairs-baseline-02`。
这些目录与命令保持，不删失败或将未运行节点算作通过。

PSQ/SQ/Wrapper 的 directed 源码行和 toggle 增益较大，是因为本层 baseline
刻意只选取了跨页相关既有用例，不是统一回归的前后分子。所有差集独立保存在
各自 `results/*-page-pairs-{baseline,after}-*` 目录，不回填 regression15。

## 3. 完整五-build 贡献范围重跑

```sh
python3 -B tools/run_summary.py --name uq-page-contributor-regression-01 --workers 8 -- tests/forward tests/psq tests/store_queue tests/lsq_wrapper tests/local_reset tests/normal_mixed/test_original_seeds.py tests/sq_endpoint/test_ldu_joint_phases.py tests/sq_endpoint/test_wrapper_raw_boundary.py tests/unalign/test_basic.py tests/unalign/test_extended.py tests/unalign/test_page_pairs.py
```

实际结果为 **1119 节点：950 PASS/169 FAIL，0 ERROR/0 SKIP**。基线由上一完整
1072 节点贡献范围与 regression15 的 41 个原 UQ 节点组成，共 1113 个；新增
6 个 page 节点全部 PASS。原 169 FAIL 的归一化全文 SHA 前后保持：
`31bff24c501b3d000c5c9ae3eb572f8210133ff0218d0a89803f92451eec04cf`。
真实运行时间为 **2521.18 秒**。

| DUT | 完整 toggle 前→后 / 分母 | 新增命中 | 旧命中丢失 |
|---|---:|---:|---:|
| ForwardModule | 37654→37654 / 40034 | 0 | 0 |
| PhysicalStoreQueue | 82574→83018 / 86318 | 444 | 0 |
| StoreQueue | 93468→94281 / 102374 | 813 | 0 |
| LsqWrapper | 276779→277741 / 322010 | 962 | 0 |
| UnalignQueue | 836→836 / 908 | 0 | 0 |

完整运行的 branch 没有新增命中，line 也没有新增命中；所有三类点全集保持。
按 Forward/PSQ/SQ/Wrapper/UQ 顺序，raw line 点分别为 **2/2、213/213、223/223、
3654/3654、4/4**；LCOV 原始源码闭包行分别为 **253/253、5817/5817、
8968/8968、59595/59602、44/44**。raw line 点与源码行不混用。
五个 build 中，UQ、PSQ、SQ、Wrapper 这 **4 个包含实际 UQ 的 build**，其
`UnalignQueue.entries_0/1_paddrHigh[0:35]` 两方向各为 **144/144**；ForwardModule
不含这个寄存器目标，不以空集合当作该目标通过。
完整运行不是旧 dat 与新 dat 的 OR，原 1113 节点、失败和公开流均在同一次
fresh 执行中核对。

## 4. 失败保持与审计

- 统一 regression15 仍为 **2330 节点、2103 PASS/227 FAIL**，不改分母、dat、
  缺口分类或失败全文。
- 原四 build 的先前 1072 节点与原 41 个 UQ 节点结果逐项保持；新增 6 节点
  均通过。原生导出数分别为 Forward **186→186**、PSQ **69→70**、SQ **82→83**、
  Wrapper **735→738**、UQ **41→42**，各项 primary journal 数与 manifest 相符。
  UQ 既有 41 份 public stream 及 Wrapper 原 **2205 份 public/check/actor**
  摘要全部保持，完整运行的 6 份新 witness 与定向对应者相同。
- 当前 `all_old_native_hits_retained` 为 `PASS/required=true/waived=false`，
  证据为 `results/uq-page-contributor-regression-01/uq-page-contributor-regression-evidence-v1.json`。
- 统一矩阵仍有 38 行、**26 条独立定向报告**，整体状态仍为
  `ACTIVE_NOT_ACCEPTED`。完整审计 `post-regression-uq-page-01.log` 已 exit 0。

```sh
python3 -B tools/audit_uq_page_pairs_v1.py --full
python3 -B tools/audit_post_regression_v1.py lsq-progress-regression-15
```

这些 early/final 派生报告曾有 baseline 节点数、source aggregate 或验证粒度
不足的版本；专项工具现在重新核对原始 dat、锁定分析器、两个运行各自
launch/end aggregate、实际节点及 witness，再按原字节 SHA 归档旧报告到
`audit-history/`。补强审计不改写任何原 dat、manifest、JUnit、历史 FAIL 或源码
启动/结束摘要，也不把语义目标的公共 bit 身份 SHA 冒充各 build 的原生源点 SHA。

补强后连续两次全链仍 **exit 0**，日志为 `post-regression-uq-page-final-02.log`
和 `post-regression-uq-page-idempotence-02.log`。12 份关键报告 SHA 完全相同，
70 份受检历史 manifest/JUnit/native dat SHA 保持，未新增重复归档；12 份相关
Python 源语法解析通过，29 份补例/辅助源的无 skip/xfail 检查保持通过。

当前完整运行剩余非 wrapper toggle：Forward **2380**、PSQ **3300**、SQ
**8093**、Wrapper **44269**、UQ **72**；branch 分别剩余 **0、4、7、78、1**。
这些点继续在各自分母与分类里，不能因144位方向目标完成就从总库存删除。

后续仍开放恢复状态、异常/特殊操作、跨页 Load、禁用反馈、总线组合和各层其余
可达 toggle/branch 缺口。第二页高位目标命中与门禁通过不代表全部 LSQ 功能已验收。
未生成逐拍 JSON、波形或完整源码副本；没有 Git commit/push 声明。
