# 非满/跨环 Store 窗口：Load 独占上界、较年轻别名与字节地址低位

本合同在新增实现前建立。它补充当前真实 PSQ/SQ 的 Forward 低半窗口选择、
地址 bits[3:0] 及完整 Wrapper 的实际程序顺序，不替代 strict、跨页、总线、
恢复或原有失败。固定开源 RTL、Picker native build、X Reactor 与独立模型不改。

## 语义功能点

| 情形 | 人类可读的行为和 oracle |
|---|---|
| `FWD-WINDOW.prefix_byte` | Store 队列的实际尾部可能已包含较年轻 Store，Load 的 SQ 上界却是它派发时的独占位置。每个有效查询只选择该上界前的较老、就绪、同地址字节；不能把物理 bank 中较年轻同址字节当成结果。|
| `PSQ-WINDOW.prefix_byte` | 由真实 STA/STD 写入完整 PSQ。非满及移位满窗逐项检查各 Load 的独占前缀；末项与首项同 VA/PA 但数据不同，末项已真实写入时，首个 Load 仍读首项，末项之后的 Load 才能读末项。|
| `SQ-WINDOW.prefix_byte` | 实际 dispatch→VSQ→PSQ 保持完整 Store 身份。Load 查询前禁止 ROB 许可和 Sbuffer 消费，检查完成后只通过真实消费和出队释放；同物理槽跨正常生命周期复用不能串代。|
| Wrapper 复合情形 | 完整 LsqWrapper 中真实交错派发 Store、紧随其后的 Load，每个 Load 的 SQ 上界来自实际 Store 派发前缀。所有 STA/STD 到达后才执行 Load 查询，包含“较年轻别名已经写入”的负对照；按实际原 LQ/ROB/uop 执行 S3 并最终正常释放。主目录沿用既有 `LSQ-FORWARD.aligned/youngest/sqid/wrap`，字节 mask 另由公开 oracle 检查，不改变原 82 项分母。|

## 合法轨迹与时序

- 正式用例连续运行窗口 `[0,63)`、`[63,127)`、`[127,191)`、`[191,254)`，
  最后 `[254,256)` 正常完成；最多 64 个真实 Store 同时活跃。四个长窗口
  既有非满池也有满池的跨环边界，结束位置不局限于物理槽 0。
- 每个 Store 是普通 1B Store，无跨 word/page、NC/MMIO/CBO 或异常。输入
  VA/PA 的页内偏移相等，offset 0..15 循环；每个字节值取自外部 producer
  记录。一个窗口内地址互异，只有末 Store 显式使用首 Store 的相同地址，
  但字节值必须不同。
- 第 i 个 Load 的独占 SQ 上界是该 Store 的绝对 position+1。即使物理 bank
  已经写入整个窗口，该 Load 也不能看到后面的 Store。测试末 alias 的早/晚
  两次有效响应，不能仅依赖内部选择信号来宣称程序顺序正确。
- S0 查询、下一拍 S1 PA，随后有效 S2 必须无依赖/别名 replay 标志，mask
  仅含所请求的一个 byte，返回该 byte 的原值。无效 mask 对应的数据为
  don't-care，不比较、不当作持久数据功能证明。
- Forward/PSQ/SQ 每个 Store 在三路查询口都检查有效响应。完整 Wrapper
  分三条原生测试分别选择 lane0/1/2；每个有效 Forward 查询绑定一个真实
  已派发 Load UID，不用复制一个 Load 同拍占三条真实执行流水。
- Wrapper 每个 Store 与其 Load 分别使用程序上连续的 ROB 身份，实际按
  Store→Load 顺序派发，再派发后继 Store。最大活跃 ROB 范围为 128，
  小于 160；下一窗口在旧 Store/Load 全部正常完成后开始，指针按公开编码
  自然跨环。每个 S3 保持原解码字段、SQ、LQ、ROB、VA/PA，不能改成新 UID。
- 查询时保持 Sbuffer ready=0、旧 ROB 头不前进；后续真实消费者接收原
  字节、mask、地址，真实出队反馈才计完成。各窗口间不 reset、不取消。

## 配置和 don't-care 边界

本配置物理 SQ=64、虚拟 SQ=128、双 flag 编码周期 256。`Low` 表示环形年龄
窗口的一段，不是地址低位；两者分别核验。若某最高位选择点在固定 RTL 中
恒不可选，必须另给精确源证据，不能因本用例未命中就自动排除或改分母。
本合同不宣称覆盖所有依赖身份、所有大小、越窗、禁用反馈、跨页或非法流。
fixture 初始正常 reset 与旧恢复/异常合同不删减；所有历史 FAIL 保留。

## 覆盖闭环与保留产物

1. 每层 fresh baseline/after：旧节点全部保留，同 source aggregate、build、
   line/toggle/branch 点全集，分别比较三类差集及 LCOV 源码行。
2. compact witness 保存五个窗口的公开 head/tail、实际物理槽、offset 集合、
   查询数量、首/末 alias 的不同字节、原 Store/Load 完成数和消费摘要；
   不保存逐拍 JSON、波形、完整源码副本或参考模型内部状态。
3. 真实完整目录/贡献范围重跑按 native build 的全部实际贡献者选择，不仅
   `tests/lsq_wrapper` 目录；既有 730 个 Wrapper 原贡献者及后续用例不得漏跑。
   历史失败的归一化全文要保持，新增失败原样记录，不 skip/xfail 或改 oracle。
4. 新结果不回填 regression15 的分子、缺口库存或历史 FAIL。功能检查、覆盖
   增益与静态配置边界分别报告，不能因任一子集通过而关闭整体 LSQ 目标。

## 正式窗口补强依据

前两次探测使用 63/63/63/63/4 的旧窗口。源 `ForwardModule.sv:2907,9304`
表明 Low 候选受 `((1 << deq.value) - 1)` 限制；欲让物理 slot62 成为
跨环的较老 Low 候选，需要 head.value=63 且窗口同时包括它，恰好达到
64 项边界。因此正式窗口加入两个 shifted-full 64 项情形，保留非满池与
年轻同址负对照，不能把仍可合法命中的 slot62 当成配置不可达。
两次旧探测产物及检查器失败保持，正式 baseline/after 均采用扩充后的合同。

## 同址消费归属（首次探测后的独立检查器补强）

首轮 `store-prefix-byte-probe-01` 为 4 PASS/2 FAIL；通用 PSQ/SQ actor 在真实
Sbuffer 消费时仅按 VA 查找 owner，把合法重复 VA 的末项误匹配为首项，触发
“同一 UID 的 part 重复”断言。该产物保留，不宣称是 RTL 失败，也不把地址改成
唯一值来删掉较年轻别名情形。

本补例的消费者改为按外部原始程序顺序依次绑定真实 Sbuffer fire，再独立
核对该 UID 的地址、mask、字节与正常出队 +2 tick。只有真实 fire/出队后才
更新外部 actor 的消费/完成台账；不修改通用 actor 或参考模型、不替换/屏蔽
每拍模型比较、不改已发行 producer record。后续仍须保留两个原有失败及
整个原测试范围；修正的是本例对重复地址的消费归属能力。
