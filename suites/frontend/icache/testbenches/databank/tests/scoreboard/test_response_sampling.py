"""Native adapter controls; not SRAM defect or additional functional credit."""
from dataclasses import replace
import pytest
from suites.frontend.icache.testbenches.databank.tests.scoreboard.support import running

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize("field", ("data", "code"))
async def test_first_wrong_response_is_not_replaced_by_a_later_matching_value(dut_factory, monkeypatch, field):
    async with running(dut_factory) as agent:
        await agent.write(0x21, 15, data=0x1122334455667788, code=1)
        sample, calls = agent.read_entries, []

        def wrong_first():
            entries = sample()
            calls.append(entries)
            if len(calls) == 1:
                return (replace(entries[0], **{field: getattr(entries[0], field) ^ 1}), *entries[1:])
            return entries

        monkeypatch.setattr(agent, "read_entries", wrong_first)
        with pytest.raises(AssertionError):
            await agent.check_read(0x21)
        assert len(calls) == 1
        monkeypatch.setattr(agent, "read_entries", sample)
        # Unlike the former opt-in checker, a caught error is persistent. A
        # later correct view cannot turn this execution or finish into PASS.
        with pytest.raises(AssertionError):
            await agent.finish()
    async with running(dut_factory) as fresh:
        await fresh.write(0x21, 15, data=0x1122334455667788, code=1)
        assert (await fresh.read(0x21))[0].data == 0x1122334455667788
        await fresh.finish()


async def test_response_time_does_not_read_the_expected_payload(databank_agent, monkeypatch):
    agent = databank_agent
    await agent.write(0x21, 15, data=0x1122334455667788, code=1)
    await agent.write(0x22, 15, data=0x8877665544332211, code=0)
    await agent.read(0x22)

    before = agent._execution.backend.tick
    sample, times = agent.read_entries, []

    def fixed_boundary():
        times.append(agent._execution.backend.tick)
        assert times == [before + 4], 'response selection moved with expected payload'
        return sample()

    monkeypatch.setattr(agent, 'read_entries', fixed_boundary)
    actual = await agent.read(0x21)
    assert agent._execution.backend.tick - before == 4
    assert tuple(entry.data for entry in actual) == (0x1122334455667788,) * 4
    assert tuple(entry.code for entry in actual) == (1,) * 4
