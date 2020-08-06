import tempfile
from pathlib import Path
from unittest.mock import patch
import warnings
import h5py
import pandas as pd

import neurom
from bluepysnap import Circuit, Config
from neuron import h

import pytest

from sonata_network_reduction.exceptions import ReductionError
from sonata_network_reduction.network_reduction import reduce_network
from sonata_network_reduction.node_reduction import _reduce_node_same_process, \
    _get_biophys_filepath, _get_morphology_filepath

from utils import TEST_DATA_DIR, copy_circuit, compile_circuit_mod_files

circuit_config_file = TEST_DATA_DIR / '9cells' / 'circuit_config.json'


def _get_node_section_map(node_population_name, sonata_circuit):
    node_section_map = {}
    node_population = sonata_circuit.nodes[node_population_name]
    for node_id in node_population.ids():
        node = node_population.get(node_id)
        morphology_file = _get_morphology_filepath(node, sonata_circuit)
        m = neurom.load_neuron(str(morphology_file))
        node_section_map[node_id] = neurom.get('number_of_sections', m)[0]
    return node_section_map


def test_reduce_node_inplace():
    circuit = Circuit(circuit_config_file)
    original_node_sections = _get_node_section_map('cortex', circuit)

    with compile_circuit_mod_files(circuit), copy_circuit(circuit_config_file) \
            as (_, copied_circuit_config_file):
        _reduce_node_same_process(1, 'cortex', copied_circuit_config_file, reduction_frequency=0)
        copied_circuit = Circuit(str(copied_circuit_config_file))
        node_population = copied_circuit.nodes['cortex']
        reduced_node = node_population.get(1)
        assert reduced_node['model_template'].endswith('_1')
        assert reduced_node['morphology'].endswith('_1')

        copied_node_sections = _get_node_section_map('cortex', copied_circuit)
        assert copied_node_sections[1] < original_node_sections[1]
        for node_id in set(node_population.ids()) - {1}:
            assert original_node_sections[node_id] == copied_node_sections[node_id]
        for edges in copied_circuit.edges.values():
            assert edges.afferent_edges(1, 'afferent_section_id') \
                .lt(original_node_sections[1]).all()


def test_reduce_network_success():
    circuit = Circuit(circuit_config_file)
    node_population_name = 'cortex'
    original_node_sections = _get_node_section_map(node_population_name, circuit)

    with compile_circuit_mod_files(circuit), tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir) / 'reduced'

        reduce_network(circuit_config_file, tmp_dir, reduction_frequency=0)
        reduced_circuit = Circuit(str(tmp_dir / circuit_config_file.name))
        reduced_node_sections = _get_node_section_map(node_population_name, reduced_circuit)
        for node_id, sections_num in original_node_sections.items():
            assert sections_num > reduced_node_sections[node_id]

        node_population = reduced_circuit.nodes[node_population_name]
        for node_id in node_population.ids():
            node = node_population.get(node_id)
            morphology_file = _get_morphology_filepath(node, reduced_circuit)
            assert morphology_file.stem.endswith('_' + str(node_id))
            assert morphology_file.is_file()
            biophys_file = _get_biophys_filepath(node, reduced_circuit)
            assert biophys_file.stem.endswith('_' + str(node_id))
            assert biophys_file.is_file()

            if not hasattr(h, biophys_file.stem):
                h.load_file(str(biophys_file))
            biophys_class = getattr(h, biophys_file.stem)
            biophys_class(0, str(morphology_file.parent), morphology_file.name)

            for edge_population in reduced_circuit.edges.values():
                edges = edge_population.afferent_edges(node_id, 'afferent_section_id')
                assert edges.le(reduced_node_sections[node_id]).all()


def _reduce_node_failed_mock(
        node_id, node_population_name, circuit_config_file, reduced_dir, **reduce_kwargs):
    if node_id == 7:
        raise RuntimeError('dummy')


@patch('sonata_network_reduction.network_reduction.reduce_node', new=_reduce_node_failed_mock)
def test_reduce_network_failed_node():
    with warnings.catch_warnings(record=True) as w_list, tempfile.TemporaryDirectory() as tmp_dir:
        reduce_network(circuit_config_file, Path(tmp_dir) / 'reduced', reduction_frequency=0)
        w_filtered = [w for w in w_list if 'reduction of node 7 failed' in str(w.message)]
        assert len(w_filtered) == 1, 'warning of a failed node reduction is missing'


def _reduce_node_failed_mock(
        node_id, node_population_name, circuit_config_file, reduced_dir, **reduce_kwargs):
    raise RuntimeError('dummy')


@patch('sonata_network_reduction.network_reduction.reduce_node', new=_reduce_node_failed_mock)
def test_reduce_network_abort():
    with tempfile.TemporaryDirectory() as tmp_dir, pytest.raises(ReductionError) as e:
        reduce_network(circuit_config_file, Path(tmp_dir) / 'reduced', reduction_frequency=0)
    assert 'Reached max number of failed reduced nodes' in e.value.args[0]


def _reduce_node_mock(
        node_id, node_population_name, circuit_config_file, reduced_dir, **reduce_kwargs):
    reduced_dir.mkdir(parents=True)

    node = pd.Series({'model_template': 'dummy'})
    node_file = reduced_dir / 'node' / '{}.json'.format(node_id)
    node_file.parent.mkdir()
    node.to_json(node_file)

    edges_dir = reduced_dir / 'edges'
    edges_dir.mkdir()
    edges = pd.DataFrame({"afferent_section_pos": {str(node_id): node_id}})
    edges.to_json(edges_dir / 'excvirt_cortex.json')

    morphology_file = reduced_dir / 'morphology' / '{}.swc'.format(node_id)
    morphology_file.parent.mkdir()
    morphology_file.touch()
    biophys_file = reduced_dir / 'biophys' / '{}.hoc'.format(node_id)
    biophys_file.parent.mkdir()
    biophys_file.touch()


@patch('sonata_network_reduction.network_reduction.reduce_node', new=_reduce_node_mock)
def test_save_network():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir) / 'reduced'
        reduce_network(circuit_config_file, tmp_dir, reduction_frequency=0)
        reduced_circuit = Circuit(tmp_dir / circuit_config_file.name)

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


def test_reduce_network_failed_validation():
    circuit = Circuit(circuit_config_file)
    with copy_circuit(circuit_config_file) as (_, copied_circuit_config_file):
        copied_config = Config(copied_circuit_config_file).resolve()
        with h5py.File(copied_config['networks']['nodes'][0]['nodes_file'], 'r+') as h5f:
            del h5f['/nodes/cortex/node_type_id']
        with compile_circuit_mod_files(circuit), tempfile.TemporaryDirectory() as tmp_dir, \
                pytest.raises(ReductionError) as e:
            tmp_dir = Path(tmp_dir) / 'reduced'
            reduce_network(copied_circuit_config_file, tmp_dir, reduction_frequency=0)
            assert f'{copied_circuit_config_file} is invalid SONATA circuit' in e.value.args[0]
