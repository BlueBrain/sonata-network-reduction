"""Module that recreates morphology of currently instantiated neuron in NEURON simulator."""
import re
import warnings
from pathlib import Path
from typing import Tuple, List, Iterable
import numpy as np

from aibs_circuit_converter.convert_to_hoc import LOCATION_MAP
from morphio.mut import Morphology
from morphio import SectionType, PointLevel
from neuron import h


def _extract_sec_name_parts(sec_name: str) -> Tuple[str, int]:
    """Extracts different parts from original NEURON's section name. Expects a section from
    BluePyOpt model.

    Args:
        sec_name: original NEURON' section name received by ``sec.name()`` method
    Returns:
        a tuple of: SectionList name(like 'apical', 'basal'...), section index in SectionList
    """
    match = re.search(r'\w+\[[\d]+\]\.(?P<list_name>\w+)\[(?P<index>\d+)\]', sec_name)
    if not match:
        raise RuntimeError(
            'Unexpected section name. Please consider updating biophysics extraction.')
    # we need to use section list names as they are in the template
    seclist_name = LOCATION_MAP[match.group('list_name')]
    sec_index = int(match.group('index'))
    return seclist_name, sec_index


def copy_soma(morph_to: Morphology, morph_file_from: Path):
    """Copies soma from morphology under ``morph_file_from`` to ``morph_to``.

    Args:
        morph_to: instance of Morphology where to copy
        morph_file_from: a path to a morphology from which to copy
    """
    morph_from = Morphology(morph_file_from)
    morph_to.soma.points = np.copy(morph_from.soma.points)
    morph_to.soma.diameters = np.copy(morph_from.soma.diameters)


def _section_points(h_section: h.Section) -> List[List]:
    """Gets list of 3d coordinates of all section points.

    Args:
        h_section: section in Neuron

    Returns:
        list of 3d coordinates of all points
    """
    points = []
    for ipt in range(h_section.n3d()):
        x = h_section.x3d(ipt)
        y = h_section.y3d(ipt)
        z = h_section.z3d(ipt)
        points.append([x, y, z])
    return points


def _section_diameters(h_section: h.Section) -> List[float]:
    return [h_section.diam3d(ipt) for ipt in range(h_section.n3d())]


def _section_type(h_section: h.Section) -> SectionType:
    name = h_section.name()
    if 'axon' in name:
        return SectionType.axon
    elif 'apic' in name:
        return SectionType.apical_dendrite
    elif 'dend' in name:
        return SectionType.basal_dendrite
    elif 'soma' in name:
        return SectionType.soma
    return SectionType.undefined


def _neuron_order(h_sections: Iterable[h.Section]) -> List[h.Section]:
    order = {
        SectionType.undefined: 0,
        SectionType.soma: 1,
        SectionType.axon: 2,
        SectionType.basal_dendrite: 3,
        SectionType.apical_dendrite: 4, }
    return sorted(h_sections, key=lambda section: order[_section_type(section)])


def _h_children(h_section: h.Section) -> List[h.Section]:
    """get children sections

    Args:
        h_section: Neuron section

    Returns:
        list: List of children sections
    """
    # currently NEURON returns children starting from the last, we need starting from the first
    return list(reversed(h_section.children()))


class ReducedNeuronMorphology:
    """Recreates a MorphIO morphology from a reduced neuron in NEURON."""

    def __init__(self, h_soma: h.Section):
        """
        Args:
            h_soma: soma of the reduced neuron in NEURON
        """
        seclist_names = set(LOCATION_MAP.values()) - {'all'}
        self.section_lists = {seclist_name: [] for seclist_name in seclist_names}
        self._h_section_to_id = {}

        self.morph = self._recreate_morphology(h_soma)

    def _register_h_section(self, morphio_section_id: int, h_section: h.Section):
        """Maps NEURON section to corresponding Morphio section id

        Also stores section in corresponding section list
        Args:
            morphio_section_id: Morphio section id
            h_section: NEURON section
        """
        self._h_section_to_id[h_section] = morphio_section_id
        seclist_name, idx = _extract_sec_name_parts(h_section.name())
        seclist = self.section_lists[seclist_name]
        assert len(seclist) == idx, 'Invalid order of reduced SectionList {}'.format(seclist_name)
        seclist.append(h_section)

    def _recreate_morphology(self, h_soma: h.Section) -> Morphology:
        """Creates Morphio morphology from corresponding NEURON model.

        Args:
            h_soma: NEURON soma, starting point of NEURON model.

        Returns:
            Morphology: recreated Morphio morphology
        """
        morph = Morphology()
        morph.soma.points = _section_points(h_soma)
        morph.soma.diameters = _section_diameters(h_soma)
        self._register_h_section(-1, h_soma)  # -1 is for Morphio soma id
        h_soma_children = _neuron_order(_h_children(h_soma))
        assert _section_type(h_soma_children[0]) != SectionType.soma, \
            'Multiple sections soma are invalid'
        for h_section in h_soma_children:
            # All neurites except Axon can't have children. Axon is an exception because we deal
            # with its stub from `replace_axon`. The stub is simple enough hence it is not reduced.
            # Often the stub is two sections, one attached to another which is an unexpected output
            # from the neuron_reduce
            if _section_type(h_section) != SectionType.axon:
                assert len(_h_children(h_section)) == 0, 'Reduced neurite can\'t have children'
            section = morph.append_root_section(
                PointLevel(_section_points(h_section), _section_diameters(h_section)),
                _section_type(h_section))
            self._register_h_section(section.id, h_section)
        with warnings.catch_warnings(record=True) as w:
            morph.sanitize()
            assert len(w) == 0, 'Reduced morphology is invalid due to {}'.format(w)
        return morph

    def save(self, filepath: Path):
        """Saves morphology to a file.

        Args:
            filepath: path to save file
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        self.morph.write(filepath)

    def get_section_id(self, h_section: h.Section):
        """Gets corresponding Morphio section id of NEURON section

        Args:
            h_section: NEURON section

        Returns:
            int: Morphio section id
        """
        return self._h_section_to_id[h_section]
