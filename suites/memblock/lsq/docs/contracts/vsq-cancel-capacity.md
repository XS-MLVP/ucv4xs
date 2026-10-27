# 大后缀取消：虚拟计数宽度、真实父级旧字节与同槽新UID

本合同先于新增用例。固定开源RTL/Chisel、原Picker DUT及X Reactor、共享actor和
参考模型不改。目标是当前VSQ/SQ的cancelCount可达方向缺口，不以单独叶子代替
真实StoreQueue或LsqWrapper连接；Wrapper已有计数命中也必须保持真实生命周期。

## 功能点

| 功能点 | 人类可读语义与检查 |
|---|---|
| `VSQ-REDIRECT.capacity_suffix` | 一次公开redirect精确取消4/8/16/32/64/128个年轻虚拟uop；保留前缀的exclusive物理尾不受取消计数宽度影响。所有被取消虚拟槽随后由不同新UID重新派发并正常退休，恢复stall窗口内不派发。|
| `SQ-RECOVER.capacity_suffix` | 4/8/16/32项年轻Store被取消但两个旧Store保留；满64项全取消使用flushSelf。取消前真实STA/STD执行、Sbuffer背压，旧被取消UID没有副作用；每个取消位置都被新UID占用、原字节真实消费并正常出队。|
| SQ头许可边界（保留FAIL） | 原探测允许ROB头等于首个Store，随后64项flushSelf时可能仍有旧preCommit输出在背压队列中；原输入轨迹和严格消费者继续运行，失败不得用未许可对照替代或屏蔽。另用ROB头保持在首个Store之前的独立对照验证未许可取消，两者结果分别报告。|
| Wrapper复合恢复 | 真实两分支同时恢复，16项部分取消/64项全取消与Load取消复用并发。幸存Load在其原Store取字节并原S3完成，被取消Load未执行；新Load使用被取消LQ槽，在新Store取字节并原S3完成。保留真实VSQ/PSQ/UQ/LoadQueue子树，不以接口mask或叶子结果替代。|

## 具体合法范围

- VSQ与SQ依次用物理起点0/62/126/190/254，取消数量4/8/16/32/64。
  小于64时保留两个uop，64时全取消；normal物理完成总318flow，取消124flow。
  SQ所有uop为单flow，窗口最大64个Store，窗间用普通Store正常完成推进，非reset。
- VSQ再在物理318处派发128个0/1-flow交替uop（总64flow），全部取消，再逐槽
  派发128个不同新UID、保持相同紧凑flow区间并正常退休。整例正常446个虚拟
  UID/382flow，取消252个虚拟UID；不声称父级128-uop零flow路径已验收。
- Leaf生产者自己维护绝对虚拟位置、物理exclusive end、ROB和UID；不从参考
  模型或DUT内部读取控制决策。参考模型只参与公开逐拍检查。PSQ代理只有在
  公开retired end可见后，才以每拍最多两个flow报告真实外部消费。
- 取消后允许重用被取消的ROB槽，但UID必须新分配；这样不人为制造超过160
  entry ROB半环的活跃年龄跨度。固定真实end与ROB slot比较，0flow仍占虚拟项。
- Wrapper两窗为物理0处16项年轻后缀（保留2个Store）、62处64项全取消；
  取消80个旧Store，正常完成126个Store及3个Load，取消2个Load，最大64Store。
  普通填充44Store真实完成，两窗间无reset。使用既有LSQ-RECOVER.partial/all/
  reuse和LSQ-FORWARD.sqid，不扩写Wrapper原82项功能分母。
- 所有被取消Store在取消前已执行且无Sbuffer fire，退休许可不越过它们；所有
  新Store真实STA/STD后才能退休/消费。每个被取消槽的旧UID与新UID建立一一
  对应，不把一个3flow新uop误称3个虚拟UID，也不只证明一个槽却声称全池复用。

## 证据与未完成边界

各层fresh baseline/after必须同源aggregate、同native build和三类点全集。
目标VSQ cancelCount[4..7]、SQ cancelCount[2..6]方向独立列示；Wrapper目标
原已命中，不预设覆盖增益。分别保留compact公开recovery/stall和每槽UID
复用/完成见证。探测发现SQ头许可取消失败后，原节点保留，另增一个未许可对照；
完整六build贡献范围从上一1173节点加4新节点预计1177，实际collect/manifest复核；
保留全部171FAIL全文、新头许可FAIL及原Wrapper主目录外41贡献者。

不回填统一regression15分母；不OR旧dat冒充完整执行；保持历史checker失败。
15850 release-wait、未复位退休计数高位、128-uop真实父级producer域、异常/
总线/跨页Load等继续开放。只保存摘要、compact witness、失败和覆盖证据。
