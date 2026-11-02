# BPU 自主流水的当前投影与接受合同

适用`public-893e1580b` + 完整DefaultConfig真实`Bpu`闭包。本合同是现有自主模型的端口和
生命周期迁移，不是所有预测器组合已完成的声明；参考模型边界见
[语义参考模型](semantic-reference-models.md)。

## 模型与实际观察分开

`bpu/model/pipeline.py`、`path_history.py`及各source-bank从reset和环境语义事件自主
维护stage/token/history、存储、选择和纠正。实际内部stage线、target、fold和表结果只作
actual，不播种/修补expected。`model/projection.py`显式列出当前物理投影，抽象纯模型的
完整flag/echo域另存，绝不从某张snapshot漏字段推断DCE。

当前保留公开prediction的PC/taken/position/override和metadata的resolve/redirect；没有
公开prediction target、perf PC/source、metadata ready或PHR flag。公共协议常量1是只读
valid-only语义，不进入driver payload/引脚所有权。三阶段内部target仍由自主模型逐拍
比较；S2属性绑定真实CommonHR/MicroRAS消费者别名，不能错绑`S2_s1Prediction`旧值。
内部比较不能计为已裁公开target/perf的证据。

MainBTB有4个真实way加1个victim、两组alignment。victim的公开metadata只保留hit/
position/counter，不伪造attribute。MicroTAGE只有4个训练fold(索引1/2/5/6)，baseStrong
被裁；模型完整历史仍独立保留，比较器显式投影而不是给actual补零。当前pipeline
lookup比较20个真正保留的fold，不沿用旧9组描述。

## 接受、身份与收尾

- 外部训练在DriveStable同步冻结valid/ready及完整payload，到紧接RisingEdge解释为同一
  输入接受；Rise-mode清valid后不能误判未接受或再次接受。模型的延迟学习仍按原独立
  可见性合同推进，不读DUT表状态修正时间。
- 每个训练/redirect先用已有真实receipt注册精确原owner，实际接受时逐字段对账。不按
  返回PC/low bits猜来源；相同公开编码可以属于不同原请求。PHR observer按输入fire/
  flush维护UID，流水receipt则用已登记S1 accepting tick和S3事件关联，见
  [PHR合同](phr-transaction-contract.md)。
- `AdmissionWindow`复用现有control driver：只在全部自主比较成功的真实S1事件后完成
  future，driver立即停止年轻接受。实际quota、同PC不同身份和漏采义务与调用次数分开。
- 退出前场景显式停止输入、排空S2/S3和已接受学习；关闭订阅不是完成。planned外部输入
  及未交付的admission window也必须对账。未知来源、坏target、错误tick或吞错保持粘滞。

## 原短表场景初始化

DefaultConfig的5/9历史下，旧连续启动可让多个尚未见分配的no-hit原请求依次退休，进而
分配table1。要求原short为table0的场景不能因此接受任意provider。

`entry_protection`及T短保护声明专属primer：Main-only合法建立fallback稳态；恢复与ready同时由
已有独立driver启动，按真实事件逐笔接受、完整排空后再发下一笔。五轮自然分配NT3并
完成三次正常减弱，交付新鲜NT0；不能在瞬时NT3时切回连续流。不能串行等redirect
pulse cleanup后才开ready，那会改变真正的read ancestor，纯模型步进可行不代表native
调用链已经对齐。此要求不替换generic长表准备程序。正常程序和冻结旧连续程序的错误
对照在`tests/bpu/scoreboard/test_entry_protection.py`，原table0断言不变。

返回opposition也须有界接受，否则等到S3才关ready时，年轻旧no-hit原件可能已分配
长表。第一笔reward只改变一次Ahead，不能再假设它自动把base饱和到NT0；需要一致但
错误的原件时，先用独立合法新原件建立NT base，再禁用早级学习并用正常resolve转Main。

T短保护还须维持正常T4/protection1种子，不能用准备期间已经饱和的T7或仅有NT原件
替代。Main-taken索引祖先配上fallback当前tag的真实查询窗口由并发RecoveryDriver
保留；串行等待pulse cleanup会得到另一个tag，从而学习/饱和错误身份。输入程序与
seed ledger始终独立，actual只用来比较，不从实时表状态挑一个碰巧能通过的种子。
positive older两条新声明路径的读历史固定为160/96（低5位同0，9位不同）；旧单fallback
路径160/352仍是合法控制，但若其长表已受保护，就不能冒领新长分配信用。

短表初始化控制的PASS不关闭`short_revisit`的同原件长分配/长优先/旧短错误消费者义务，
也不关闭positive保护或MBTB写回清理；它们仍须各自保留真实来源、完整前置与区分性错误
控制。`tests/framework/test_pipeline_projection.py`和`test_pipeline_native_obligations.py`
只给模型/真实native检查链信用，不是RTL mutation coverage或全部BPU功能通过。
