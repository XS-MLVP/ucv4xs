"""Later-window matching must consume the original query version."""
from bpuverify.utage.env.ancestor_lifetime import AncestorLifetime


async def check_ancestor_lifetime(agent,program,coverage,evidence):
    await AncestorLifetime(agent,program,coverage,evidence).run()
