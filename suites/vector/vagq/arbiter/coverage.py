"""Behavior coverage for VAGQArbiter's source arbitration and routing."""
from toffee import Bin, CoverGroupDef, CoverPointDef


class Coverage:
    def __init__(self):
        self.group = CoverGroupDef('vagq_arbiter_contract_v1', (
            CoverPointDef('source_mix', {name: Bin.values(name) for name in (
                'idle', 'VAGQ-load', 'VAGQ-store', 'load+store',
                'native-only', 'native+VAGQ')}),
            CoverPointDef('age_rule', {name: Bin.values(name) for name in (
                'ROB-order', 'LQ-order', 'SQ-order', 'same-pointer lane tie',
                'wrapped pointer')}),
            CoverPointDef('grant_shape', {name: Bin.values(name) for name in (
                'load-0', 'load-1', 'load-2', 'load-3',
                'store-0', 'store-1', 'store-2')}),
            CoverPointDef('native_policy', {name: Bin.values(name) for name in (
                'no-native', 'native-older-blocks', 'VAGQ-older-displaces',
                'native-invalid')}),
            CoverPointDef('backpressure', {name: Bin.values(name) for name in (
                'all-ready', 'LDU-blocked', 'STA-blocked', 'mixed-ready',
                'issue-ready-suppressed')}),
            CoverPointDef('metadata_route', {name: Bin.values(name) for name in (
                'native-preserved', 'load-route', 'store-route', 'valid-payload')}),
            CoverPointDef('std_busy', {name: Bin.values(name) for name in (
                'idle', 'available', 'busy')}),
            CoverPointDef('std_route', {name: Bin.values(name) for name in (
                'none', 'slot0', 'slot1', 'both')}),
        )).instantiate(
            'vagq.arbiter.checked',
            contract='three-source LSU/STD arbitration and metadata/v1',
        )

    def sample(self, beat, observed):
        active = [request for request in beat.vagq_lsu if request.valid]
        loads = [request for request in active if request.is_load]
        stores = [request for request in active if not request.is_load]
        native_valid = [request for request in beat.issue_lda + beat.issue_sta if request.valid]
        native_present = [request for request in beat.issue_lda + beat.issue_sta if request.valid or request.fields]
        if not active and not native_valid and not native_present:
            source_mix = 'idle'
        elif loads and stores:
            source_mix = 'load+store'
        elif loads:
            source_mix = 'VAGQ-load' if not native_valid else 'native+VAGQ'
        elif stores:
            source_mix = 'VAGQ-store' if not native_valid else 'native+VAGQ'
        else:
            source_mix = 'native-only'

        if any(
            request.rob_flag or request.lq_flag or request.sq_first_flag
            or request.sq_second_flag
            for request in active
        ):
            age_rule = 'wrapped pointer'
        elif len(active) > 1 and (
            (loads and all(
                request.rob_value == loads[0].rob_value
                and request.lq_value == loads[0].lq_value
                for request in loads
            ))
            or (stores and all(
                request.rob_value == stores[0].rob_value
                and request.sq_value == stores[0].sq_value
                for request in stores
            ))
        ):
            age_rule = 'same-pointer lane tie'
        elif len({request.rob_value for request in active}) > 1:
            age_rule = 'ROB-order'
        elif loads:
            age_rule = 'LQ-order'
        elif stores:
            age_rule = 'SQ-order'
        else:
            age_rule = 'wrapped pointer'

        load_count = sum(grant is not None for grant in observed.load_grants)
        store_count = sum(grant is not None for grant in observed.store_grants)
        # One sample carries both source families; grant_shape records the
        # load side when present and otherwise the store side.
        grant_shape = f'load-{load_count}' if loads else f'store-{store_count}'

        if not native_valid and native_present:
            native_policy = 'native-invalid'
        elif not native_valid:
            native_policy = 'no-native'
        elif active and (
            any(
                request.valid and grant is None
                for request, grant in zip(beat.issue_lda, observed.load_grants)
            )
            or any(
                request.valid and grant is None
                for request, grant in zip(beat.issue_sta, observed.store_grants)
            )
        ):
            native_policy = 'native-older-blocks'
        else:
            native_policy = 'VAGQ-older-displaces'

        ready = beat.ldu_ready + beat.sta_ready
        if all(ready):
            backpressure = 'all-ready'
        elif not any(beat.ldu_ready):
            backpressure = 'LDU-blocked'
        elif not any(beat.sta_ready):
            backpressure = 'STA-blocked'
        elif any(
            (grant is not None and not ready[index])
            for index, grant in enumerate(observed.load_grants + observed.store_grants)
        ):
            backpressure = 'issue-ready-suppressed'
        else:
            backpressure = 'mixed-ready'

        has_load_route = any(grant is not None for grant in observed.load_grants)
        has_store_route = any(grant is not None for grant in observed.store_grants)
        if has_load_route and has_store_route:
            metadata_route = 'valid-payload'
        elif has_load_route:
            metadata_route = 'load-route'
        elif has_store_route:
            metadata_route = 'store-route'
        else:
            metadata_route = 'native-preserved'

        if not any(request.valid for request in beat.vagq_store_data):
            std_busy = 'idle'
        elif any(beat.std_busy):
            std_busy = 'busy'
        else:
            std_busy = 'available'
        std_count = sum(
            request.valid and not beat.std_busy[index]
            for index, request in enumerate(beat.vagq_store_data)
        )
        std_route = ('both' if std_count == 2 else 'slot0' if std_count == 1 and
                     beat.vagq_store_data[0].valid and not beat.std_busy[0] else
                     'slot1' if std_count == 1 else 'none')

        self.group.sample({
            'source_mix': source_mix,
            'age_rule': age_rule,
            'grant_shape': grant_shape,
            'native_policy': native_policy,
            'backpressure': backpressure,
            'metadata_route': metadata_route,
            'std_busy': std_busy,
            'std_route': std_route,
        })
