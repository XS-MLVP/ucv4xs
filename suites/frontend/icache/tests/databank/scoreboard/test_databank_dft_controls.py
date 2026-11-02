"""Declared SRAM-control transactions for the generated DataBank wrapper."""

from dataclasses import replace
import pytest
from toffee import ScoreboardMismatch

from suites.frontend.icache.databank.transaction.types import BankCycle, BankWrite, BankBist
from suites.frontend.icache.transactions.sram import SramControl, SramControls
from suites.frontend.icache.tests.databank.scoreboard.support import running

pytestmark = pytest.mark.selftest


async def test_hold_blocks_only_the_selected_physical_data_macro(databank_agent):
    agent = databank_agent
    await agent.write(0x21, 0b1111, data=7)
    held = SramControls(tuple(SramControl(hold=int(way == 1)) for way in range(4)))
    offered = await agent.cycle(BankCycle(write=BankWrite(0x21, 0b1111, 9), controls=held))
    consumed = await agent.cycle()
    assert len(offered.launched) == 2
    assert all(uid in consumed.accepted for uid in offered.launched)
    assert tuple(entry.data for entry in await agent.read(0x21)) == (9, 7, 9, 9)
    row = next(row for row in agent.receipt()["inputs"]
               if row.kind == "write" and row.uid in offered.launched)
    assert row.state == "held" and row.memory_mask == 0b1101
    control = next(row for row in agent.receipt()["inputs"]
                   if row.kind == "controls" and row.uid in offered.launched)
    assert control.state == "applied" and control.accepted_tick is not None
    assert control.accepted_tick == control.launch_tick + 2
    await agent.cycle(BankCycle(controls=SramControls.idle(4)))
    await agent.finish()


async def test_bypass_and_macro_clock_enable_controls_are_observed_but_do_not_change_behavioral_macro(
        databank_agent):
    agent = databank_agent
    await agent.wait_ready()
    controls = SramControls(tuple(SramControl(bypass=1, bp_clken=1) for _ in range(4)))
    await agent.cycle(BankCycle(write=BankWrite(0x22, 0b1111, 0x55), controls=controls))
    await agent.cycle()
    assert tuple(entry.data for entry in await agent.read(0x22)) == (0x55,) * 4
    await agent.cycle(BankCycle(controls=SramControls.idle(4)))
    await agent.finish()


@pytest.mark.parametrize("field", ("hold", "bypass", "bp_clken", "aux_clk", "aux_ckbp", "mcp_hold", "cgen"))
def test_sram_control_fields_reject_nonphysical_values(field):
    with pytest.raises(ValueError):
        SramControl(**{field: True})
    with pytest.raises(ValueError):
        SramControl(**{field: 2})


@pytest.mark.parametrize("field", ("bypass", "bp_clken", "aux_clk", "aux_ckbp", "mcp_hold", "cgen"))
async def test_non_hold_controls_do_not_invent_a_different_behavioral_macro_contract(databank_agent, field):
    agent = databank_agent
    await agent.wait_ready()
    controls = SramControls(tuple(SramControl(**{field: 1}) for _ in range(4)))
    await agent.cycle(BankCycle(write=BankWrite(0x21, 15, 7, 1), controls=controls))
    await agent.cycle()
    assert tuple((entry.data, entry.code) for entry in await agent.read(0x21)) == ((7, 1),) * 4
    assert (await agent.settle(2)).responses == ()
    await agent.cycle(BankCycle(controls=SramControls.idle(4)))


async def test_releasing_hold_in_the_next_offer_does_not_retroactively_enable_the_previous_write(databank_agent):
    agent = databank_agent
    await agent.write(0x21, 15, data=7)
    held = SramControls((SramControl(hold=1),) * 4)
    offered = await agent.cycle(BankCycle(write=BankWrite(0x21, 15, 9), controls=held))
    await agent.cycle(BankCycle(controls=SramControls.idle(4)))
    assert tuple(entry.data for entry in await agent.read(0x21)) == (7,) * 4
    row = next(row for row in agent.receipt()["inputs"] if row.uid == offered.launched[0])
    assert row.state == "held" and row.memory_mask == 0


async def test_hold_during_sweep_retains_only_unwritten_cells_with_their_real_old_ancestors(databank_agent):
    agent = databank_agent
    await agent.write(33, 15, data=7)
    old = agent.receipt()["inputs"][-1]
    await agent.reset()
    await agent.cycle(BankCycle(controls=SramControls(tuple(
        SramControl(hold=int(way == 1)) for way in range(4)))))
    await agent.settle(60)
    await agent.cycle(BankCycle(controls=SramControls.idle(4)))
    await agent.wait_ready()
    assert tuple(entry.data for entry in await agent.read(33)) == (0, 7, 0, 0)
    row = agent.receipt()["inputs"][-1]
    assert row.sources[1].uid == old.uid and row.sources[1].epoch < row.planned_epoch
    assert all(row.sources[way].kind == "reset" for way in (0, 2, 3))


async def test_mbist_uses_hold_at_its_physical_macro_stage_not_ack_or_next_preview(databank_agent):
    agent = databank_agent
    await agent.write(33, 15, data=7)
    offered = await agent.cycle(BankCycle(bist=BankBist(
        array=5, readen=0, writeen=1, addr_rd=33, indata=9 << 2)))
    await agent.cycle(BankCycle(controls=SramControls((SramControl(hold=1),) * 4)))
    await agent.cycle(BankCycle(controls=SramControls.idle(4)))
    await agent.settle(2)
    assert tuple(entry.data for entry in await agent.read(33)) == (7,) * 4
    row = next(row for row in agent.receipt()["inputs"] if row.uid in offered.launched)
    assert row.ack_tick == offered.tick + 2 and row.accepted_tick == offered.tick + 4
    assert row.memory_mask == 0


async def test_hold_suppressed_mbist_write_with_read_enabled_reads_the_old_word(databank_agent):
    agent = databank_agent
    await agent.write(33, 15, data=7)
    await agent.write(34, 15, data=11)
    await agent.bist_command(array=5, addr_rd=34)
    await agent.cycle(BankCycle(controls=SramControls((SramControl(hold=1),) * 4)))
    ack, word = await agent.bist_command(array=5, readen=1, writeen=1, addr_rd=33, indata=99)
    assert ack == 1 and word == 7 << 2
    await agent.cycle(BankCycle(controls=SramControls.idle(4)))


async def test_still_nonzero_controls_are_not_implicitly_released_by_finish(dut_factory):
    async with running(dut_factory) as agent:
        await agent.wait_ready()
        await agent.cycle(BankCycle(controls=SramControls((SramControl(bypass=1),) * 4)))
        await agent.cycle()
        tick = agent.receipt()["tick"]
        with pytest.raises(ScoreboardMismatch):
            await agent.finish()
        assert agent.receipt()["tick"] == tick


async def test_wrong_hold_algorithm_is_rejected_by_a_native_fixed_answer(dut_factory, monkeypatch):
    async with running(dut_factory) as agent:
        await agent.write(33, 15, data=7)
        monkeypatch.setattr(agent.checker, "_hold_mask", lambda controls: 0)
        await agent.cycle(BankCycle(write=BankWrite(33, 15, 9),
                                   controls=SramControls((SramControl(hold=1),) * 4)))
        await agent.cycle()
        with pytest.raises(ScoreboardMismatch):
            await agent.read(33)


async def test_wrong_control_input_is_rejected_before_any_memory_readback(dut_factory, monkeypatch):
    async with running(dut_factory) as agent:
        await agent.wait_ready()
        put = agent.control_driver.set
        def wrong(values):
            groups = list(values["ways"])
            groups[0] = dict(groups[0], hold=groups[0]["hold"] ^ 1)
            return put(dict(ways=tuple(groups)))
        monkeypatch.setattr(agent.control_driver, "set", wrong)
        with pytest.raises(ScoreboardMismatch):
            await agent.cycle(BankCycle(controls=SramControls((SramControl(hold=1),) * 4)))


def test_control_container_detaches_and_both_cycle_shapes_reject_raw_dicts():
    controls = [SramControl(hold=1), SramControl(), SramControl(), SramControl()]
    snapshot = SramControls(controls)
    controls[0] = SramControl()
    assert snapshot.ways[0].hold == 1
    with pytest.raises(ValueError):
        BankCycle(controls={})
    with pytest.raises(ValueError):
        replace(snapshot, ways=[{}] * 4)
