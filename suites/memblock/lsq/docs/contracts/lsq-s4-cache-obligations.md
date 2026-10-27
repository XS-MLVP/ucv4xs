# S4的两段Cache miss要各自偿还外部义务（补例前）

原66定向中已真实区分精确ROB头trap与LQ释放，但继承的Cache响应服务仍仅核最终
Replay MSHR字段：head nack/tail miss可能在tail缓存补完之前就重试成hit，head miss
路径还重复四拍wrong-ID脉冲。输入接口压力是真实执行，却不足以证明闭合的外部
Cache生产者程序。旧61 PASS/5检查器FAIL原件保留，不追溯修改结果或称全部正常域。

新增S4P-CACHE-JOBS（整段外部依赖关系的遗漏，不是多枚举一个bit）：

- 每段真实S2选择miss/handled时建立外部Cache job：head MSHR3、tail MSHR9。它是
  在S0前选择的外部DCache模型假设，不是本DUT可观察的MSHR内部状态。
- 实际LSQ refill输入必须有原job，每个job只偿还一次；head nack/tail miss先真实
  refill9，再允许tail重试成hit，不能只因最终cause是nack就忘了tail miss。
- 新增both-miss：tail9先偿还，原head3仍阻塞，不允许grant；然后head3真实refill，
  原owner才grant/原slot反馈。这样同时检查head原因与MSHR选择，而非借字段默认值。
- head miss/tail nack的wrong9只发一次，明确属于外部独立prefetch job；不虚构一个
  CPU Load UID，也不冒称本DUT或native DCache执行过prefetch。之后几拍无refill，
  原head3仍不得grant，最后真实偿还3。
- 所有原Cache job在终态归零；取消/trap不能把外部未偿还义务当作正常完成。

新72例保留原66合法情况并在同页/跨页三lane补both-miss6例。另修检查器valid0时
误要求Forward payload清零的问题，仅忽略无效payload，valid1时mask/危险标志检查
继续；不改DUT、共享参考、比较mask或旧结果。默认只小摘要、0逐拍JSON/0wave。
