"""TAGE entry/useful bindings over the shared SDK service observation scope."""
from toffee import ReadyValidMonitor
from suites.frontend.bpu.bpu.bundle.tage_service import service_binding
from suites.frontend.bpu.bpu.monitor.service import ServiceMonitor


class TageServiceMonitor(ServiceMonitor):
    def __init__(self,agent,checker,*,binding_factory=None):
        factory=service_binding if binding_factory is None else binding_factory
        super().__init__(agent,checker,binding=factory(agent,table=checker.table,bank=checker.bank,
            include_retention=getattr(checker,'observe_retention',False)))
