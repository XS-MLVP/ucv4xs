# LSQ-BUS-OWNERSHIP-001：旧NC响应把另一笔串行IO事务错误解锁

**结论：已确认的RTL bug；未完成修复复测。** 固定提交`893e1580b705d81f113c30c7a05734e09a08050e`。6个原失败节点属于这个根因。

## 1. 用一句话理解

一笔早先发出的NC Load后来才返回；此时总线正在等待另一笔IO Store。RTL看到“有响应了”，就把IO Store的串行锁释放，尽管IO Store自己的响应还没回来。

这相当于A窗口的业务办完了，却把B窗口的“正在办理”标牌撤掉。

## 2. 正常应该怎样工作

Load和Store共用一条Uncache接口。开启NC outstanding后，NC请求可以先发出并让其它请求继续前进；串行IO请求则要保持独占，直到**自己的**完成事件到达。

必须分别回答两个问题：

1. 响应数据应该送给Load侧还是Store侧？
2. 这个响应是不是当前持有串行锁的事务的完成？

把第一个问题答对，不代表第二个也答对。

## 3. 有问题的Scala实现

文件：[LSQWrapper.scala](../../../../XiangShan/src/main/scala/xiangshan/mem/lsqueue/LSQWrapper.scala)，**282–300行**：NC可以不占`pendingstate`，但之后任意响应都能清掉串行状态。

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/LSQWrapper.scala:282-300 -->
```scala
  switch(pendingstate){
    is(s_idle){
      when(io.uncache.req.fire){
        pendingstate :=
          Mux(io.uncacheOutstanding && io.uncache.req.bits.nc, s_idle,
          Mux(selectLq, s_load,
          s_store))
      }
    }
    is(s_load){
      when(io.uncache.resp.fire){
        pendingstate := s_idle
      }
    }
    is(s_store){
      when(io.uncache.resp.fire){
        pendingstate := s_idle
      }
    }
```

**311–325行**显示，锁是否打开直接控制新请求是否能发出；响应的方向只用于路由：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/LSQWrapper.scala:311-325 -->
```scala
  when(pendingstate === s_idle){
    when(selectLq){
      io.uncache.req <> loadQueue.io.uncache.req
    }.otherwise{
      io.uncache.req <> storeQueue.io.toUncacheBuffer.req
    }
  }.otherwise{
    io.uncache.req.valid := false.B
    io.uncache.req.bits := DontCare
  }
  when (io.uncache.resp.bits.is2lq) {
    io.uncache.resp <> loadQueue.io.uncache.resp
  } .otherwise {
    io.uncache.resp <> storeQueue.io.toUncacheBuffer.resp
  }
```

## 4. 怎样激励

1. 打开`uncacheOutstanding`。
2. 正常分派并执行NC Load A，接受其总线请求并返回编号确认，但先不返回数据。
3. 让已获正常许可的IO Store B发出，完成它的请求握手；B进入`s_store`，自己的响应暂时不返回。
4. 准备另一笔NC Load C，使它等待共享接口。
5. 此时返回**A**的原始响应，`is2lq=1`，而B的完成仍欠着。
6. 检查C是否被错误地允许发出。

| 时刻 | 正确行为 | 实际行为 |
|---|---|---|
| B在等待自己的响应 | 串行锁保持，新请求`valid=0` | 此时还正确 |
| A的旧响应返回 | 响应交给A，但B的锁不能变 | `pendingstate`被清成idle |
| A返回后的新周期 | C继续等待，直到B响应 | C的请求`valid=1`提前出现 |

已有对照把B换成NC Store，该情况下允许NC并行，不能把这个合法对照也判为串行错误。

## 5. 为什么不是非法“凭空响应”

测试中的A已经真实发出请求、取得确认，返回的是这笔原请求的响应，不是伪造B的响应。Uncache实际接收规则`Uncache.scala:365–384`也没有要求“任何另一block的IO到来之前必须排空所有旧NC”。

因此不能凭假设的外围互斥排除此场景。真正缺少的是当前串行owner与响应的对应关系。

## 6. 后果和修复方向

- **已经观察到**：B尚未得到自己的响应，`io_uncache_req_valid`已从应有的0变成1。
- **潜在后果**：破坏设备访问的串行约束、混淆后续请求/响应的完成顺序。
- **没有扩大声称**：本报告没有证明某个具体外设寄存器已经被写错，或者整核ISA程序一定产生哪一种错误。

修复时要保证只有当前串行事务的完成才能解锁；仅正确路由响应数据是不够的。还应覆盖反向组合以及同方向多笔请求的身份区分。

## 7. 复现和证据

- [test_bus_ownership.py](../../tests/lsq_wrapper/test_bus_ownership.py)，`test_old_nc_load_response_cannot_unlock_later_serial_store[serial-io-1-0]`。
- 直接首次失败：`io_uncache_req_valid` **实际1，预期0**。
- 测试保留真实LsqWrapper、LoadQueue和StoreQueue父子连接，不是把多个Python模型拼成DUT。
- 生成RTL：`rtl/lsq_wrapper/LsqWrapper.sv:1499–1508`。
- [全量裁定JSON](../../results/fail-source-adjudication-01/all-fail-verdicts-v1.json)中查`LSQ-BUS-OWNERSHIP-001`。

## 8. GitHub状态

未找到明确对应当前“旧NC响应误解锁后来IO owner”的报告。[PR #3732](https://github.com/OpenXiangShan/XiangShan/pull/3732)修的是非idle状态还接收新请求的旧问题；当前代码虽然只在idle发新请求，却会被**不属于当前owner的响应**错误变回idle，两者不是同一修复点。[PR #6592](https://github.com/OpenXiangShan/XiangShan/pull/6592)的fence/NC-store死锁也不是此根因。
