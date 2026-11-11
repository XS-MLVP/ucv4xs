# 正常混合CBO调度：保留全域程序类型，等待真实串行许可

此合同在新代理/用例前定义，补既有八类型随机的生产者时序情形；原种子、
size3接口版、仅QB包修正版及全部失败产物保留，不用新生成器追溯改写它们。

1. 仍使用原8种子0x7100..0x7107和全部八类型/权重：cached/NC/MMIO/IO Load、
   普通/NC/IO Store与CBO。保留普通Store split/VA别名、立即可复用SID、错误、
   多因重放、背压、branch/RAW/异常恢复；strict逐拍参考与独立UID义务不变。
2. 一旦随机程序的下一个类型是CBO，若实际已分配ROB非空，必须**记住这个意图**
   并停分配，继续服务原已接受事务；不能重抽一个更容易通过的普通Store/Load。
   同拍已有老分配时CBO也等待下一次真正空ROB，而不是偷塞到该batch尾。
3. 真正ROB空时单独分配CBO，QB/fullmask/wline不变；BlockBack期间不分配更年轻
   指令，直到原CBO实际WB后按原ROB退休条件退出，或原shared redirect取消。
   老普通Store可以已经ROB退休但仍在真实Sbuffer中，**不要求LSQ物理空**。
4. 600拍原随机后仍保留fair阶段。若还有尚未接受的CBO意图，先排空原已接受
   事务，再真实分配这个相同类型的CBO并服务完成；不悄悄遗失意图，也不把尚未
   分配意图算成已完成UID。随后原取消UID同物理槽新UID完成检查保持。
5. 新严格失败仍立即普通FAIL，不捕捉或掩盖失配；完整600/fair/恢复只有实际运行
   与独立producer/UID证据满足才能声明，不能凭新代理命名或CBO门禁静态通过验收。

NoSpec/BlockBack源码依据及合法retired-old-Sbuffer边界见
[串行CBO合同](lsq-cbo-serialized.md)。这不是选择更保守域来替换目标：等待是实际
Decode/Dispatch/ROB施加的许可，CBO类型不删，老Sbuffer失败域也不排除。
