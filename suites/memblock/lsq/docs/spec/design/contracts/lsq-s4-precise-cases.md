# 普通LD的S4精确ROB头恢复：本轮情况与检查（实现前）

继承`lsq-s4-precise-rob-head.md`，DUT仍仅真实53文件LsqWrapper，不扩大为native
LoadUnit/TLB/DCache/ROB UT。原始八类型八种子/全部FAIL/回归12范围不变。本轮只补
被旧“异常WB就立即trap”遗漏的完整源关系，不能代替完整随机。

## 固定TLB/PMP输入域

普通operation6、hyper=0、nonleaf=0，无PBMT NC/MMIO，无SFENCE/权限变化；准确S3
DCache错误仍由固定配置关闭。S1的PF是TLB权限异常并kill Forward/DCache，S2的AF
来自CSR已启用的有效tag_error。无异常段的nack/miss在S0前选择，重试清除一次性
nack/miss但保留PF/AF。外部事件是生产者边界假设，不伪称native上游执行。

稳定同4KiB页必须有一致PF结果。因此同页单侧PF/AF-PF权限差异不能仅凭两个任意
TLB返回值自封正常域：单侧PF及AF/PF优先只放跨页，两段PF另覆盖同页与跨页。此为
**该固定稳定TLB profile的准入边界**，不是把带权限更新/SFENCE的整个LSQ情形证明
绝对不可达；后者依然是未生成边界。旧plain01不追溯改写，其同页PF差异亦无本域准入。

跨页：原13关系加both-PF，共14模式×3lane=42例；同页：7个无PF模式加both-PF，
8模式×3lane=24例，共66例。无PF的3C→40也是跨Cache line，允许不同tag错误/
miss/nack。跨页tail PA不连续，同页PA保持页内偏移。不是skip或删除旧用例。

## 独立微架构行为与检查

1. 真实较老Store、较老未执行Load、S4目标和年轻未执行Load按程序序dispatch。S4
   同lane连续head/tail，分别S1 PA、S2真实RAR/RAW query、S3保存与S4最终输入。
2. 从事先选择的外部PF/AF/nack/miss独立推导异常head优先、写回与Replay的独立性、
   head原因优先和另按headMiss选择MSHR、最终head PA/VA/mask与异常fullva/gpaddr、
   各段last/older revoke。检查器不导入控制器的fault/cause/WB答案函数。
3. headReplay/tail异常而无WB时不得trap，须真实grant/原slot反馈后再产生fault WB；
   错误tail MSHR refill不能代替原head miss解除。grant异常位清零/fullva回vaddr按
   Replay实际源码分别检查。
4. 原fault有WB后，先真实执行较老Store STA/STD/S2与较老Load S0→S3并完成，再把
   pending推进且停在原fault ROB。此时才flushSelf；老Store已退休但尚未Sbuffer消费
   合法，不能额外要求SQ空。
5. fault无Replay时可能在trap前已释放VLQ；不得当普通成功或假称被LQ取消。fault仍
   Replay时LQ/LRQ随trap取消。真正年轻victim两种情况下都取消；恢复按实际未释放
   集合计算。每个真正取消的结构槽均由新UID正常S4完成。
6. Sbuffer原字节消费、延后一拍SQ释放、Load实际结构deq、异常WB+头部trap、纯年轻
   取消、grant/反馈分别记账；终态UID互斥守恒，禁止把返回credit当普通成功。

默认不写逐拍JSON或wave。独立检查器逐次在线检查公开输入/实际输出，只交付每例
少量UID终态/恢复/计数汇总；原生fixture仍完整比较458输出。汇总不是事后重放全部
新逐拍历史，source门禁与native LSQ效应须分开表述。首轮后仍逐条分类原DA、补真实
代际情形再跑，不用body行满或少数定向绿色验收整个目标。
