# 真正串行许可下的CBO与完整类型混合：失败保留，不替换整体目标

**结论：CBO包及NoSpec/BlockBack门禁通过，功能仍NOT_PASS。** 不等于混合流的完整LDU准入，后续[LDU路由纠正](lsq-ldu-rar-routing-20261019.md)及[新全类型混合](lsq-ldu-mixed-20261019.md)限定其范围。本批不仅满足QB/fullmask/wline，
还从真实Decode/Dispatch/ROB约束检查NoSpec/BlockBack，没有以“LSQ物理空”代替
“ROB空”，保留老普通Store已退休但Sbuffer尚未消费的合法故障域。

## 1. 实际运行与原件

| 冻结运行 | 结果 | 启动/结束源 | 公开证据 |
|---|---|---:|---|
| `lsq-serialized-cbo-01` | **12例：7 PASS / 5 FAIL** | 404 | `serialized-cbo-audit-v1.json` |
| `lsq-serialized-mixed-01` | **原8种子：8 FAIL** | 408 | `serialized-mixed-audit-v2.json` |

均实际Picker+xreactor，结束立即捕获，所有启动/结束SHA一致；没有skip/xfail，
没有目标RTL/Chisel改动。原size3接口版、仅QB包修正版及其NoSpec拒绝历史均保留，
不追溯改旧结果。合同在实现前建立，见[串行CBO](../contracts/lsq-cbo-serialized.md)、
[完整类型随机](../contracts/lsq-serialized-mixed.md)。

## 2. NoSpec/BlockBack与实际字段，两层都核对

定向例**522个CBO owner/522次STA**，混合例**33个CBO owner/34次STA**（含retry），
都由实际dispatch/STA/ROB epoch重建，**NoSpec和BlockBack违例均为0**。每个CBO
QB4/FFFF/wline1/对齐也与两张603实驱pin图一致。

源码链为`Opcode.scala:676-680` → `DecodeStage.scala:160-161` →
`Dispatch.scala:861-885` → `Rob.scala:198-205,512-524,623-625`，不是仅相信代理命名。
原03轮716个CBO owner全部BlockBack违例、204个NoSpec违例的拒绝仍保持。

## 3. 全槽原UID真正完成，且正常故障域没有删掉

两个严格全输出全槽例完成**64槽×4opcode×2STA=512组合**：512原CBO、512个在
它们实际WB/退休之后才分配的年轻Load全部完成。384 Cache req/resp、128次原
16字节zero、512次原WB与队列释放，不是提前同拍派年轻Load。

其余10例分为两个strict zero例和8个明确协议探针。probe始终
`checked=false/full_cycle_reference_compared=false`，不借探针补全输出参考。

### 3.1 原Cache错误在实际WB.fire丢失：3 FAIL

单独正常CBO，原Cache响应**tick44**的denied/corrupt分别为(1,0)/(0,1)/(1,1)。
WB背压3拍后，**tick52实际WB.fire均变为(0,0)**。独立审计只依据这个原响应和
实际fire，三个0拍背压对照均保留原错误并通过。没有年轻Load干扰，也未让错误
CBO虚假架构退休；这些是既有WB保持问题的真实正常生产者域补证，不另虚报新缺陷。

### 3.2 老Store已ROB退休但仍SB背压：zero真实错误与strict前缀分别证明

先独立分配/执行老普通Store，再让它从ROB退休但保持实际Sbuffer未消费；此时
ROB空，单独分配正常zero，没有年轻指令。合法NoSpec/BlockBack均满足，未加
`read==head`限制。

- strict例在**tick80**捕获flush应为0却变1，只证明该阶段，不给它伪造后续WB。
- 独立protocol-only例真实消费老Store，老SQ在**tick82**释放；zero在**tick84**
  WB.fire、**tick86** SQ释放，但**自己的zero16实际消费为0次**。原UID与每个
  side effect均从公开引脚重建，普通FAIL保留。
- 没有旧Sbuffer的strict/protocol两个对照都真实完成自己的zero16。

## 4. 原8种子、八类型/权重的合法串行随机，仍8 FAIL

新生成器不排除CBO。一旦抽中CBO而ROB非空，就保存类型意图并停止分配、继续
服务旧事务；不重抽更容易通过的Load/Store。原八类型、权重、split、VA别名、
SID归还后立即复用、错误、重放和共享恢复保持。源策略审查不冒充未接受意图的
运行时完成证明，实际FAIL前缀也不补成完整600拍。

独立**7677条记录 / 430 UID=214完成+166取消+50失败停留**；39次shared恢复，
69总线接受=69真实响应，另8笔Load数据已返回未消费。1187 grant/1177原slot反馈
差额按实际取消/失败在途保留，不伪造完成或全部取消者同槽复用。

| 种子 | 实际终点 | 观察范围 |
|---|---:|---|
| 28928 | tick11222 | 完成600随机+5000实际fair边沿，但18原UID未完成；外层有界性FAIL，所有周期比较一致，不当坏RTL pin |
| 28929 | tick1198 | 原SID响应error=1，s1异常字段变0；具体UID89/SID7/原tick1184响应 |
| 28930 | tick320 | 原Cache corrupt在valid WB保持阶段丢失 |
| 28931 | tick808 | 原Cache denied/corrupt在valid WB保持阶段丢失 |
| 28932 | tick1106 | 原Cache denied/corrupt在valid WB保持阶段丢失 |
| 28933 | tick200 | 原Cache denied在valid WB保持阶段丢失 |
| 28934 | tick280 | 原Cache denied在valid WB保持阶段丢失 |
| 28935 | tick220 | 原Cache corrupt在valid WB保持阶段丢失 |

六个混合Cache终点均在ready=false的有效WB保持阶段，**没有给这些前缀声称后来
实际WB.fire**；实际fire错误另由第3.1节三个定向例证明。28928的18个未完成者仍
需逐UID定位公平/依赖原因，不把5000拍投入时间、共同reset或新绿色例当排空。

## 5. 覆盖及整体边界

串行CBO定向自身本体109/114、闭包**28196/59602**；串行混合自身本体114/114、
闭包**36737/59602**，不是完整LSQ覆盖。未运行的Load队列/总线/恢复枚举不能
因为此特定定向目录而宣布整个功能不存在，后续完整范围仍须逐行核对。

此前34例的自身raw覆盖56989→57394/59602、+405逐行映射见
[生产者域/端点报告](lsq-normal-domain-20261019.md)；其中CBO命中仍受原串行拒绝
限制，不与本批数字或独立叶子拼接。完整38DUT回归08已实际1828例1658/170，
新增54例须扩大到新1882范围统一重跑/审计，不能改写旧回归。

完整正常联合容量与CBO分阶段、随机fair未完义务、RAW等其余exact128域、恢复
交错、扩大后的参考影响回归及最终请求→产物/失败/未验证边界审计仍必需。
目标active，三个STRESS总项继续未checked，不以本批正常准入或局部完成关闭目标。

```sh
python3 -B tools/audit_lsq_serialized_cbo_v1.py lsq-serialized-cbo-01
python3 -B tools/audit_lsq_serialized_mixed_v2.py lsq-serialized-mixed-01
```

混合审计v1合并报告时与raw helper重复terminal_scope键，原样TypeError拒绝；v2
仅改报告标签observed_failure_scope，全部实际轨迹/语义核心不变，旧器保留。
