import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch
import warnings
import h5py
import pandas as pd

import neurom
from bluepysnap import Circuit
from neuron import h

import pytest

from sonata_network_reduction.exceptions import ReductionError
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


def test_reduce_node_inplace(circuit_9cells):
    _, circuit_config_path, circuit = circuit_9cells
    original_node_sections = _get_node_section_map('cortex', circuit)

    with compile_circuit_mod_files(circuit), tempfile.TemporaryDirectory() as tmp_dirpath:
        circuit_copy_dirpath = Path(tmp_dirpath) / 'circuit_copy'
        shutil.copytree(str(circuit_config_path.parent), str(circuit_copy_dirpath))
        circuit_copy_config_path = circuit_copy_dirpath / circuit_config_path.name
        _reduce_node_same_process(1, 'cortex', circuit_copy_config_path, reduction_frequency=0)
        circuit_copy = Circuit(str(circuit_copy_config_path))
        node_population = circuit_copy.nodes['cortex']
        reduced_node = node_population.get(1)
        assert reduced_node['model_template'].endswith('_1')
        assert reduced_node['morphology'].endswith('_1')

        node_copy_sections = _get_node_section_map('cortex', circuit_copy)
        assert node_copy_sections[1] < original_node_sections[1]
        for node_id in set(node_population.ids()) - {1}:
            assert original_node_sections[node_id] == node_copy_sections[node_id]
        for edges in circuit_copy.edges.values():
            assert edges.afferent_edges(1, 'afferent_section_id') \
                .lt(original_node_sections[1]).all()


def test_reduce_network_success(circuit_9cells):
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
            assert morphology_filepath.stem.endswith('_' + str(node_id))
            assert morphology_filepath.is_file()
            biophys_filepath = _get_biophys_filepath(node, reduced_sonata_circuit)
            assert biophys_filepath.stem.endswith('_' + str(node_id))
            assert biophys_filepath.is_file()

            if not hasattr(h, biophys_filepath.stem):
                h.load_file(str(biophys_filepath))
            biophys_class = getattr(h, biophys_filepath.stem)
            biophys_class(0, str(morphology_filepath.parent), morphology_filepath.name)

            for edge_population in reduced_sonata_circuit.edges.values():
                edges = edge_population.afferent_edges(node_id, 'afferent_section_id')
                assert edges.le(reduced_node_sections[node_id]).all()


def _reduce_node_failed_mock(
        node_id, node_population_name, circuit_config_file, reduced_dir, **reduce_kwargs):
    if node_id == 7:
        raise RuntimeError('dummy')


@patch('sonata_network_reduction.network_reduction.reduce_node', new=_reduce_node_failed_mock)
def test_reduce_network_failed_node(circuit_9cells):
    _, circuit_config_path, _ = circuit_9cells
    with warnings.catch_warnings(record=True) as w, tempfile.TemporaryDirectory() as tmp_dirpath:
        warnings.filterwarnings('ignore', 'No biophys nodes*')
        reduce_network(circuit_config_path, Path(tmp_dirpath) / 'reduced', reduction_frequency=0)
        assert len(w) == 1
        message = str(w[0].message)
        assert 'dummy' in message and 'reduction of node 7 failed' in message


def _reduce_node_failed_mock(
        node_id, node_population_name, circuit_config_file, reduced_dir, **reduce_kwargs):
    raise RuntimeError('dummy')


@patch('sonata_network_reduction.network_reduction.reduce_node', new=_reduce_node_failed_mock)
def test_reduce_network_abort(circuit_9cells):
    _, circuit_config_path, _ = circuit_9cells
    with tempfile.TemporaryDirectory() as tmp_dirpath, pytest.raises(ReductionError) as e:
        reduce_network(circuit_config_path, Path(tmp_dirpath) / 'reduced', reduction_frequency=0)
    assert 'Reached max number of failed reduced nodes' in e.value.args[0]


def _reduce_node_mock(
        node_id, node_population_name, circuit_config_file, reduced_dir, **reduce_kwargs):
    reduced_dir.mkdir(parents=True)

    node = pd.Series({'model_template': 'dummy'})
    node_path = reduced_dir / 'node' / '{}.json'.format(node_id)
    node_path.parent.mkdir()
    node.to_json(node_path)

    edges_path = reduced_dir / 'edges'
    edges_path.mkdir()
    edges = pd.DataFrame({"afferent_section_pos": {str(node_id): node_id}})
    edges.to_json(edges_path / 'excvirt_cortex.json')

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
        node_ids = reduced_circuit.nodes['cortex'].ids()
        for node_id in node_ids:
            assert morph_dir.joinpath(str(node_id) + '.swc').is_file()
            assert biophys_dir.joinpath(str(node_id) + '.hoc').is_file()
            assert reduced_circuit.nodes['cortex'].get(node_id)['model_template'] == 'dummy'

        excvirt_edges_h5 = next(
            edges['edges_file'] for edges in reduced_circuit.config['networks']['edges']
            if 'excvirt_cortex' in edges['edges_file'])
        with h5py.File(excvirt_edges_h5) as h5f:
            mocked_pos = h5f['/edges/excvirt_cortex/0/afferent_section_pos'][node_ids].tolist()
            assert mocked_pos == node_ids.tolist()
