// Standalone RTL generation entry points used by the picker/xreactor BPU verification.
// This file lives in the isolated verification worktree, not the user's XiangShan tree.
package bpuverify

import chisel3.RawModule
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
  private implicit val p: Parameters = config.alterPartial {
    case XSCoreParamsKey => config(XSTileKey).head
  }

  // Standalone predictor generation has no DPI-C/SQLite consumers.
  Constantin.init(false)
  ChiselDB.init(false)

  private def selectedDut: RawModule = dutName match {
    case "bpu"    => new Bpu
    case "ubtb"   => new MicroBtb
    case "abtb"   => new AheadBtb
    case "utage"  => new MicroTage
    case "mbtb"   => new MainBtb
    case "tage"   => new Tage
    case "sc"     => new Sc
    case "ittage" => new Ittage
    case "ras"    => new Ras
    case "uras"   => new MicroRas
    case other     => throw new IllegalArgumentException(s"unknown BPU DUT: $other")
  }

  Generator.execute(firrtlOpts, selectedDut, firtoolOpts)
}
