"""Module that recreates morphology of currently instantiated neuron in NEURON simulator."""
import warnings

from morphio.mut import Morphology
from morphio import SectionType, PointLevel
from neuron import h


def _current_neuron_soma():
    """Gets soma of currently instantiated neuron in Neuron.

    Returns:
        Soma. Throws an error if there are multiple neurons.
    """
    cells = h.SectionList()
    cells.allroots()
    cells = list(cells)
    assert len(cells) == 1
    return cells[0]


def _section_points(h_section):
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


def _section_diameters(h_section):
    return [h_section.diam3d(ipt) for ipt in range(h_section.n3d())]


def _section_type(h_section):
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


def _neuron_order(sections):
    order = {
        SectionType.undefined: 0,
        SectionType.soma: 1,
        SectionType.axon: 2,
        SectionType.basal_dendrite: 3,
        SectionType.apical_dendrite: 4, }
    return sorted(sections, key=lambda section: order[_section_type(section)])


def _h_children(section):
    # currently NEURON returns children starting from the last, we need starting from the first
    return reversed(section.children())


class CurrentNeuronMorphology:
    """Represents morphology of currently instantiated neuron in NEURON. If there are multiples
    neurons then it throws an error"""

    def __init__(self):
        soma = _current_neuron_soma()
        self._id_to_hsection = {}
        self._hsection_to_id = {}
        self._put_section(soma, -1)
        if soma.n3d() == 0 and soma.children()[0].n3d() == 0:
            warnings.warn('No 3D morphology information. Using h.define_shape()')
            h.define_shape()

        soma_sections = [soma]
        soma_children = _neuron_order(_h_children(soma))
        while _section_type(soma_children[0]) == SectionType.soma:
            soma_sections.append(soma_children.pop(0))
        self._morpho = Morphology()
        self._morpho.soma.points = sum([_section_points(sec) for sec in soma_sections], [])
        self._morpho.soma.diameters = sum([_section_diameters(sec) for sec in soma_sections], [])
        for h_section in soma_children:
            section = self._morpho.append_root_section(
                PointLevel(
                    _section_points(h_section),
                    _section_diameters(h_section)
                ),
                _section_type(h_section))
            self._put_section(h_section, section.id)
            self._create_neurite(section, h_section)

    def _put_section(self, hsection, section_id: int):
        self._id_to_hsection[section_id] = hsection
        self._hsection_to_id[hsection] = section_id

    def get_section_id(self, hsection):
        """Id of neuron section.

        Args:
            hsection: h.Section

        Returns:
            id
        """
        return self._hsection_to_id[hsection]

    def get_section(self, section_id: int):
        """Section of section id.

        Args:
            section_id: id

        Returns:
            h.Section
        """
        return self._id_to_hsection[section_id]

    def get_section_list(self):
        """List of all sections of morphology.

        Returns:
            list
        """
        return list(self._id_to_hsection.values())

    def save(self, filepath):
        """Saves morphology to a file.

        Args:
            filepath: file
        """
        self._morpho.write(filepath)

    def _create_neurite(self, section, h_section):
        for h_child_section in _h_children(h_section):
            child_section = section.append_section(
                PointLevel(
                    _section_points(h_child_section),
                    _section_diameters(h_child_section),
                ))
            self._put_section(h_child_section, child_section.id)
            self._create_neurite(child_section, h_child_section)
