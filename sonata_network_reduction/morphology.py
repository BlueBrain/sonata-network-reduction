"""Module that recreates morphology of currently instantiated neuron in NEURON simulator."""
import re
from typing import Tuple, List, Iterable

from aibs_circuit_converter.convert_to_hoc import LOCATION_MAP
from morphio.mut import Morphology, Soma, Section
from morphio import SectionType, PointLevel
from neuron import h
from sonata_network_reduction.exceptions import SonataReductionError


def _extract_sec_name_parts(sec_name: str) -> Tuple[str, int]:
    """Extracts different parts from original NEURON's section name. Expects a section from
    BluePyOpt model.

    Args:
        sec_name: original NEURON' section name received by ``sec.name()`` method
    Returns:
        a tuple of: SectionList name, section index in SectionList
    """
    match = re.search(r'\w+\[[\d]+\]\.(?P<list_name>\w+)\[(?P<index>\d+)\]', sec_name)
    if not match:
        raise RuntimeError(
            'Unexpected section name. Please consider updating biophysics extraction.')
    # we need to use section list names as they are in the template
    seclist_name = LOCATION_MAP[match.group('list_name')]
    sec_index = int(match.group('index'))
    return seclist_name, sec_index


def _fix_soma_point_cylinder(morph_soma: Soma, soma_sections: List):
    """Changes inplace ``morph_soma`` from cylinder to point if it has 1 nseg.

    Args:
        morph_soma: MorphIO soma instance
        soma_sections: list of soma sections in NEURON
    """
    is_single_nseg_soma = (len(soma_sections) == 1) and (len(list(soma_sections[0])) == 1)
    if is_single_nseg_soma and len(morph_soma.points) == 3:
        morph_soma.points = [morph_soma.points[1]]
        morph_soma.diameters = [morph_soma.diameters[1]]


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


def _h_children(section: h.Section) -> Iterable[h.Section]:
    # currently NEURON returns children starting from the last, we need starting from the first
    return reversed(section.children())


class NeuronMorphology:
    """Represents morphology of a neuron in NEURON."""

    def __init__(self, soma: h.Section):
        """
        Args:
            soma: soma of a neuron in NEURON
        """
        seclist_names = set(LOCATION_MAP.values()) - {'all'}
        self.section_lists = {seclist_name: [] for seclist_name in seclist_names}
        self._id_to_hsection = {}
        self._hsection_to_id = {}
        self._put_section(soma, -1)

        soma_sections = [soma]
        soma_children = _neuron_order(_h_children(soma))
        while _section_type(soma_children[0]) == SectionType.soma:
            soma_sections.append(soma_children.pop(0))
        self._morph = Morphology()
        self._morph.soma.points = sum([_section_points(sec) for sec in soma_sections], [])
        self._morph.soma.diameters = sum([_section_diameters(sec) for sec in soma_sections], [])
        _fix_soma_point_cylinder(self._morph.soma, soma_sections)
        for h_section in soma_children:
            section = self._morph.append_root_section(
                PointLevel(
                    _section_points(h_section),
                    _section_diameters(h_section)
                ),
                _section_type(h_section))
            self._put_section(h_section, section.id)
            self._create_neurite(section, h_section)

    def _put_section(self, hsection: h.Section, section_id: int):
        """Stores section with its ID for later access.

        Args:
            hsection: section instance in NEURON
            section_id: section ID
        """
        self._id_to_hsection[section_id] = hsection
        self._hsection_to_id[hsection] = section_id
        seclist_name, idx = _extract_sec_name_parts(hsection.name())
        seclist = self.section_lists[seclist_name]
        if len(seclist) != idx:
            raise SonataReductionError(
                'Invalid order of reduced SectionList {}'.format(seclist_name))
        seclist.append(hsection)

    def get_section_id(self, hsection: h.Section) -> int:
        """Id of neuron section.

        Args:
            hsection: h.Section

        Returns:
            id
        """
        return self._hsection_to_id[hsection]

    def get_section(self, section_id: int) -> h.Section:
        """Section of section id.

        Args:
            section_id: id

        Returns:
            h.Section
        """
        return self._id_to_hsection[section_id]

    def save(self, filepath: str):
        """Saves morphology to a file.

        Args:
            filepath: file
        """
        self._morph.write(filepath)

    def _create_neurite(self, section: Section, h_section: h.Section):
        """Iterates over section in NEURON and creates its corresponding morphology.

        Args:
            section: morphio Section, morphology target.
            h_section: section in NEURON, morphology source.
        """
        for h_child_section in _h_children(h_section):
            child_section = section.append_section(
                PointLevel(
                    _section_points(h_child_section),
                    _section_diameters(h_child_section),
                ))
            self._put_section(h_child_section, child_section.id)
            self._create_neurite(child_section, h_child_section)
