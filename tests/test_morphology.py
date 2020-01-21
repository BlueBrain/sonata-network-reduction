from neuron import h

import sonata_network_reduction.morphology as morphology


def test_morphology_children():
    """This test rather verifies that NEURON's `section.children()` method returns in the expected
    order because `morphology` module relies on this behaviour.
    """
    soma = h.Section(name='soma')
    dend1 = h.Section(name='dend1')
    dend2 = h.Section(name='dend2')
    dend1.connect(soma)
    dend2.connect(soma)
    assert [dend2, dend1] == list(soma.children())
    assert [dend1, dend2] == list(morphology._h_children(soma))


def test_current_morphology():
    soma = h.Section(name='cell[0].soma[0]')
    dend1 = h.Section(name='cell[0].dend[0]')
    dend2 = h.Section(name='cell[0].dend[1]')
    dend1.connect(soma)
    dend2.connect(soma)

    h.define_shape()
    m = morphology.NeuronMorphology(soma)
    expected = {'axonal': [], 'basal': [dend1, dend2], 'somatic': [soma], 'apical': []}
    assert expected == m.section_lists
    assert m.get_section_id(soma) == 0
    assert m.get_section_id(dend1) == 1
    assert m.get_section_id(dend2) == 2
    assert m.get_section(0) == soma
    assert m.get_section(1) == dend1
    assert m.get_section(2) == dend2
