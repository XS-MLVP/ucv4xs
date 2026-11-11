"""Closed StoreDelay command schema and immutable output observations."""
from dataclasses import dataclass

PAYLOAD_FIELDS = {
    'accessType_instrType': 3,
    'uop_exceptionVec_23': 1, 'uop_exceptionVec_19': 1, 'uop_exceptionVec_15': 1,
    'uop_exceptionVec_7': 1, 'uop_exceptionVec_6': 1, 'uop_exceptionVec_3': 1,
    'uop_trigger': 4, 'uop_robIdx_flag': 1, 'uop_robIdx_value': 8, 'uop_robIdx_isFormer': 1,
    'fullva': 64, 'tlbException_vaNeedExt': 1, 'tlbException_isHyper': 1,
    'isForVSnonLeafPTE': 1, 'gpaddr': 64, 'nc': 1, 'mmio': 1, 'memBackTypeMM': 1,
}
REDIRECT_FIELDS = {'valid': 1, 'level': 1, 'flag': 1, 'value': 8, 'former': 1}


def validate_fields(values, fields, label):
    missing, unknown = fields.keys() - values.keys(), values.keys() - fields.keys()
    if missing or unknown:
        raise ValueError(f'{label}: missing={sorted(missing)}, unknown={sorted(unknown)}')
    for key, width in fields.items():
        value = values[key]
        if not isinstance(value, int) or not 0 <= value < (1 << width):
            raise ValueError(f'{label}.{key} does not fit {width} bits: {value!r}')


@dataclass(frozen=True)
class DelayCommand:
    valid: int
    bits: tuple[int, ...]
    redirect: tuple[int, ...]
    reset: bool = False

    @classmethod
    def build(cls, valid, bits, redirect, *, reset=False):
        if valid not in (0, 1) or reset not in (False, True):
            raise ValueError('DelayPipeline valid/reset must be boolean')
        validate_fields(bits, PAYLOAD_FIELDS, 'payload')
        validate_fields(redirect, REDIRECT_FIELDS, 'redirect')
        if valid and bits['uop_robIdx_value'] >= 160:
            raise ValueError('payload ROB value must be in [0, 160)')
        if redirect['valid'] and redirect['value'] >= 160:
            raise ValueError('redirect ROB value must be in [0, 160)')
        return cls(valid, tuple(bits[name] for name in PAYLOAD_FIELDS),
                   tuple(redirect[name] for name in REDIRECT_FIELDS), reset)


@dataclass(frozen=True)
class DelayOutput:
    valid: int
    bits: tuple[int, ...]

    def mapping(self):
        return {'valid': self.valid, 'bits': dict(zip(PAYLOAD_FIELDS, self.bits, strict=True))}

    def meaningful(self):
        # Invalid payload is outside the interface contract, not an oracle.
        return (self.valid, self.bits if self.valid else ())
