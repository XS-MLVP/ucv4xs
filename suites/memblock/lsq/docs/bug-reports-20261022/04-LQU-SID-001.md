# LQU-SID-001：旧Load还没取走结果，新请求就覆盖了它

**结论：已确认的RTL bug；未完成修复复测。** 固定提交`893e1580b705d81f113c30c7a05734e09a08050e`。29个原失败节点及2个独立补充探针失败指向这个根因。

## 1. 用一句话理解

Uncache总线的一笔请求完成后，其编号可以分给下一笔请求。但LQU还拿旧编号接收响应，导致新请求的结果同时写进了旧Load的存储位置。

可以类比为快递取件码：第一件包裹已送到柜子，取件人还没来；系统把编号用于第二件包裹时，错误地把第一格柜子里的包裹也换掉了。

## 2. 必须区分两种生命周期

- **SID生命周期**：Uncache给外部请求分配的编号。响应被交回后，可以归还并复用。
- **LQU entry生命周期**：LoadQueueUncache里保存某个Load结果的位置。数据可能已经返回，但Load要过几拍才来取。

“SID已归还”不代表“Load已经取走数据”。正确设计应该保留旧Load的数据，同时停止用旧SID接收新响应。

## 3. 有问题的Scala实现

文件：[LoadQueueUncache.scala](../../../../XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala)，**94–110行**：绑定SID后，直到取消、重新分配或Load消费时才撤销`slaveAccept`，没有在原响应返回时撤销。

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:94-110 -->
```scala
  /* enter req */
  when (flush) {
    req_valid := false.B
    slaveAccept := false.B
  } .elsewhen (io.req.valid) {
    req_valid := true.B
    slaveAccept := false.B
    req := io.req.bits
    nderr := false.B
    derr := false.B
  } .elsewhen(slaveAck) {
    slaveAccept := true.B
    slaveId := io.uncache.idResp.bits.sid
  } .elsewhen (writeback) {
    req_valid := false.B
    slaveAccept := false.B
  }
```

**190–197行**：一旦收到路由过来的响应，数据和错误直接被重写，没有检查本entry是不是仍在等待**原来那次**响应。

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:190-197 -->
```scala
  io.uncache.resp.ready := true.B

  /* uncache resp */
  when (io.uncache.resp.fire) {
    uncacheData := io.uncache.resp.bits.data
    nderr := io.uncache.resp.bits.nderr
    derr := io.uncache.resp.bits.error
  }
```

父级**437–440行**又只按SID匹配发送响应：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueUncache.scala:437-440 -->
```scala
      // uncache resp
      when (e.io.slaveId.valid && e.io.slaveId.bits === io.uncache.resp.bits.id) {
        e.io.uncache.resp <> io.uncache.resp
      }
```

## 4. 怎样激励

使用两个不同地址的正常NC Load，保证不是把一笔未完成的总线请求非法重用：

| 步骤 | 操作 |
|---|---|
| 1 | Load A：`PA=0x80000000`，实际发出请求，得到`SID=3` |
| 2 | A的响应实际返回，数据`0x0123456789abcdef`；等待其正常LQ唤醒，但暂不让A通过bypass取走数据 |
| 3 | Load B：`PA=0x80001000`，实际发出另一请求，合法复用已归还的`SID=3` |
| 4 | B返回`0xfedcba9876543210`，可另外带错误 |
| 5 | 再用A原来的LQ身份取走A的数据，检查A有效的s1/s2输出 |

**正确**：A仍返回A的数据和A的错误；B返回B的数据和B的错误。

**实际**：A的原地址/身份仍在，但有效s2数据已经变成B的数据；B的错误也可能污染A。128bit接口会把64bit原始响应复制到两个半区，比较时按该接口格式检查，不是把数据宽度误解成另一笔请求。

## 5. 为什么SID复用合法

`cache/dcache/Uncache.scala:493–499`在响应`resp.fire`时执行`updateReturn()`，结束该外部SID的占用。Uncache没有“等待LDU最终取走数据再归还SID”的接口。

因此不能要求测试一直扣住SID直到A消费；那会隐藏LQU把两种生命周期混淆的问题。

## 6. 根因和后果

1. A响应后仍保留`slaveAccept=1、slaveId=3`。
2. B绑定SID3后，A、B两个entry都满足父级的SID路由条件。
3. B响应同时送到两者，A的`uncacheData/nderr/derr`被覆盖。
4. A稍后执行正常消费时，输出的内容已经不属于A。

- **已经观察到**：A有效bypass数据错误；独立探针还区分了不同SID、先消费A两种对照，只有“同SID＋A未消费”组合失败。
- **潜在后果**：Load读到别的地址的数据，或者收到别的访问的异常状态。
- 这里证明的是原Load有效输出被污染，没有宣称完成了整核寄存器提交的ISA复现。

修复应在原响应完成后撤销SID接收资格，或用明确的“仍在等待原响应”状态门控路由/更新。不能把原Load的数据也随SID归还一起删除。

## 7. 复现和证据

- 原测试：[test_initial_probes.py](../../tests/load_uncache/test_initial_probes.py)，`test_sid_reused_after_response_preserves_old_unconsumed_data`。
- 独立探针：[test_public_contracts.py](../../tests/fail_review/test_public_contracts.py)，`test_returned_SID_cannot_rewrite_original_response[False-reuse_unconsumed-load_queue_uncache]`。
- 原失败的s2数据：实际为B的64bit值双份，预期为A的64bit值双份。
- 生成RTL：`rtl/load_queue_uncache/UncacheEntry.sv:247–252、325–330`。
- [裁定JSON](../../results/fail-source-adjudication-01/all-fail-verdicts-v1.json)，查`LQU-SID-001`和其补充探针。

## 8. GitHub状态

未找到明确描述这个SID返回后污染旧结果的公开报告。[PR #4154](https://github.com/OpenXiangShan/XiangShan/pull/4154)介绍过mid/sid协议和合并功能，但“引入过该协议”不等于“已经报告或修复该生命周期缺陷”。[PR #6634](https://github.com/OpenXiangShan/XiangShan/pull/6634)处理异常候选筛选/年龄仲裁，是[另一项尚未被本套UT检出的检查盲区](13-github-missed-bugs.md)，不是此bug的重复报告。
