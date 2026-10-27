# CBO正常生产者准入复核：保留原接口结果，拒绝不实的正常流量声明

**状态：发现验证域错误，目标active。正常CBO原生重跑尚待执行。** 此复核不修改
目标RTL/Chisel，不隐藏普通FAIL，不将审计/静态输入适配当Picker功能通过。

## 1. 新发现及需要更正的声明

继续审计8个混合首失败时，独立PA来源重建定位到年轻CBO.zero与老普通Store的
同line选择。进一步核对真实生产者，发现此前代理的CBO元信息不属于普通
`NewStoreUnit`输出域：

| 同一CBO STA字段 | 实际StoreUnit正常输出 | 当前16轮代理输入 |
|---|---:|---:|
| size | **QB=4** | 3 |
| mask | **0xffff** | 0x00ff |
| wlineflag | **1** | 0 |
| VA/PA对齐 | **16B** | 16B（此项符合） |

依据固定开源`NewStoreUnit.scala:98-102,433-438`、`MemCommon.scala:169`及
`LSQWrapper.scala:206,252`实际同一STA到SQ/RAW的连接，不是从DUT输出或问题清单
反推合法域。PSQ在`NewStoreQueue.scala:1966`还会强制CBO.zero有效数据为0，
所以非零外部STD payload本身不是本次生产者错误，不能混淆。

`cbo-producer-audit-v1.json`已从**317例原始日志**独立核验：30个含CBO STA的用例，
747次实际CBO STA全部为旧size3/mask255/wline0；其中**8个混合种子＋6个联合例**
必须撤回正常CBO准入。前轮生命周期审计核过公开接口守恒，却没有包含这一
真实StoreUnit字段门禁，不能以其绿色判定或staged参考通过来补造准入证据。

原317例269PASS/48FAIL、旧510例原始历史/失败签名相等、53原RTL/native/源码
哈希、同场池峰值等仍是实际接口执行事实。**但本批CBO相关完整fair段不再当作
正常全域CBO证明，size3 CBO范围现象也不能登记成普通程序RTL/ISA缺陷。** 三个
STRESS原本就未checked，继续保持；不是为了新拒绝而将失败转PASS或缩小目标。

## 2. 三个混合终点的精确观察范围

`mixed-terminal-audit-v3.json`独立重建原UID、SQ绝对代、已接受job和真实片段：

- **28928，tick390**：原Load UID352、SQ边界86；旧普通Store UID275/SQ61的
  byte12/13实际返回119/65。更年轻UID290/SQ70是同line CBO.zero，公开接口语义
  应为0，但该CBO的size3元信息非正常生产者。因此只保留**接口范围观察**，
  不是新的正常VA别名或架构缺陷。新QB流量须重新检查，不能将旧反例“平移”。
- **28932，tick302**：ROB头zero UID75/SQ6自己的片段尚未消费，却在另一普通
  Store UID74/SQ5实际fire时flush从0变1。与Chisel975-978未标原owner的head.fire
  相位一致，但该前缀**没有**zero WB或错误SQ释放观察；既有protocol-only
  zero后果反例是另一份证据，不给本前缀伪造后续效应。其CBO元信息也需正常化。
- **28933，tick214→216**：串行IO Store UID113/SQ3已实际接受、尚无自己的ack/
  resp；tick216另一Load UID138/SID0响应后，真实post-edge又出现年轻read valid。
  这提供原串行所有权失配的具体公开身份见证，**没有**下一拍第三请求fire或
  ISA后果声明。整批含其他非正常CBO，正常全域种子仍须修正后重跑。

终点v1误删取消后的旧弹性Load，v2又只按普通size范围寻找PA来源、漏掉CBO整行；
两器拒绝和原源码保留。v3改正的是独立重建逻辑，不改任何原始输入/输出、
严格比较或旧prefix语义核心；随后生产者复核进一步限制了这些观察的正常域声明。

## 3. 用例前新合同与尚未接入的正确代理

[正常CBO补充合同](../contracts/lsq-normal-cbo.md)先于新流量修正定义了QB/全mask/
wline、同STA真实RAW、零字节/WB、普通Store合法头许可和完整同槽完成要求。

新增而未改旧启动文件：

- `tests/lsq_wrapper/normal_owners.py`：显式`NormalCboStore`，只规范同一UID/ROB/SQ
  的真实CBO包，保留value/opcode；拒绝非CBO、uncache、跨页、size3或未对齐的
  直接普通生产者构造，不能静默把这些接口边界当普通数据流。
- `normal_mixed_owners.py`：新的opt-in `NormalMixedOwners/NormalJointOwners`工厂；
  原8类权重、完整随机失败域、SID立即复用、错误/恢复和strict fixture不变。
  旧混合/联合用例不改写，后续用新正常域用例/目录明确分开，不能追溯提升旧结果。
- `results/static/lsq-normal-cbo-v1/report.json`：**256静态输入配置/7非法包拒绝**，
  通过完整603-pin codec并同时核对SQ和RAW公开视图。该检查**没有原生DUT/功能/
  覆盖证明**，尚未接入上述新正常域的实际测试。首次直接python执行因工程根
  不在PYTHONPATH而未加载，使用项目明确`PYTHONPATH=.`后完成；未将导入错误当
  RTL问题。

当前38DUT/1828例统一回归08仍使用其冻结启动源。结束前不改这些文件，完成后
先捕获源再重做原1828接口结果/覆盖门禁，并注明本准入限制。随后新正常域
原生用例/独立producer＋UID审计、全域随机/恢复、公平以及最终请求证据审计仍
必须实施；不以本审计或静态256配置关闭目标。

```sh
python3 -B tools/audit_lsq_cbo_producer_v1.py
python3 -B tools/audit_lsq_mixed_terminal_v3.py
PYTHONPATH=. python3 -B tools/check_normal_cbo_v1.py
```
