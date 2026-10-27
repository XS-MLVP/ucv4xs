# 源正确的联合容量转移、恢复与串行CBO（实现前合同）

固定开源893e1580b、真实53文件LsqWrapper、Picker+xreactor与全部严格公开输出检查。
这是补充定向，不替换原8种子/八类型/错误/别名/split随机，不勾选STRESS总项。
旧joint04六PASS的实际效应和DA保留，但`joint-producer-audit-v1.json`已拒绝其正常
准入：初始六快照合计720次Replay无revoke、624次非原lane下一拍S3、96次缺S2。
因此不能要求正常标量Load同时长期占有原RAR记录与自己的Replay等待项来凑峰值。

## 1. 功能与源关系（先定义后用例）

| 功能 | 人可读的行为与必要检查 |
|---|---|
| JPH-SHARED | 未返回的最老NC使VLQ头保留；较年轻命中Load虽已执行也未释放LQ信用，RAR记录不能提前丢失 |
| JPH-AGE | Store前的Load没有未来Store依赖，不分RAW；Store后的Load遇真实老STA缺口才占RAW；不靠任意外驱rawFull |
| JPH-STAGES | 每个请求真实S0 Forward→S1 PA→S2 RAR/RAW→同lane下一拍S3；普通Replay精确revoke与不写回，首次NC/原bypass再执行分别处理 |
| JPH-TRANSFER | 第一容量快照RAR96/RAW56/LRQ24/SQ128/LQ120/UE16；原NC真实回包/原slot反馈后释放112个LQ，再派112新Load形成LRQ120/LQ120，RAR回收而非假装全池长期同时满 |
| JPH-WINDOW | SQ虚拟128但只当前64物理窗口STA/STD；头Store地址缺口阻止地址指针；第二64必须等真实SQ消费释放物理窗口后执行 |
| JPH-FAIR | 原owner完成、ROB退休、Replay grant/原slot反馈、Sbuffer消费、SQ释放、bus ack/resp分开记账；一代所有义务偿还后才称排空 |
| JPH-CBO | CBO0..3不预塞满池程序；真实ROB空时单独分配，直到退休/取消才允许年轻Load；正常QB4/maskFFFF/wline包不改 |
| JPH-RECOVERY | 第一满快照redirect或共同系统reset中止后，同物理槽新UID在后续真实完成；redirect必须偿还16个旧请求真实响应，不伪造消费；共同reset显式中止外部义务 |
| JPH-EPOCH | 三完整代覆盖ROB640/SQ256/LQ240回绕；采用单一绝对ROB与Load-exclusive SQ边界，不能把落后128解释为年轻128 |

## 2. 单代程序与容量转移

程序序是`16 NC Load + 40 cached Load + 64 Store + 64 cached Load + 64 Store`，
共248个不同ROB owner。地址各自唯一、8B对齐、无异常/额外cache miss，外部响应
显式clean；这些是定向正条件，不是过滤完整随机域。只执行第一64 Store中的1..63，
保留SQ头0地址缺口；不提前执行第二64。所有Load沿固定源流水执行，先前40cached
的exclusive SQ边界为0，后64为64，所以可保留96RAR但只56RAW；其余8cached及16NC
等待真实Replay。留足流水稳定拍后，用公开历史重建第一快照，不能信actor汇总。

然后真实响应/唤醒/再执行原16NC；不执行Store头、不接受其他Replay grant。
RAR满时较年轻NC replay可能再次发起Uncache，原UID已消费旧job后须承担新job，
转移阶段持续接受/方向ack/响应全部新旧义务，不能只回原16包后关闭外部请求。
VLQ逐原UID释放112个Load（16NC+96命中），剩8个容量等待。补112个新cached Load，
exclusive SQ边界128，处于真实未执行的128老Store之后；RAW池依旧占56，这112个
Load沿原生流水进入Replay。于是LQ和LRQ都120，ROB最老Store到tail跨度304<320。
这里显式使用`tests/sq_endpoint`的向前exclusive128 opt-in参考；共享`sq_after`
半环拒绝与全部共享模型不改，准入必须核对真实程序序、SQ占用和代际。

最后连续公平服务真实Store窗口/Load再执行/总线，直到所有原UID、槽与外部义务完成。
CBO0..3分别在真实ROB空时单派，完成退休后才派年轻cached Load；不能借减少容量、
删除CBO、要求原Sbuffer先空或跳过错误反例伪造验收。旧老Sbuffer/zero/WB故障例仍保留。

## 3. 执行与证据要求

两个payload/稀疏dispatch种子×普通/redirect/共同reset，后续各三完整代。逐拍独立
审计核验源关系、两类快照、公开请求/响应/原UID守恒与回绕；没有公开RAW记录slot时
只映射完整输入signature，不虚构物理slot。审计需要负对照拒绝缺revoke、伪S3更新、
提前CBO与虚增快照。按本目录自己的原DA逐行分类，比较首轮和补例真实命中，不混用
旧59595行或叶子分子。失败普通保留，初始化/驱动错误与RTL FAIL分别记录。

**02实测后的补充情况**：持续接收新NC义务后，原6例全部在真实SID复用的bypass s2
原字节比较失败，普通FAIL保留。增加固定响应节拍`period8`的6个正条件对照，不替换
`period1`原6例；SID仍在resp后立即可ack给新job，没有延长到旧Load消费，也没有查询
消费状态控制回包。12例共同重跑，正条件即使完成三代/CBO也不抵消原SID反例或通过
完整随机。新的节拍只用于继续验证其后未到达的容量转移、公平Store窗口与CBO阶段。
