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
    soma = h.Section(name='soma')
    dend1 = h.Section(name='dend1')
    dend2 = h.Section(name='dend2')
    dend1.connect(soma)
    dend2.connect(soma)

    m = morphology.CurrentNeuronMorphology()
    assert [soma, dend1, dend2] == m.get_section_list()
    assert m.get_section_id(soma) == -1
    assert m.get_section_id(dend1) == 0
    assert m.get_section_id(dend2) == 1
