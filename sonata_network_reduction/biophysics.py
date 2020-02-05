"""
Util module for extraction of biophysics from given NEURON sections.
"""
import warnings
from collections import defaultdict
from typing import Iterable, List, Tuple, Dict, Generator
import itertools

import numpy as np
from neuron import h


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
        param_names.append(_short_param_name(full_name, mech_name))
    return param_names


def _short_param_name(full_param_name: str, mech_name: str) -> str:
    return full_param_name.split('_' + mech_name)[0]


def _full_param_name(param_name: str, mech_name: str) -> str:
    return param_name + '_' + mech_name


def _get_mech_name(full_param_name: str) -> str:
    return full_param_name.rsplit('_', 1)[1]


def _get_sec_mechs_params(sec: h.Section) -> Tuple[List[str], Dict[str, float]]:
    """Gets mechanism names and parameters of section.

    It is assumed that mechanisms and parameters are uniform along section.
    Args:
        sec: instance of section in NEURON

    Returns:
        Tuple of mechanism names list and dict of parameter value per name.
    """
    mech_names = []
    params = {'cm': sec.cm, 'Ra': sec.Ra}
    first_seg = next(iter(sec))
    for mech in first_seg:
        mech_name = mech.name()
        if mech.is_ion() and mech_name.endswith('_ion'):
            # take only reverse potential from ions mechanisms
            erev_name = 'e' + mech_name.split('_ion')[0]
            params[erev_name] = getattr(mech, erev_name)
        else:
            mech_names.append(mech_name)
            nmodl_param_names = _get_nmodl_param_names(mech_name)
            for param_name in nmodl_param_names:
                if not hasattr(mech, param_name):
                    continue
                param_value = getattr(mech, param_name)
                params[_full_param_name(param_name, mech_name)] = param_value
    return mech_names, params


def _iter_mechs(seclist: Iterable[h.Section]) -> Generator:
    """Iterates over all mechanisms of section list except ions.

    Args:
        seclist: section list

    Returns:
        An generator over mechanisms.
    """
    return (
        (sec, mech)
        for sec in seclist for mech in itertools.chain.from_iterable(sec)
        if not mech.is_ion()
    )


def _separate_params(
        seclist: Iterable[h.Section],
        seclist_params: Dict[str, float],
        seclist_mech_names: List[str]) \
        -> Tuple[Dict[str, float], Dict[str, List[float]]]:
    """Separates nonuniform from uniform parameters.

    Args:
        seclist: instance of section list in NEURON
        seclist_params: section list parameters as a dict of parameter value per name
        seclist_mech_names: list of mechanism names of section list

    Returns:
        Tuple of uniform parameters and nonuniform parameters. The former is a dict of single
        parameter value per name. The latter is a dict of parameter values per name.
    """
    uniform_params = seclist_params.copy()
    nonuniform_params = {k: [] for k in uniform_params.keys()}
    for sec, mech in _iter_mechs(seclist):
        mech_name = mech.name()
        if mech_name not in seclist_mech_names:
            warnings.warn('Nonuniform mech {} in sec {}'.format(mech_name, sec.name()))
        nmodl_param_names = _get_nmodl_param_names(mech_name)
        for param_name in nmodl_param_names:
            full_param_name = _full_param_name(param_name, mech_name)
            if full_param_name not in seclist_params:
                warnings.warn(
                    'Nonuniform param {} in sec {}'.format(full_param_name, sec.name()))
            else:
                param_value = getattr(mech, param_name, None)
                nonuniform_params[full_param_name].append(param_value)
                is_uniform = full_param_name in uniform_params
                if is_uniform and not np.isclose(param_value, uniform_params[full_param_name]):
                    del uniform_params[full_param_name]
    for uniform_key in uniform_params.keys():
        del nonuniform_params[uniform_key]
    return uniform_params, nonuniform_params


def get_mechs_params(seclists: Dict[str, h.Section]) \
        -> Tuple[Dict[str, List], Dict[str, Dict[str, float]], Dict[str, Dict[str, List]]]:
    """Gets all mechanisms and parameters of section lists.

    Args:
        seclists: dict of sections per seclist

    Returns:
        Tuple of mechanisms, uniform parameters and nonuniform parameters.
        Mechanisms are represented as a dict of mechanism names per section list.
        Uniform parameters is a dict of: seclist name -> dict of param value per param name.
        Nonuniform parameters is a dict of: seclist name -> dict of param values list per param name
    """
    mech_names = {}
    uniform_params = {}
    nonuniform_params = {}
    for seclist_name, seclist in seclists.items():
        if len(seclist) == 0:
            continue
        seclist_mech_names, seclist_params = _get_sec_mechs_params(seclist[0])
        seclist_uniform_params, seclist_nonuniform_params = _separate_params(
            seclist, seclist_params, seclist_mech_names)
        if seclist_nonuniform_params:
            nonuniform_params[seclist_name] = seclist_nonuniform_params
        mech_names[seclist_name] = seclist_mech_names
        uniform_params[seclist_name] = seclist_uniform_params
    return mech_names, uniform_params, nonuniform_params


def get_seclist_nsegs(seclists: Dict[str, h.Section]) -> Dict[str, List]:
    """Gets number of nsegs per seclist.

    Args:
        seclists: dict of sections per seclist

    Returns:
        Dict of sections nsegs per seclist. It replaces each section of ``seclists`` with its nseg.
    """
    seclist_nsegs = defaultdict(list)
    for seclist_name, seclist in seclists.items():
        for sec in seclist:
            seclist_nsegs[seclist_name].append(sec.nseg)
    return dict(seclist_nsegs)
