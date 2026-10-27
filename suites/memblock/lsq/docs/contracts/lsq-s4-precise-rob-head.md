# S4异常WB、VLQ释放与ROB精确trap必须分开（新增合同）

ROB853/898的异常flush受deqPtr/head控制，不能在更老Load未执行时，只看到年轻异常WB
就称为精确trap。旧S4-02/03和普通PF/AF plain01仍保留实际接口结果；旧flow的此关系
没有正常域准入。所有早先body DA、原UID效果和FAIL不是伪造，但不能补上该缺失关系。

VirtualLoadQueue239-248只要`!need_rep && updateAddrValid`就会标记完成并可能先释放LQ；
它不等待ROB异常trap。因此必须区分：普通Load执行完成、异常真实WB且随后ROB头trap、
陷入前已释放的结构LQ槽、尚有Replay而随trap取消的LQ/LRQ owner，以及真正年轻victim。
不能强迫已释放的fault槽一定被取消，也不能把其结构credit叫普通成功。

下一独立普通LD程序：真实较老Store+较老blocker Load+原S4目标+真实年轻未执行Load。
S4仍先经历正常同lane head/tail、真实S2 query/revoke，异常输入为可达PF/AF、普通
operation6/hyper0/nonleaf0。head Replay/tail fault无WB时必须先真实grant/原slot反馈。

有异常WB后，先实际执行较老Store STA/STD/S2、较老Load S0→S3并完成，再将ROB推进到
原fault（不能越过它退休），此时才允许flushSelf。老Store可以已经ROB退休但仍停在
Sbuffer，不能另加物理SQ必须空的限制。依当时实际未释放owner恢复LQ/SQ；所有真的
取消UID均需同物理槽新UID正常完成，原fault以fault-WB-and-head-trap单列。

逐拍JSON和wave默认关闭；后续先用运行时独立检查/小摘要与原生DA迭代。只有检查
尚未证明的源关系或定位唯一FAIL时显式打开有限定向trace，并限大小；不再把每轮
全量JSON当默认交付。该合同仍须真实实现/运行/审计，不能仅凭静态推导称完成。
