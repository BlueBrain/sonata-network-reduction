"""
Util module for extraction of biophysics from given NEURON sections.
"""
import warnings
from typing import Iterable, List, Tuple, Dict, Generator
import itertools
from pathlib import Path
import pkg_resources
import numpy as np

from bluepyopt.ephys import create_hoc
from bluepyopt.ephys.locations import NrnSeclistLocation
from bluepyopt.ephys.mechanisms import NrnMODMechanism
from bluepyopt.ephys.parameters import NrnSectionParameter
from neuron import h

from sonata_network_reduction import utils


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


def _to_bluepyopt_format(mech_names: Dict[str, List], uniform_params: Dict[str, Dict[str, float]]) \
        -> Tuple[List[NrnMODMechanism], List[NrnSectionParameter]]:
    mechs = []
    params = []
    for seclist_name in mech_names.keys():
        loc = NrnSeclistLocation(seclist_name, seclist_name)
        mechs += [NrnMODMechanism(mech_name, suffix=mech_name, locations=[loc])
                  for mech_name in mech_names[seclist_name]]
        params += [NrnSectionParameter(
            param_name, param_value, True, param_name=param_name, locations=[loc])
            for param_name, param_value in uniform_params[seclist_name].items()]
    return mechs, params


class Biophysics:
    """Representation of biophysical model template"""

    def __init__(self,
                 mech_names: Dict[str, List],
                 uniform_params: Dict[str, Dict[str, float]],
                 nonuniform_params: Dict[str, Dict[str, List]],
                 nsegs: Dict[str, List]):
        """Constructor

        Args:
            mech_names: dict of mechanism names per section list
            uniform_params: dict of <section list name>: <dict of <param name: param value>>
                params that are uniform across a section list
            nonuniform_params: dict of <section list name>: <dict of <param name: param value list>>
                params that are not uniform across a section list
            nsegs: dict of <section list name>: <list of nseg values for each section of the list>
                ``nseg`` value of each section in section list
        """
        self._mech_names = mech_names
        self._uniform_params = uniform_params
        self._nonuniform_params = nonuniform_params
        self._nsegs = nsegs

    @classmethod
    def from_nrn(cls, section_lists: Dict[str, h.Section]):
        """Creates an instance from section lists of a neuron

        Args:
            section_lists: dict of sections per section list name

        Returns:
            Biophysics: an instance of Biophysics
        """
        mech_names, uniform_params, nonuniform_params, nsegs = {}, {}, {}, {}
        for seclist_name, seclist in section_lists.items():
            if len(seclist) == 0:
                continue
            seclist_mech_names, seclist_params = _get_sec_mechs_params(seclist[0])
            seclist_uniform_params, seclist_nonuniform_params = _separate_params(
                seclist, seclist_params, seclist_mech_names)
            if seclist_nonuniform_params:
                nonuniform_params[seclist_name] = seclist_nonuniform_params
            mech_names[seclist_name] = seclist_mech_names
            uniform_params[seclist_name] = seclist_uniform_params
            nsegs[seclist_name] = [sec.nseg for sec in seclist]
        return cls(mech_names, uniform_params, nonuniform_params, nsegs)

    def save(self, biophys_filepath: Path, default_morphology_name: str):
        """Saves as a hoc template.

        Args:
            biophys_filepath: path where to save
            default_morphology_name: default morphology name to use in the saved hoc template.
                Required by our hoc templates. You can use empty string if you want.
        """
        biophys_filepath.parent.mkdir(exist_ok=True)
        mechs, uniform_params = _to_bluepyopt_format(self._mech_names, self._uniform_params)
        nonuniform_param_names = set(itertools.chain(*self._nonuniform_params.values()))
        template_filepath = pkg_resources.resource_filename(
            __name__, 'templates/reduced_cell_template.jinja2')
        biophysics = create_hoc.create_hoc(
            mechs=mechs,
            parameters=uniform_params,
            morphology=default_morphology_name,
            replace_axon='',
            template_name=utils.to_valid_nrn_name(biophys_filepath.stem),
            template_filename=template_filepath,
            template_dir='',
            custom_jinja_params={
                'nsegs_map': self._nsegs,
                'nonuniform_params': self._nonuniform_params,
                'nonuniform_param_names': nonuniform_param_names,
            },
        )
        with biophys_filepath.open('w') as f:
            f.write(biophysics)
