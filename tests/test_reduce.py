import os
import tempfile
from distutils.dir_util import copy_tree
from pathlib import Path
from unittest.mock import patch

import neurom
from bluepysnap import Circuit
from neuron import h

from sonata_network_reduction.network_reduction import reduce_network
from sonata_network_reduction.node_reduction import reduce_node, \
    _get_biophys_filepath, _get_morphology_filepath

from utils import compile_circuit_mod_files, circuit_9cells


def _get_node_section_map(node_population_name, sonata_circuit):
    node_section_map = {}
    node_population = sonata_circuit.nodes[node_population_name]
    for node_id in node_population.ids():
        node = node_population.get(node_id)
        morphology_filepath = _get_morphology_filepath(node, sonata_circuit)
        m = neurom.load_neuron(str(morphology_filepath))
        node_section_map[node_id] = neurom.get('number_of_sections', m)[0]
    return node_section_map


def test_reduce_network(circuit_9cells):
    circuit_path, circuit_config_path, circuit = circuit_9cells
    node_population_name = 'cortex'
    original_node_sections = _get_node_section_map(node_population_name, circuit)

    with compile_circuit_mod_files(circuit), tempfile.TemporaryDirectory() as out_dirpath:
        out_dirpath = Path(out_dirpath)

        reduce_network(circuit_config_path, str(out_dirpath), reduction_frequency=0)
        reduced_sonata_circuit = Circuit(str(out_dirpath / circuit_config_path.name))
        reduced_node_sections = _get_node_section_map(node_population_name, reduced_sonata_circuit)
        for node_id, sections_num in original_node_sections.items():
            assert sections_num > reduced_node_sections[node_id]

        node_population = reduced_sonata_circuit.nodes[node_population_name]
        for node_id in node_population.ids():
            node = node_population.get(node_id)
            morphology_filepath = _get_morphology_filepath(node, reduced_sonata_circuit)
            assert morphology_filepath.is_file()
            biophys_filepath = _get_biophys_filepath(node, reduced_sonata_circuit)
            assert biophys_filepath.is_file()

            if not hasattr(h, biophys_filepath.stem):
                h.load_file(str(biophys_filepath))
            biophys_class = getattr(h, biophys_filepath.stem)
            biophys_class(0, str(morphology_filepath.parent), morphology_filepath.name)

            for _, edge_population in reduced_sonata_circuit.edges.items():
                edges = edge_population.afferent_edges(node_id, 'morpho_section_id_post')
                assert edges.le(reduced_node_sections[node_id]).all()


@patch('neuron_reduce.subtree_reductor')
def test_save_morphology(subtree_reductor_mock, circuit_9cells):
    # make reduction a blank operation that does nothing
    subtree_reductor_mock.return_value = (None, [], [])
    circuit_path, circuit_config_path, circuit = circuit_9cells
    with compile_circuit_mod_files(circuit), tempfile.TemporaryDirectory() as tmp_dirpath:
        copy_tree(str(circuit_path), tmp_dirpath)
        circuit_copy = Circuit(str(Path(tmp_dirpath) / circuit_config_path.name))
        reduce_node(0, circuit_copy, 'cortex', reduction_frequency=0)
        morph_dirpath = Path(circuit_copy.config['components']['morphologies_dir'])
        morph_file = morph_dirpath / 'Scnn1a_473845048_m.swc'
        reduced_morph_file = morph_dirpath / 'Scnn1a_473845048_m_0.swc'
        assert reduced_morph_file.is_file()
        assert os.path.getsize(morph_file) == os.path.getsize(reduced_morph_file)
        assert morph_file.open('r').read() == reduced_morph_file.open('r').read()
