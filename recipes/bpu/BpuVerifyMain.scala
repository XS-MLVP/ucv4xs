// Standalone RTL generation entry points used by the ucv/toffee BPU verification.
// This file lives in the isolated verification worktree, not the user's XiangShan tree.
package bpuverify

import chisel3._
import utility.sram.SramHelper
import org.chipsalliance.cde.config.Parameters
import top.{ArgParser, Generator}
import utility.{ChiselDB, Constantin}
import xiangshan.{XSCoreParamsKey, XSTileKey}
import xiangshan.frontend.bpu.Bpu
import xiangshan.frontend.bpu.abtb.AheadBtb
import xiangshan.frontend.bpu.ittage.Ittage
import xiangshan.frontend.bpu.mbtb.MainBtb
import xiangshan.frontend.bpu.ras.{MicroRas, Ras}
import xiangshan.frontend.bpu.sc.Sc
import xiangshan.frontend.bpu.tage.Tage
import xiangshan.frontend.bpu.ubtb.MicroBtb
import xiangshan.frontend.bpu.utage.MicroTage

object BpuVerifyMain extends App {
  private val selector = "--bpu-dut"
  private val selectorIndex = args.indexOf(selector)
  require(
    selectorIndex >= 0 && selectorIndex + 1 < args.length,
    s"usage: $selector <bpu|ubtb|abtb|utage|mbtb|tage|sc|ittage|ras|uras> [XiangShan generator options]"
  )

  private val dutName = args(selectorIndex + 1).toLowerCase
  private val generatorArgs = args.take(selectorIndex) ++ args.drop(selectorIndex + 2)
  private val (config, firrtlOpts, firtoolOpts) = ArgParser.parse(generatorArgs)
  // Match XSTile: materialize the core configuration once. Rebuilding it on
  // every parameter lookup makes standalone elaboration needlessly quadratic.
  private val coreParams = config(XSTileKey).head
  private implicit val p: Parameters = config.alterPartial {
    case XSCoreParamsKey => coreParams
  }

  // Standalone predictor generation has no DPI-C/SQLite consumers.
  Constantin.init(false)
  ChiselDB.init(false)

  // The parent Frontend supplies the SRAM broadcast in the SoC. At this
  // standalone verification boundary use functional mode (all DFT controls 0).
  private def functionalSramBroadcast(): Unit = {
    val broadcast = SramHelper.genBroadCastBundleTop()
    broadcast := 0.U.asTypeOf(broadcast)
  }

  private def selectedDut: RawModule = dutName match {
    case "bpu"    => new Bpu { override def desiredName = "Bpu"; functionalSramBroadcast() }
    case "ubtb"   => new MicroBtb { override def desiredName = "MicroBtb"; functionalSramBroadcast() }
    case "abtb"   => new AheadBtb { override def desiredName = "AheadBtb"; functionalSramBroadcast() }
    case "utage"  => new MicroTage { override def desiredName = "MicroTage"; functionalSramBroadcast() }
    case "mbtb"   => new MainBtb { override def desiredName = "MainBtb"; functionalSramBroadcast() }
    case "tage"   => new Tage { override def desiredName = "Tage"; functionalSramBroadcast() }
    case "sc"     => new Sc { override def desiredName = "Sc"; functionalSramBroadcast() }
    case "ittage" => new Ittage { override def desiredName = "Ittage"; functionalSramBroadcast() }
    case "ras"    => new Ras { override def desiredName = "Ras"; functionalSramBroadcast() }
    case "uras"   => new MicroRas { override def desiredName = "MicroRas"; functionalSramBroadcast() }
    case other     => throw new IllegalArgumentException(s"unknown BPU DUT: $other")
  }

  Generator.execute(firrtlOpts, selectedDut, firtoolOpts)
}
