"""Opt-in real StoreUnit CBO traffic without rewriting frozen interface cases.

All original full-domain kinds/weights/seeds/errors/recovery/SID policies and
strict fixture remain. Only CBO's actual producer ABI is normalized. These
actors require NEW normal-case tests/runs; static construction is not native
functional evidence, and they do not retroactively bless the original14 cases.
"""
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.joint_owners import JointOwners
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.mixed_owners import MixedOwners
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.normal_owners import NormalCboStore


def normal_cbo(state):
    if state["kind"]=="store" and state["owner"].cbo is not None:
        state["owner"]=NormalCboStore.from_interface(state["owner"])
    return state


class NormalMixedOwners(MixedOwners):
    def make(self,kind,*,unique=False):
        return normal_cbo(super().make(kind,unique=unique))


class NormalJointOwners(JointOwners):
    def make(self,kind,*,unique=True):
        return normal_cbo(super().make(kind,unique=unique))
