import functools
import operator
import re

import numpy as np
from aibs_circuit_converter.convert_to_hoc import LOCATION_MAP
from bluepyopt.ephys.locations import NrnSeclistLocation
from bluepyopt.ephys.mechanisms import NrnMODMechanism
from bluepyopt.ephys.parameters import NrnSectionParameter
from neuron import h
from nmodl import dsl


def extract_sec_name_parts(sec_name):
    match = re.search(r'\w+\[[\d]+\]\.(?P<list_name>\w+)\[(?P<index>\d+)\]', sec_name)
    # we need to use section list names as they are in the template
    seclist_name = LOCATION_MAP[match.group('list_name')]
    sec_index = int(match.group('index'))
    sec_name = '{}[{}]'.format(seclist_name, sec_index)
    return seclist_name, sec_name, sec_index


def extract_mech_params(mech, loc):
    params = []
    mech_name = mech.name()
    mech_params = get_mech_params(mech_name)
    for n in mech_params:
        if not hasattr(mech, n):
            continue
        v = getattr(mech, n)
        n_mech = n + '_' + mech_name
        params.append(NrnSectionParameter(n, v, locations=[loc], frozen=True, param_name=n_mech))
    return params


class Seclist:
    def __init__(self, seclist_name, sec):
        self._mechanisms = {}
        self._params = {}
        self.create(seclist_name, sec)

    @property
    def mechanisms(self):
        return list(self._mechanisms.values())

    @property
    def params(self):
        return list(self._params.values())

    def _put_mech(self, mech_name, loc):
        self._mechanisms[mech_name] = NrnMODMechanism(mech_name, suffix=mech_name, locations=[loc])

    @staticmethod
    def _full_param_name(param_name, mech_name):
        if mech_name:
            return param_name + '_' + mech_name
        else:
            return param_name

    def _has_param(self, param_name, mech_name):
        full_param_name = self._full_param_name(param_name, mech_name)
        return full_param_name in self._params

    def _get_param(self, param_name, mech_name):
        full_param_name = self._full_param_name(param_name, mech_name)
        return self._params.get(full_param_name)

    def _put_param(self, param_name, param_value, mech_name, loc):
        full_param_name = self._full_param_name(param_name, mech_name)
        self._params[full_param_name] = NrnSectionParameter(
            param_name, param_value, locations=[loc], frozen=True, param_name=full_param_name)

    def create(self, seclist_name, sec):
        loc = NrnSeclistLocation(seclist_name, seclist_name)
        self._put_param('cm', sec.cm, None, loc)
        self._put_param('Ra', sec.Ra, None, loc)
        first_seg = next(iter(sec))
        for mech in first_seg:
            if not mech.is_ion():
                mech_name = mech.name()
                self._put_mech(mech_name, loc)
                mech_params = get_mech_params(mech_name)
                for param_name in mech_params:
                    if not hasattr(mech, param_name):
                        continue
                    param_value = getattr(mech, param_name)
                    self._put_param(param_name, param_value, mech_name, loc)

    def check(self, sec):
        # assume that section list has uniform mechanisms and params
        for seg in sec:
            for mech in seg:
                if not mech.is_ion():
                    if mech.name() not in self._mechanisms:
                        print('Warning! Unidentified mech {} in sec {}'.format(
                            mech.name(), sec.name()))
                    mech_params = get_mech_params(mech.name())
                    for param_name in mech_params:
                        if not self._has_param(param_name, mech.name()):
                            print('Warning! Unidentified param {} in sec {}'.format(
                                param_name, sec.name()))
                        else:
                            param = self._get_param(param_name, mech.name())
                            param_value = getattr(mech, param_name, None)
                            if not np.isclose(param_value, param.value):
                                print('Warning! Unequal param {} value {} in sec {}'.format(
                                    param_name, (param_value, param.value), sec.name()))


class SeclistCache:
    def __init__(self):
        self._cache = {}

    @property
    def mechanisms(self):
        mechanisms = [seclist.mechanisms for seclist in self._cache.values()]
        return functools.reduce(operator.concat, mechanisms)

    @property
    def params(self):
        params = [seclist.params for seclist in self._cache.values()]
        return functools.reduce(operator.concat, params)

    def has(self, seclist_name):
        return seclist_name in self._cache

    def put(self, seclist_name, sec):
        self._cache[seclist_name] = Seclist(seclist_name, sec)

    def check(self, seclist_name, sec):
        self._cache[seclist_name].check(sec)


def extract(sections):
    seclist_cache = SeclistCache()
    for sec in sections:
        seclist_name, sec_name, sec_index = extract_sec_name_parts(sec.name())
        if seclist_cache.has(seclist_name):
            seclist_cache.check(seclist_name, sec)
        else:
            seclist_cache.put(seclist_name, sec)
    return seclist_cache.mechanisms, seclist_cache.params


def get_mech_params(mech_name):
    """extracts params from mechanism's PARAMETER block

    Args:
        mech_name (str): mechanism name like `hh`

    Returns:
        dict: params<name, value>
    """
    mech_type = h.MechanismType(0)
    mech_type.select(mech_name)
    code = mech_type.code()
    driver = dsl.NmodlDriver()
    modast = driver.parse_string(code)
    lookup_visitor = dsl.visitor.AstLookupVisitor()
    param_block = lookup_visitor.lookup(modast, dsl.ast.AstNodeType.PARAM_ASSIGN)

    params = {}
    for param in param_block:
        name = param.name.value.value
        value = None
        if param.value is not None:
            value = param.value.value
        params[name] = value
    return params
