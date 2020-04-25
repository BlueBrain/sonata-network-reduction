from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from neuron import h

from sonata_network_reduction.morphology import ReducedNeuronMorphology, _h_children, copy_soma
from utils import TEST_DATA_DIR


def test_neuron_children_order():
    """This test rather verifies that NEURON's `section.children()` method returns in the expected
    order because `morphology` module relies on this behaviour.
    """
    soma = h.Section(name='soma')
    dend1 = h.Section(name='dend1')
    dend2 = h.Section(name='dend2')
    dend1.connect(soma)
    dend2.connect(soma)
    assert [dend2, dend1] == list(soma.children())
    assert [dend1, dend2] == list(_h_children(soma))


def test_expected_behavior():
    soma = h.Section(name='cell[0].soma[0]')
    dend1 = h.Section(name='cell[0].dend[0]')
    dend2 = h.Section(name='cell[0].dend[1]')
    apic1 = h.Section(name='cell[0].apic[0]')
    apic2 = h.Section(name='cell[0].apic[1]')
    apic3 = h.Section(name='cell[0].apic[2]')
    axon1 = h.Section(name='cell[0].axon[0]')
    axon2 = h.Section(name='cell[0].axon[1]')
    dend1.connect(soma)
    dend2.connect(soma)
    apic1.connect(soma)
    apic2.connect(soma)
    apic3.connect(soma)
    axon1.connect(soma)
    axon2.connect(axon1)

    h.define_shape()
    m = ReducedNeuronMorphology(soma)
    assert m.section_lists == {
        'axonal': [axon1], 'basal': [dend1, dend2], 'somatic': [soma],
        'apical': [apic1, apic2, apic3]}
    assert m.get_section_id(soma) == -1
    assert m.get_section_id(axon1) == 0
    assert m.get_section_id(dend1) == 1
    assert m.get_section_id(dend2) == 2
    assert m.get_section_id(apic1) == 3
    assert m.get_section_id(apic2) == 4
    assert m.get_section_id(apic3) == 5

    with pytest.raises(KeyError) as e:
        m.get_section_id(axon2)
    assert e.value.args[0] == axon2

    with TemporaryDirectory() as tmpdirname:
        m.save(Path(tmpdirname, 'm.swc'))


def test_copy_soma():
    soma = h.Section(name='cell[0].soma[0]')
    dend1 = h.Section(name='cell[0].dend[0]')
    axon1 = h.Section(name='cell[0].axon[0]')
    dend1.connect(soma)
    axon1.connect(soma)

    h.define_shape()
    m = ReducedNeuronMorphology(soma)
    assert (m.morph.soma.points == [[0, 0, 0],
                                    [50, 0, 0],
                                    [100, 0, 0]]).all()
    assert (m.morph.soma.diameters == [500, 500, 500]).all()

    copy_soma(m.morph, TEST_DATA_DIR / 'morphology' / 'reduced_soma.swc')
    assert (m.morph.soma.points == [[5, 5, 5]]).all()
    assert m.morph.soma.diameters == [10]


def test_morphology_neurite_child():
    soma = h.Section(name='cell[0].soma[0]')
    dend1 = h.Section(name='cell[0].dend[0]')
    dend2 = h.Section(name='cell[0].dend[1]')
    dend3 = h.Section(name='cell[0].dend[2]')
    dend1.connect(soma)
    dend2.connect(dend1)
    dend3.connect(soma)

    h.define_shape()
    with pytest.raises(AssertionError) as e:
        ReducedNeuronMorphology(soma)
    assert e.value.args[0] == 'Reduced neurite can\'t have children'
