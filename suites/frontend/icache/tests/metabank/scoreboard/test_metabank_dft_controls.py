"""Declared SRAM-control transactions for the generated MetaBank wrapper."""

import pytest
from toffee import ScoreboardMismatch

from suites.frontend.icache.metabank.transaction.types import MetaBankCycle, MetaBankWrite, MetaBankBist
from suites.frontend.icache.transactions.sram import SramControl, SramControls
from suites.frontend.icache.tests.metabank.scoreboard.test_runtime_obligations import running

pytestmark = pytest.mark.selftest


async def test_hold_blocks_the_selected_two_way_metadata_macro_but_validity_still_records_write(
        metabank_agent):
    agent = metabank_agent
    await agent.write(0x21, 0b1111, phy_tag=7)
    held = SramControls((SramControl(), SramControl(hold=1)))
    offered = await agent.cycle(MetaBankCycle(
        write=MetaBankWrite(0x21, 0b1111, 9), controls=held))
    consumed = await agent.cycle()
    assert len(offered.launched) == 2
    assert all(uid in consumed.accepted for uid in offered.launched)
    values = await agent.read(0x21)
    assert tuple(entry.entry.phy_tag for entry in values) == (9, 9, 7, 7)
    assert all(entry.valid for entry in values)
    row = next(row for row in agent.receipt()["inputs"]
               if row.kind == "write" and row.uid in offered.launched)
    assert row.state == "held" and row.memory_mask == 0b0011
    assert all(source.kind == "write" for source in
               next(row for row in agent.receipt()["inputs"] if row.kind == "read").validity_sources)
    await agent.cycle(MetaBankCycle(controls=SramControls.idle(2)))
    await agent.finish()


async def test_bypass_and_macro_clock_enable_controls_are_observed_but_do_not_change_behavioral_macro(
        metabank_agent):
    agent = metabank_agent
    await agent.wait_ready()
    controls = SramControls((SramControl(bypass=1, bp_clken=1),) * 2)
    await agent.cycle(MetaBankCycle(
        write=MetaBankWrite(0x22, 0b1111, 0x55), controls=controls))
    await agent.cycle()
    assert tuple(entry.entry.phy_tag for entry in await agent.read(0x22)) == (0x55,) * 4
    await agent.cycle(MetaBankCycle(controls=SramControls.idle(2)))
    await agent.finish()


@pytest.mark.parametrize("field", ("hold", "bypass", "bp_clken", "aux_clk", "aux_ckbp", "mcp_hold", "cgen"))
def test_sram_control_fields_reject_nonphysical_values(field):
    with pytest.raises(ValueError):
        SramControl(**{field: True})
    with pytest.raises(ValueError):
        SramControl(**{field: 2})


@pytest.mark.parametrize("field", ("bypass", "bp_clken", "aux_clk", "aux_ckbp", "mcp_hold", "cgen"))
async def test_non_hold_controls_do_not_invent_a_different_behavioral_macro_contract(metabank_agent, field):
    agent = metabank_agent
    await agent.wait_ready()
    controls = SramControls((SramControl(**{field: 1}),) * 2)
    await agent.cycle(MetaBankCycle(write=MetaBankWrite(33, 15, 7, 8, 1), controls=controls))
    await agent.cycle()
    values = await agent.read(33)
    assert tuple((way.valid, way.entry.phy_tag, way.entry.maybe_rvc_map, way.entry.code)
                 for way in values) == ((1, 7, 8, 1),) * 4
    assert (await agent.settle(2)).responses == ()
    await agent.cycle(MetaBankCycle(controls=SramControls.idle(2)))


async def test_releasing_hold_in_the_next_offer_does_not_retroactively_enable_the_previous_write(metabank_agent):
    agent = metabank_agent
    await agent.write(33, 15, phy_tag=7)
    held = SramControls((SramControl(hold=1),) * 2)
    offered = await agent.cycle(MetaBankCycle(write=MetaBankWrite(33, 15, 9), controls=held))
    await agent.cycle(MetaBankCycle(controls=SramControls.idle(2)))
    assert tuple(entry.entry.phy_tag for entry in await agent.read(33)) == (7,) * 4
    row = next(row for row in agent.receipt()["inputs"] if row.uid == offered.launched[0])
    assert row.state == "held" and row.memory_mask == 0 and row.validity_tick is not None


async def test_hold_during_sweep_retains_tags_while_reset_independently_invalidates_all_ways(metabank_agent):
    agent = metabank_agent
    await agent.write(33, 15, phy_tag=7)
    old = agent.receipt()["inputs"][-1]
    await agent.reset()
    await agent.cycle(MetaBankCycle(controls=SramControls((SramControl(), SramControl(hold=1)))))
    await agent.settle(60)
    await agent.cycle(MetaBankCycle(controls=SramControls.idle(2)))
    await agent.wait_ready()
    original = 7 << 33
    ack, word = await agent.bist_command(array=1, addr_rd=33)
    assert ack == 1 and word == original | (original << 69)
    assert all(not entry.valid for entry in await agent.read(33))
    row = agent.receipt()["inputs"][-1]
    assert row.storage_sources[2].uid == old.uid and row.storage_sources[2].epoch < row.planned_epoch
    assert all(source.kind == "reset" for source in row.validity_sources)


async def test_mbist_uses_hold_at_its_physical_macro_stage_not_ack_or_next_preview(metabank_agent):
    agent = metabank_agent
    await agent.write(33, 15, phy_tag=7)
    offered = await agent.cycle(MetaBankCycle(bist=MetaBankBist(
        array=1, readen=0, writeen=1, be=3, addr_rd=33, indata=9 << 33)))
    await agent.cycle(MetaBankCycle(controls=SramControls((SramControl(hold=1),) * 2)))
    await agent.cycle(MetaBankCycle(controls=SramControls.idle(2)))
    await agent.settle(2)
    assert tuple(entry.entry.phy_tag for entry in await agent.read(33)) == (7,) * 4
    row = next(row for row in agent.receipt()["inputs"] if row.uid in offered.launched)
    assert row.ack_tick == offered.tick + 2 and row.accepted_tick == offered.tick + 4
    assert row.memory_mask == 0 and row.memory_tick is None


async def test_hold_suppressed_mbist_write_with_read_enabled_reads_the_old_word(metabank_agent):
    agent = metabank_agent
    await agent.write(33, 15, phy_tag=7)
    await agent.write(34, 15, phy_tag=11)
    await agent.bist_command(array=1, addr_rd=34)
    await agent.cycle(MetaBankCycle(controls=SramControls((SramControl(hold=1),) * 2)))
    ack, word = await agent.bist_command(array=1, readen=1, writeen=1, be=3, addr_rd=33, indata=99)
    original = 7 << 33
    assert ack == 1 and word == original | (original << 69)
    await agent.cycle(MetaBankCycle(controls=SramControls.idle(2)))


async def test_still_nonzero_controls_are_not_implicitly_released_by_finish(dut_factory):
    async with running(dut_factory) as agent:
        await agent.wait_ready()
        await agent.cycle(MetaBankCycle(controls=SramControls((SramControl(bypass=1),) * 2)))
        await agent.cycle()
        tick = agent.receipt()["tick"]
        with pytest.raises(ScoreboardMismatch):
            await agent.finish()
        assert agent.receipt()["tick"] == tick


async def test_wrong_hold_algorithm_is_rejected_by_a_native_fixed_answer(dut_factory, monkeypatch):
    async with running(dut_factory) as agent:
        await agent.write(33, 15, phy_tag=7)
        monkeypatch.setattr(agent.checker, "_hold_mask", lambda controls: 0)
        await agent.cycle(MetaBankCycle(write=MetaBankWrite(33, 15, 9),
                                       controls=SramControls((SramControl(hold=1),) * 2)))
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
            await agent.cycle(MetaBankCycle(controls=SramControls((SramControl(hold=1),) * 2)))
