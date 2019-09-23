"""
Util module for extraction of biophysics from given NEURON sections.
"""
import functools
import logging
import operator
import re
from typing import Iterable, List, Tuple

import numpy as np
from bluepyopt.ephys.locations import NrnSeclistLocation, Location
from bluepyopt.ephys.mechanisms import NrnMODMechanism
from bluepyopt.ephys.parameters import NrnSectionParameter
from aibs_circuit_converter.convert_to_hoc import LOCATION_MAP
from neuron import h  # pylint: disable=E0611

logger = logging.getLogger(__name__)

PARAMETERS_TYPE = List[NrnSectionParameter]
MECHANISMS_TYPE = List[NrnMODMechanism]


def _extract_sec_name_parts(sec_name: str) -> Tuple[str, str, int]:
    """Extracts different parts from original NEURON's section name. Expects a section from
    BluePyOpt model.

    Args:
        sec_name: original NEURON' section name received by ``sec.name()`` method
    Returns:
        a tuple of: section's list name, section's name, section's index in section's list
    """
    match = re.search(r'\w+\[[\d]+\]\.(?P<list_name>\w+)\[(?P<index>\d+)\]', sec_name)
    if not match:
        raise RuntimeError(
            'Unexpected section name. Please consider updating biophysics extraction.')
    # we need to use section list names as they are in the template
    seclist_name = LOCATION_MAP[match.group('list_name')]
    sec_index = int(match.group('index'))
    sec_name = '{}[{}]'.format(seclist_name, sec_index)
    return seclist_name, sec_name, sec_index


def _get_nmodl_param_names(mech_name: str) -> List[str]:
    """extracts parameter names from nmodl mechanism's PARAMETER block

    Args:
        mech_name: mechanism name like 'hh'

    Returns:
        array of parameter names without mechanism's suffix
    """
    ms = h.MechanismStandard(mech_name, 1)
    param_name = h.ref('')
    param_names = []
    for i in range(ms.count()):
        ms.name(param_name, i)
        full_name = param_name[0]
        param_names.append(full_name.split('_' + mech_name)[0])
    return param_names


def _get_mech_parameters(mech, loc: Location) -> PARAMETERS_TYPE:
    """get the list of current parameters from a given mechanism

    Args:
        mech: mechanism, instance of NEURON mechanism
        loc: location of parameter, instance of
    Returns:
        list of NrnSectionParameter
    """
    params = []
    mech_name = mech.name()
    mech_params = _get_nmodl_param_names(mech_name)
    for param_name in mech_params:
        if not hasattr(mech, param_name):
            continue
        v = getattr(mech, param_name)
        full_param_name = param_name + '_' + mech_name
        params.append(NrnSectionParameter(
            param_name, v, locations=[loc], frozen=True, param_name=full_param_name))
    return params


class _Seclist:
    """
    Inner representation of section list. Stores it's mechanisms, parameters and location.
    """

    def __init__(self, seclist_name: str, sec: h.Section):
        self._mechanisms = {}
        self._parameters = {}
        self._create(seclist_name, sec)

    def mechanisms(self) -> MECHANISMS_TYPE:
        """
        Returns:
            List of section list mechanisms
        """
        return list(self._mechanisms.values())

    def params(self) -> PARAMETERS_TYPE:
        """
        Returns:
            List of section list parameters
        """
        return list(self._parameters.values())

    def _put_mechanism(self, mech_name: str, loc: NrnSeclistLocation):
        self._mechanisms[mech_name] = NrnMODMechanism(mech_name, suffix=mech_name, locations=[loc])

    @staticmethod
    def _full_param_name(param_name: str, mech_name: str) -> str:
        if mech_name is None:
            return param_name
        return param_name + '_' + mech_name

    def _has_parameter(self, param_name: str, mech_name: str) -> bool:
        full_param_name = self._full_param_name(param_name, mech_name)
        return full_param_name in self._parameters

    def _get_parameter(self, param_name: str, mech_name: str) -> NrnSectionParameter:
        full_param_name = self._full_param_name(param_name, mech_name)
        return self._parameters.get(full_param_name)

    def _create(self, seclist_name: str, sec: h.Section):
        """instantiates mechanism, parameters and location of section list.

        Args:
            seclist_name: section list name
            sec: section
        """

        def _put_parameter(param_name, param_value, loc, mech_name=None):
            full_param_name = self._full_param_name(param_name, mech_name)
            self._parameters[full_param_name] = NrnSectionParameter(
                param_name, param_value, locations=[loc], frozen=True, param_name=full_param_name)

        loc = NrnSeclistLocation(seclist_name, seclist_name)
        _put_parameter('cm', sec.cm, loc)
        _put_parameter('Ra', sec.Ra, loc)
        first_seg = next(iter(sec))
        for mech in first_seg:
            if not mech.is_ion():
                mech_name = mech.name()
                self._put_mechanism(mech_name, loc)
                nmodl_params = _get_nmodl_param_names(mech_name)
                for param_name in nmodl_params:
                    if not hasattr(mech, param_name):
                        continue
                    param_value = getattr(mech, param_name)
                    _put_parameter(param_name, param_value, loc, mech_name)

    def check(self, sec: h.Section):
        # pylint: disable=too-many-nested-blocks
        """Checks that section has the same mechanisms and parameters as this section list.

        It verifies that section list has uniform mechanisms and params. If this assumption is
        violated, warning messages are logged.
        Args:
            sec: section
        """
        for seg in sec:
            for mech in seg:
                if not mech.is_ion():
                    if mech.name() not in self._mechanisms:
                        logger.warning('Unidentified mech %s in sec %s', mech.name(), sec.name())
                    nmodl_params = _get_nmodl_param_names(mech.name())
                    for param_name in nmodl_params:
                        if not self._has_parameter(param_name, mech.name()):
                            logger.warning(
                                'Unidentified param %s in sec %s', param_name, sec.name())
                        else:
                            param = self._get_parameter(param_name, mech.name())
                            param_value = getattr(mech, param_name, None)
                            if not np.isclose(param_value, param.value):
                                logger.warning(
                                    'Unequal param %s value %s in sec %s',
                                    param_name, (param_value, param.value), sec.name())


class _SeclistCache:
    """cache of _Seclist instances"""

    def __init__(self):
        self._cache = {}

    def mechanisms(self) -> MECHANISMS_TYPE:
        """Returns: List of mechanisms of all sections"""
        mechanisms = [seclist.mechanisms() for seclist in self._cache.values()]
        return functools.reduce(operator.concat, mechanisms)

    def params(self) -> PARAMETERS_TYPE:
        """Returns: List of parameters of all sections"""
        params = [seclist.params() for seclist in self._cache.values()]
        return functools.reduce(operator.concat, params)

    def has(self, seclist_name: str):
        """Checks that ``seclist_name`` is in cache.

        Args:
            seclist_name: section list name
        Returns:
            Boolean
        """
        return seclist_name in self._cache

    def put(self, seclist_name: str, sec: h.Section):
        """Create a new entry for ``seclist_name`` and puts it into cache.

        Args:
            seclist_name: section list name
            sec: section
        """
        self._cache[seclist_name] = _Seclist(seclist_name, sec)

    def check(self, seclist_name: str, sec: h.Section):
        """Verifies that section ``sec`` is valid for ``seclist_name`` section list.

        Args:
            seclist_name: section list name
            sec: section
        """
        self._cache[seclist_name].check(sec)


def get_mechanisms_and_params(sections: Iterable[h.Section]) -> \
        Tuple[MECHANISMS_TYPE, PARAMETERS_TYPE]:
    """Gets list of all mechanisms and parameters of sections.

    Args:
        sections: list of sections
    Returns:
        Tuple of lists. The first is the list of mechanisms. The second is the list of parameters.
    """
    seclist_cache = _SeclistCache()
    for sec in sections:
        seclist_name, _, _ = _extract_sec_name_parts(sec.name())
        if seclist_cache.has(seclist_name):
            seclist_cache.check(seclist_name, sec)
        else:
            seclist_cache.put(seclist_name, sec)
    return seclist_cache.mechanisms(), seclist_cache.params()
