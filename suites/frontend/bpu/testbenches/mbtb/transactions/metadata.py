"""Exact MainBTB sidebands and recursively immutable, detached snapshots.

An explicit deepcopy returns a mutable diagnostic/expected-profile copy. It
never aliases the captured mapping; callers must construct a new transaction
to submit an edited copy. This preserves the existing profile-model API.
"""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass


def unsigned(value,bits,name):
    if type(value) is not int or not 0<=value<(1<<bits):
        raise ValueError(f'MainBTB {name} must be an unsigned {bits}-bit integer')


@dataclass(frozen=True,slots=True,eq=False)
class MetadataMapping(Mapping):
    _items:tuple
    origin:object=None
    declared_reason:str|None=None

    def __getitem__(self,key):
        for name,value in self._items:
            if name==key:return value
        raise KeyError(key)

    def __iter__(self):return (name for name,_ in self._items)
    def __len__(self):return len(self._items)
    def __deepcopy__(self,memo):
        return MetadataCopy({key:deepcopy(value,memo) for key,value in self._items},
            origin=self.origin,declared_reason=self.declared_reason)
    def __repr__(self):return repr(dict(self))


class MetadataCopy(dict):
    """Mutable diagnostic copy retaining its non-wire ancestry declaration.

    Editing fields does not silently turn a captured lookup into external input.
    A deliberate port-characterization edit must use declared_metadata().
    """
    __slots__=('_origin','_declared_reason')

    def __init__(self,*args,origin=None,declared_reason=None,**kwargs):
        super().__init__(*args,**kwargs)
        self._origin=origin
        self._declared_reason=declared_reason

    @property
    def origin(self):return self._origin

    @property
    def declared_reason(self):return self._declared_reason


@dataclass(frozen=True,slots=True)
class MetadataOrigin:
    uid:int
    epoch:int
    pc:int
    offer_tick:int
    response_tick:int

    def __post_init__(self):
        for name in ('uid','epoch','offer_tick','response_tick'):
            value=getattr(self,name)
            if type(value) is not int or value<0:raise ValueError('MainBTB metadata origin requires nonnegative input identity and times')
        unsigned(self.pc,50,'metadata source PC')
        if self.response_tick<=self.offer_tick:raise ValueError('MainBTB metadata response must follow its input offer')


def metadata_origin(values):
    origins={getattr(source,'origin',None) for row in values for source in row}
    if len(origins)!=1:raise ValueError('MainBTB metadata cannot mix lookup ancestors or silently drop one')
    return next(iter(origins))


def declared_metadata(values,*,reason):
    """Deliberate isolated port input; never genuine lookup/FTQ provenance."""
    if not isinstance(reason,str) or not reason.strip():raise ValueError('MainBTB declared metadata requires its port-domain reason')
    return freeze_metadata(values,clear_origin=True,declared_reason=reason)


def fields(value,expected,name):
    if not isinstance(value,Mapping) or set(value)!=set(expected):
        raise ValueError(f'MainBTB {name} requires exactly {tuple(expected)}')


def freeze_metadata(values,*,prediction=False,origin=None,clear_origin=False,declared_reason=None):
    if type(values) not in (tuple,list) or len(values)!=2:
        raise ValueError('MainBTB metadata requires exactly two alignments')
    sizes=(5,)
    if any(type(row) not in (tuple,list) or len(row) not in sizes for row in values) or len({len(row) for row in values})!=1:
        raise ValueError('MainBTB metadata requires four Main ways and the complete victim prediction snapshot')
    inherited=None if clear_origin else metadata_origin(values)
    if inherited is not None and type(inherited) is not MetadataOrigin:
        raise ValueError('MainBTB metadata has an invalid ancestry declaration')
    selected=None if clear_origin else origin if origin is not None else inherited
    result=[]
    for align,row in enumerate(values):
        bank=[]
        for way,source in enumerate(row):
            label=f'metadata[{align}][{way}]'
            expected=('rawHit','position','counter_value')+(('attribute',) if way<4 else ())
            fields(source,expected,label)
            for name,bits in (('rawHit',1),('position',5),('counter_value',2)):
                unsigned(source[name],bits,label+'.'+name)
            copied=[(name,source[name]) for name in expected if name!='attribute']
            if way<4:
                attribute=source['attribute'];fields(attribute,('branchType','rasAction'),label+'.attribute')
                for name in ('branchType','rasAction'):unsigned(attribute[name],2,label+'.'+name)
                copied.append(('attribute',MetadataMapping(tuple(attribute.items()))))
            reason=declared_reason if clear_origin else getattr(source,'declared_reason',None)
            bank.append(MetadataMapping(tuple(copied),selected,reason))
        result.append(tuple(bank))
    return tuple(result)
