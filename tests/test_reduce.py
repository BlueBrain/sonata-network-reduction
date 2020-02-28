import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd

import neurom
from bluepysnap import Circuit
from morph_tool import diff
from neuron import h

from sonata_network_reduction.network_reduction import reduce_network
from sonata_network_reduction.node_reduction import _reduce_node_same_process, \
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
    _, circuit_config_path, circuit = circuit_9cells
    node_population_name = 'cortex'
    original_node_sections = _get_node_section_map(node_population_name, circuit)

    with compile_circuit_mod_files(circuit), tempfile.TemporaryDirectory() as tmp_dirpath:
        tmp_dirpath = Path(tmp_dirpath) / 'reduced'

        reduce_network(circuit_config_path, tmp_dirpath, reduction_frequency=0)
        reduced_sonata_circuit = Circuit(str(tmp_dirpath / circuit_config_path.name))
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

            for edge_population in reduced_sonata_circuit.edges.values():
                edges = edge_population.afferent_edges(node_id, 'morpho_section_id_post')
                assert edges.le(reduced_node_sections[node_id]).all()


def _reduce_node_mock(
        node_id, reduced_dir, node_population_name, circuit_config_file, **reduce_kwargs):
    reduced_dir.mkdir(parents=True)

    node = pd.Series({'model_template': 'dummy'})
    node_path = reduced_dir / 'node' / '{}.json'.format(node_id)
    node_path.parent.mkdir()
    node.to_json(node_path)

    circuit = Circuit(circuit_config_file)
    edges_path = reduced_dir / 'edges'
    edges_path.mkdir()
    for edge_population_name, edge_population in circuit.edges.items():
        if edge_population.target.name == node_population_name:
            edges = edge_population.afferent_edges(node_id, ['afferent_section_pos'])
            edges = edges.assign(afferent_section_pos=node_id)
            edges.to_json(edges_path / (edge_population_name + '.json'))

    morphology_path = reduced_dir / 'morphology' / '{}.swc'.format(node_id)
    morphology_path.parent.mkdir()
    morphology_path.touch()
    biophys_path = reduced_dir / 'biophys' / '{}.hoc'.format(node_id)
    biophys_path.parent.mkdir()
    biophys_path.touch()


@patch('sonata_network_reduction.network_reduction.reduce_node', new=_reduce_node_mock)
def test_save_network(circuit_9cells):
    _, circuit_config_path, _ = circuit_9cells
    with tempfile.TemporaryDirectory() as tmp_dirpath:
        tmp_dirpath = Path(tmp_dirpath) / 'reduced'
        reduce_network(circuit_config_path, tmp_dirpath, reduction_frequency=0)
        reduced_circuit = Circuit(tmp_dirpath / circuit_config_path.name)

        morph_dir = Path(reduced_circuit.config['components']['morphologies_dir'])
        biophys_dir = Path(reduced_circuit.config['components']['biophysical_neuron_models_dir'])
        for node_id in reduced_circuit.nodes['cortex'].ids():
            assert morph_dir.joinpath(str(node_id) + '.swc').is_file()
            assert biophys_dir.joinpath(str(node_id) + '.hoc').is_file()
            assert reduced_circuit.nodes['cortex'].get(node_id)['model_template'] == 'dummy'
            for edge_population in reduced_circuit.edges.values():
                if edge_population.target.name == 'cortex':
                    edges = edge_population.afferent_edges(node_id, ['afferent_section_pos'])
                    assert (edges['afferent_section_pos'] == node_id).all()


def _subtree_reductor_mock(cell, synapses, netcons, **kwargs):
    """make reduction a blank operation that just returns the original"""
    return cell, synapses, netcons


@patch('neuron_reduce.subtree_reductor', new=_subtree_reductor_mock)
def test_save_node(circuit_9cells):
    _, circuit_config_path, circuit = circuit_9cells
    with compile_circuit_mod_files(circuit), tempfile.TemporaryDirectory() as tmp_dirpath:
        tmp_dirpath = Path(tmp_dirpath)
        _reduce_node_same_process(
            0, tmp_dirpath, 'cortex', circuit_config_path, reduction_frequency=0)

        # node stayed the same except new names for 'model_template' and 'morphology'
        original_node = circuit.nodes['cortex'].get(0)
        reduced_node = pd.read_json(tmp_dirpath / 'node' / '0.json', typ='series')
        assert reduced_node['morphology'] == 'Scnn1a_473845048_m_0'
        assert reduced_node['model_template'] == 'hoc:Cell_472363762_0'
        assert original_node.drop(['model_template', 'morphology']) \
                   .equals(reduced_node.drop(['model_template', 'morphology'])) is True

        # edges stayed the same
        edge_populations_names = ['excvirt_cortex', 'inhvirt_cortex']
        for population_name in edge_populations_names:
            reduced_edges = pd.read_json(tmp_dirpath / 'edges' / (population_name + '.json'))
            original_edges = circuit.edges[population_name] \
                .afferent_edges(0, reduced_edges.columns.values)
            original_edges.to_json(tmp_dirpath / 'original_{}.json'.format(population_name))
            assert np.allclose(original_edges.to_numpy(), reduced_edges.to_numpy()) is True

        # morphology stayed the same
        morph_dirpath = Path(circuit.config['components']['morphologies_dir'])
        original_morph_file = morph_dirpath / 'Scnn1a_473845048_m.swc'
        reduced_morph_file = tmp_dirpath / 'morphology' / 'Scnn1a_473845048_m_0.swc'
        assert not diff(original_morph_file, reduced_morph_file) is True
