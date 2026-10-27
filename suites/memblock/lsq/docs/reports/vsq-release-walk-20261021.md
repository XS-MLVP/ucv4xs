# VSQ release→walk：退休前缀、恢复尾与同槽新 UID

**状态：阶段补例已完成，整体仍为 `ACTIVE_NOT_ACCEPTED`。** 本轮按固定
`kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e` 原样 RTL，在
VSQ→StoreQueue→LsqWrapper 真实层次上补充 release→walk 情形；
没有改 RTL/Chisel、Picker DUT、共享 actor 或参考模型。

## 1. 语义合同和真实检查

先建立 [vsq-release-walk 合同](../contracts/vsq-release-walk.md)，再实现三个
层次的参数化用例。四个合法窗口为 `(SQ 起点, 已退休前缀)`：
`(0,1)、(62,8)、(126,9)、(190,59)`；每窗保留前缀及两条幸存 Store，
取消三个年轻 Store，随后用三个新 UID 正常复用并消费。redirect 额外等待相位
为 `0/1/2` 拍，每层各有三个参数化节点。

| 层次 | 检查内容 | 功能 bin |
|---|---|---:|
| VSQ | 公开 ROB/redirect、recover stall、exclusive physical tail、取消年轻后缀；叶子不冒充父级内存消费 | `VSQ-WALK.prefix_windows`：0→24 checked |
| StoreQueue | 保留真实 VSQ/PSQ/UQ 连接；Sbuffer 背压下保留旧 Store 字节，取消后仅回收年轻后缀，同位置新 UID 正常 fire/出队 | `SQ-RECOVER.prefix_windows`：0→12 checked |
| LsqWrapper | 两分支真实恢复；幸存 Load 在 ROB 推进前完成原 S3/字节检查；取消 Load 不执行，新 Load 使用复用 LQ 槽与原 S3 完成；Store 字节和出队真实完成 | 既有 `LSQ-RECOVER.retired_store`：1→4 checked |

所有窗口使用独立外部 UID、ROB/SQ/LQ 台账，恢复尾通过公开端口读取；没有写入
内部 state、entry array 或指针。被取消 Store 未被伪造 physical dequeue；Wrapper
只在真实查询/翻译/执行后才推进 Load，未把未发射查询当作完成。

## 2. Directed fresh baseline/after

| DUT | 节点 | raw line | raw toggle | raw branch | 15850 `if` | 15850 `else` | 15853 `if` | 15853 `else` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| VirtualStoreQueue | 7→10 | 8→8/8 | 5899→6594/10060 | 349→355/364 | 8 | 0 | 8 | 0 |
| StoreQueue | 4→7 | 151→156/223 | 63421→71514/102374 | 2021→2077/2198 | 7 | 0 | 7 | 0 |
| LsqWrapper | 3→6 | 180→230/3654 | 91380→120901/322010 | 7396→8063/18670 | 7 | 0 | 7 | 0 |

各组 baseline/after 使用同一 native build 和同一点全集，旧命中无丢失。Wrapper
的 directed toggle 增益较大，是因为该 baseline 只选恢复相关既有节点，不是完整
回归前后分子。完整源码 LCOV 行分母仍分别独立报告；本轮不把 raw line 点当作
LCOV 行。

三种 redirect 相位均有 compact witness；不同相位的公开 stall 周期实际不同。
每份 witness 有四个窗口、12 个取消旧 Store UID 和12个新 Store UID；父级每个
完整测试完成254个正常 Store。Wrapper 每个参数还完成4个原 Load、4个复用新
Load、4个取消 Load 和254个真实 Sbuffer fragment（另外12个取消的是Store）。

## 3. `state==3` 边界与 release-wait 边界分离

固定三份 `VirtualStoreQueue` 原样源 SHA 均为：
`61685efc3ab12cba8d0695f23d033929b8ead3a30688d71dd51ecf2644bda822`。

- `state` 是2位寄存器；异步 reset 写入0；完整 clocked 写入只有0、2、0、1
  （源行14578、15851、15854、15857）。初始化随机写不属于复位后动态域。
- 对15848..15857完整谓词枚举32种 state/reset/redirect/head 条件，复位后闭包
  为 `{0,1,2}`；15853 的 `else` 精确要求 state3。因此三个 DUT 的
  `15853 else` 保留原 branch 分母但有 **post-reset state3 不可达**的源/归纳
  边界证据。它不是动态 coverage gain，也不证明无 reset、启动随机态、故障注入
  或其他配置。
- `15850 else` 是 release 状态继续等待 retired head；本轮合法窗口命中了对应
  `if`，但 `else` 仍为0。它不受 state3 归纳覆盖，继续作为
  `release_wait_not_proven_unreachable` 开放缺口，没有豁免。

审计证据：`results/lsq-progress-regression-15/vsq-recovery-boundary-audit-v1.json`。
统一branch原缺口库存仍为563点（不是总branch分母）；初始化137个仍有单独
精确源范围证明，另3个state3点由原条件缺例修正为已证明post-reset边界，余423个
条件缺例保持。各build总分母和原始未命中点全集均不改变，不当成动态增益。

## 4. 六-build fresh 完整贡献范围

```sh
python3 -B tools/run_summary.py --name vsq-release-contributor-regression-01 --workers 8 -- tests/forward tests/psq tests/store_queue tests/lsq_wrapper tests/local_reset tests/normal_mixed/test_original_seeds.py tests/sq_endpoint/test_ldu_joint_phases.py tests/sq_endpoint/test_wrapper_raw_boundary.py tests/unalign/test_basic.py tests/unalign/test_extended.py tests/unalign/test_page_pairs.py tests/vsq
```

实际结果：**1171 节点，1000 PASS / 171 FAIL，0 ERROR / 0 SKIP**，运行时间
**2558.69秒**；manifest/JUnit、native artifact、锁定 Verilator 5.052 分析器
均核验，source launch/end aggregate 相等。

完整原始范围由：

- 上一五-build贡献范围 **1119** 节点；
- regression15 中原有 VSQ **42** 节点；
- 一个在本轮新用例之前已经存在、但不在 regression15贡献命令中的
  `tests.vsq.test_extended::test_redirect_release_walks_after_head_is_consumed`；
- 本轮新参数化节点 **9** 个；

组成。故严格基线为 **1162** 节点，新增节点为9个，9个均 PASS；不是把那个
既有漏选节点错误算成新补例。原171个失败保留；其中两个 VSQ 失败的当前测试
源行从196到226，精确源diff证明为此前插入一个30行 release 测试所致（不只是
注释变化）；移除这个新增函数后，旧/新模块所有原函数AST完全相同。assertion、实际值、
失败 outcome 和其余全文均相同。专项审计只对这两个明确 node 做行号占位归一化：

- 原 failure SHA：`50aaa8ae636f58cabfb70cfbb2adacc6bafe45bc7370e5f73e6d9ba4274f898b`；
- 当前 raw failure SHA：`ee31498630cb268f734a4db9f48d19a35ef6f4cb11255193dda16aa313a019e3`；
- 限定归一化后 SHA：`04354c9cf07e8126b71b2434a6abf825b49b787c35045bcd894c94bc4973dfff`。

### 完整 native 覆盖变化

| DUT | toggle 前→后/分母 | 新增命中 | branch 前→后/分母 | LCOV 原始源码行 |
|---|---:|---:|---:|---:|
| ForwardModule | 37654→37654/40034 | 0 | 54→54/54 | 253→253/253 |
| PhysicalStoreQueue | 83018→83018/86318 | 0 | 1830→1830/1834 | 5817→5817/5817 |
| StoreQueue | 94281→95219/102374 | 938 | 2191→2191/2198 | 8968→8968/8968 |
| LsqWrapper | 277741→277863/322010 | 122 | 18592→18592/18670 | 59595→59595/59602 |
| UnalignQueue | 836→836/908 | 0 | 17→17/18 | 44→44/44 |
| VirtualStoreQueue | 8622→8665/10060 | 43 | 361→361/364 | 3125→3125/3125 |

完整运行的 raw line 点没有新增命中；所有 build 的三类点全集保持，旧命中无丢失。
实际 native `input_files` 为 Forward 186→186、PSQ70→70、SQ83→86、Wrapper
738→741、UQ42→42、VSQ42→46。上一五-build的原主摘要、Wrapper **2214**份
public/check/actor 流、原UQ42份流和VSQ42份流逐项保持；完整9份新 witness
与 directed 对应 witness 相同。

## 5. 统一链和剩余范围

- `all_old_native_hits_retained`：`PASS / required=true / waived=false`，证据
  `results/vsq-release-contributor-regression-01/vsq-release-contributor-regression-evidence-v1.json`。
- post-regression 连续链已 exit 0；当前 gap summary 有 **29** 份独立 directed
  报告，统一 regression15 仍为 **2330节点、2103 PASS/227 FAIL**，不改原 dat、
  分母或失败库存。
- 当前完整 VSQ release 运行的非 wrapper toggle 剩余：Forward2380、PSQ3300、
  SQ7155、Wrapper44147、UQ72、VSQ1395；VSQ/父级 branch 中15850 else仍开放，
  另有其他恢复、异常、总线、跨页 Load、禁用反馈和可达业务缺口。
- 没有生成逐拍 JSON、波形或完整源码副本；没有 Git commit/push 声明。

详细机器证据：
`results/vsq-release-windows-after-01/vsq-release-windows-evidence-v1.json`、
`results/sq-release-windows-after-01/vsq-release-windows-evidence-v1.json`、
`results/lsq-release-windows-after-01/vsq-release-windows-evidence-v1.json`、
`results/vsq-release-contributor-regression-01/vsq-release-contributor-regression-evidence-v1.json`。
