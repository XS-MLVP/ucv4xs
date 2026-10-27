"""Diagnostic only: observe the inherited MicroRAS enable port, no functional credit."""
import json

from bpuverify.uras.case.definitions import CALL_A
from bpuverify.uras.case.definitions import MAIN_TOP
from bpuverify.uras.transaction.types import UrasCycle


async def test_probe_enable_gate_is_observable(uras_agent, request):
    await uras_agent.reset()
    armed = await uras_agent.pulse(
        UrasCycle(
            enable=1,
            s1_fire=1,
            spec_start_pc=CALL_A.start_pc,
            spec_position=CALL_A.position,
            spec_action=2,
        )
    )
    disabled_advance = await uras_agent.pulse(UrasCycle(enable=0, s2_fire=1))
    disabled_neutral = await uras_agent.pulse(
        UrasCycle(enable=0, s1_fire=1, full_ret_addr=MAIN_TOP)
    )
    evidence = dict(
        armed=dict(usable=armed.usable, target=armed.target),
        disabled_advance=dict(usable=disabled_advance.usable, target=disabled_advance.target),
        disabled_neutral=dict(usable=disabled_neutral.usable, target=disabled_neutral.target),
        rtl_uses_enable=False,
        scope='diagnostic only; the intended disable policy is not yet a functional point',
    )
    request.node.user_properties.append(('uras_enable_probe', json.dumps(evidence)))
    print(json.dumps(evidence, indent=2))
