# LSQ摘要运行性能：不减语义检查的对照合同

本合同先于性能插件、优化和性能DUT运行。它服务于原LSQ验证闭环，不替代剩余
功能/三类覆盖率补例，也不授权修改固定RTL/Chisel、共享参考或冻结actor。

## 已有观测及待证假设

- `load-response-contributor-regression-02` 实际1457节点1265 PASS/192 FAIL，总
  2274.17秒。三个精确S4长例各360程序、1734UID、20515检查周期，均PASS；
  两个旧mixed FAIL实际用尽5000周期公平排空。正常长例与失败等待分别处理。
- 3471份journal摘要记录合计47,906,108,694字节在内存中序列化/哈希，保存逐拍
  trace为0。Wrapper最长单例约2.274GB。`asdict`、模型、采样、JSON和哈希的
  各自时间占比尚未由profile证明，不能只因字节大就声称已找到主要瓶颈。

## 性能观测功能点

| 功能点 | 验证义务 |
|---|---|
| PERF-PROFILE | 显式启用插件，仅在指定真实用例call阶段cProfile；只保留调用数、独占/累计时间Top列表和时钟/CPU时间，不保留profile二进制、逐拍数据或波形。 |
| PERF-SEMANTICS | 对照使用原节点、原严格fixture、原DUT/seed/actor/参考和原全部检查。冻结源SHA不变，旧FAIL仍FAIL；不缩短排空等待、不增加reset、不改变数据及场景。 |
| PERF-IDENTITY | 性能优化先为opt-in，不能默认启用；同节点前后records/serialized_bytes/SHA与所有公开/check/actor摘要相等，三类native完整点键与计数相等；不只比hit数。 |
| PERF-CORNER | 小型对照至少含正常Load/Store、原必保留strict失败、Uncache响应错误和S4故障恢复。优化的输入域/异常路径若无证据则保持未验证。 |
| PERF-RESULT | profile会扰动时间，不把profile时间当正常加速比。实际速度用无profile的同选择前后对照测量，明确机器竞争/样本量，不能据短例外推整轮保证。 |

## 实施边界

1. 先完成已有Load响应八build和全链索引；不重跑已完成1457节点。
2. 先用极少原Wrapper节点做profile，再根据真实热点选择优化。不安装/替换锁定
   工具，不减少检查，不修改冻结模型/actor来逃避SHA保护。插件必须可撤销且不
   污染未启用运行；输入/输出/异常值不得因插件不同。
3. 字节相等是强控制；若未来需要改变摘要格式，必须另立版本和独立等价验证，
   不将新格式SHA与旧格式静默等同。本轮优先保持完整旧字节流。
4. 保留全部新/旧失败、真实raw dat、JUnit、manifest和命令，默认仍无逐拍JSON、
   波形或新完整源码副本。每次fresh记录源码聚合，source/build/点集逐对比较。
5. 后续若优化本身不满足等价，保留失败证据并不采用；不能为了提速把原语义
   检查改成统计、smoke或只验证绿例。完整38-DUT统一回归与未证明边界仍开放。

## 首批profile后的具体试验（实现前追加）

两个原Wrapper节点（普通Store/Load正例、原strict-full-pool FAIL）实际profile，
结果/6份公开流摘要与完整after-02完全一致。strict例profile的JSON encoder独占
约0.136/9.55秒，不支持“JSON是最大热点”的判断；startswith约0.925秒、重复
Load/Replay/Wrapper encode累计占用明显。profile不代表未插桩时间占比。

下一试验只缓存四个纯接口编码函数（Replay/LoadQueue/StoreQueue/Wrapper），
不缓存参考输出、DUT引脚、反馈、model.connected或任何可变业务状态。

- 显式插件选项开关；每例安装、每例还原，不改变未启用默认运行。
- 仅深度不可变的固定`lsqverify` frozen dataclass、tuple、int/bool/str/None输入
  可缓存；其他输入始终走原函数。key为完整输入值，容量64且逐例清空，不读取
  DUT/model，不按valid掩盖字段。原函数在miss完整执行所有形状/宽度/冲突验证。
- 返回独立dict副本，不让调用者修改污染缓存；无异常缓存。字典key插入顺序、
  数值、JSON字节保持。插件卸载时还原所有被替换的纯函数别名。
- 原invalid输入的异常类型/文本也需与原函数一致；可变输入和返回值被修改的
  对照需验证。单测不代替真实DUT正/负/错误/恢复对照。
- 原文中“先处理摘要开销”改为按实测先消除重复纯转换；完整字节摘要仍保留，
  不声称已优化47.9GB序列化本身，也不对整轮37.9分钟作线性加速承诺。
