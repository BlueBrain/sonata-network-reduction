"""Module that recreates morphology of currently instantiated neuron in NEURON simulator."""
import re
from pathlib import Path
from typing import Tuple, List, Iterable
import numpy as np

from aibs_circuit_converter.convert_to_hoc import LOCATION_MAP
from morphio.mut import Morphology, Section
from morphio import SectionType, PointLevel, Option
from neuron import h
from sonata_network_reduction.exceptions import SonataReductionError


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


def copy_soma(morph_to: Morphology, morph_file_from: str):
    """Copies soma from morphology under ``morph_from`` to ``morph_to``.

    Args:
        morph_to: instance of Morphology where to copy soma
        morph_file_from: a path to a morphology file where from copy soma
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


def _neuron_order(sections: Iterable[h.Section]) -> List[h.Section]:
    order = {
        SectionType.undefined: 0,
        SectionType.soma: 1,
        SectionType.axon: 2,
        SectionType.basal_dendrite: 3,
        SectionType.apical_dendrite: 4, }
    return sorted(sections, key=lambda section: order[_section_type(section)])


def _h_children(section: h.Section) -> List[h.Section]:
    """get children sections

    Args:
        section: Neuron section

    Returns:
        list: List of children sections
    """
    # currently NEURON returns children starting from the last, we need starting from the first
    return list(reversed(section.children()))


class NeuronMorphology:
    """Represents morphology of a neuron in NEURON."""

    def __init__(self, soma: h.Section):
        """
        Args:
            soma: soma of a neuron in NEURON
        """
        seclist_names = set(LOCATION_MAP.values()) - {'all'}
        self.section_lists = {seclist_name: [] for seclist_name in seclist_names}
        self._id_to_h_section = {}
        self._h_section_to_id = {}
        self._section_id_counter = 0
        self._put_section(soma)

        soma_sections = [soma]
        soma_children = _neuron_order(_h_children(soma))
        while _section_type(soma_children[0]) == SectionType.soma:
            soma_sections.append(soma_children.pop(0))
        self.morph = Morphology()
        self.morph.soma.points = sum([_section_points(sec) for sec in soma_sections], [])
        self.morph.soma.diameters = sum([_section_diameters(sec) for sec in soma_sections], [])
        for h_section in soma_children:
            section = self.morph.append_root_section(
                PointLevel(
                    _section_points(h_section),
                    _section_diameters(h_section)
                ),
                _section_type(h_section))
            self._put_section(h_section)
            self._create_neurite(section, h_section)

    def is_equal_to(self, morphology_filepath: Path) -> bool:
        """Whether ``self`` is equal to a morphology under ``morphology_filepath``.

        This method's purpose is to check section indexing of ``self``. You should save ``self`` to
        a file and compare with it after to verify the same section indexing.
        Args:
            morphology_filepath: morphology to compare with
        """
        m = Morphology(morphology_filepath, options=Option.nrn_order)
        for section in m.iter():
            section_id = section.id + 1  # +1 to account for soma section
            h_section = self.get_section(section_id)
            if section.type != _section_type(h_section):
                return False
        return True

    def _store_to_section_list(self, h_section: h.Section):
        """Stores ``h_section`` to its section list"""
        seclist_name, idx = _extract_sec_name_parts(h_section.name())
        seclist = self.section_lists[seclist_name]
        if len(seclist) != idx:
            raise SonataReductionError(
                'Invalid order of reduced SectionList {}'.format(seclist_name))
        seclist.append(h_section)

    def _put_section(self, h_section: h.Section):
        """Stores section for later access.

        Args:
            h_section: section instance in NEURON
        """
        section_id = self._section_id_counter
        self._section_id_counter += 1
        self._id_to_h_section[section_id] = h_section
        self._h_section_to_id[h_section] = section_id
        self._store_to_section_list(h_section)

    def _continue_section(self, h_section: h.Section, h_child_section: h.Section):
        """Continues ``h_section`` with its child ``h_child_section``"""
        self._h_section_to_id[h_child_section] = self.get_section_id(h_section)
        self._store_to_section_list(h_child_section)

    def get_section_id(self, h_section: h.Section) -> int:
        """Id of neuron section.

        Args:
            h_section: h.Section

        Returns:
            id
        """
        return self._h_section_to_id[h_section]

    def get_section(self, section_id: int) -> h.Section:
        """Section of section id.

        Args:
            section_id: id

        Returns:
            h.Section
        """
        return self._id_to_h_section[section_id]

    def save(self, filepath: Path):
        """Saves morphology to a file.

        Additionally validates equality of the saved with `self.is_equal_to`.
        Args:
            filepath: path to save file
        """
        filepath.parent.mkdir(exist_ok=True)
        self.morph.write(filepath)
        assert self.is_equal_to(filepath) is True

    def _create_neurite(self, section: Section, h_section: h.Section):
        """Iterates over section in NEURON and creates its corresponding morphology.

        Args:
            section: morphio Section, morphology target.
            h_section: section in NEURON, morphology source.
        """
        h_children = _h_children(h_section)
        for h_child_section in h_children:
            child_section = section.append_section(
                PointLevel(
                    _section_points(h_child_section),
                    _section_diameters(h_child_section),
                ))
            if len(h_children) > 1:
                # we create section only when multiple children because single children will be
                # merged into parent upon loading and won't have any section id.
                self._put_section(h_child_section)
            else:
                self._continue_section(h_section, h_child_section)
            self._create_neurite(child_section, h_child_section)
