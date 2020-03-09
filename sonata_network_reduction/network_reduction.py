"""Main API"""
import os
import json
import shutil
import warnings
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Iterable

import h5py
import pandas as pd
from bluepysnap.circuit import Circuit
from bluepysnap.edges import DYNAMICS_PREFIX as EDGES_DYNAMICS_PREFIX
from bluepysnap.nodes import DYNAMICS_PREFIX as NODES_DYNAMICS_PREFIX, NodePopulation
from sonata_network_reduction.node_reduction import reduce_node


def _get_biophys_node_ids(population: NodePopulation) -> List:
    """Gets ids of biophysics nodes.

    Args:
        population: node population

    Returns:
        List of node ids that have biophysics
    """
    node_ids = []
    for node_id in population.ids():
        node = population.get(node_id)
        has_morphology = node.get('morphology') is not None
        is_biophysical = node.get('model_type') == 'biophysical'
        if has_morphology or is_biophysical:
            node_ids.append(node_id)
    return node_ids


def _find_node_population_file(population_name: str, sonata_circuit: Circuit):
    for nodes in sonata_circuit.config['networks']['nodes']:
        if population_name in nodes['nodes_file']:
            return nodes['nodes_file']
    return None


def _find_edge_population_file(population_name: str, sonata_circuit: Circuit):
    for edges in sonata_circuit.config['networks']['edges']:
        if population_name in edges['edges_file']:
            return edges['edges_file']
    return None


def _overwrite_nodes(node_paths: Iterable[Path], node_population_name: str, circuit: Circuit):
    """Writes reduced nodes to their corresponding h5 files in circuit.

    Args:
        node_paths: iterable of tmp node .json files that contain reduced nodes
        node_population_name: name of node population
        circuit: sonata circuit
    """
    nodes_filepath = _find_node_population_file(node_population_name, circuit)
    with h5py.File(nodes_filepath, 'r+') as nodes_f:
        nodes_h5ref = nodes_f['/nodes/{}/0'.format(node_population_name)]
        for node_path in node_paths:
            node_id = int(node_path.stem)
            with node_path.open() as f:
                node = json.load(f)
            for name in node.keys():
                if name.startswith(NODES_DYNAMICS_PREFIX):
                    h5name = name.split(NODES_DYNAMICS_PREFIX)[1]
                    nodes_h5ref['dynamics_params/' + h5name][node_id] = node[name]
                else:
                    nodes_h5ref[name][node_id] = node[name]


def _overwrite_edges(edges_paths: Iterable[Path], circuit: Circuit):
    """Writes reduced edges to their corresponding h5 files in circuit.

    Args:
        edges_paths: iterable of tmp edge .json files that contain reduced edges
        circuit: sonata circuit
    """
    for edges_path in edges_paths:
        edge_population_name = edges_path.stem
        edge_population_filepath = _find_edge_population_file(edge_population_name, circuit)

        with h5py.File(edge_population_filepath, 'r+') as f:
            edges_h5ref = f['/edges/{}/0'.format(edge_population_name)]
            edges = pd.read_json(edges_path)
            edges.sort_index(inplace=True)
            dynamics_columns_idx = edges.columns.str.startswith(EDGES_DYNAMICS_PREFIX)
            dynamics_columns = edges.columns[dynamics_columns_idx]
            non_dynamics_columns = edges.columns[~dynamics_columns_idx]
            for column in non_dynamics_columns:
                edges_h5ref[column][edges.index] = edges[column].to_numpy()
            for column in dynamics_columns:
                h5name = column.split(EDGES_DYNAMICS_PREFIX)[1]
                edges_h5ref['dynamics_params/' + h5name][edges.index] = edges[column].to_numpy()


def _overwrite_morphologies(morph_paths: Iterable[Path], circuit: Circuit):
    """Moves reduced morphologies from their tmp dir to the circuit's 'morphologies_dir'

    Args:
        morph_paths: iterable of tmp morphology paths
        circuit: sonata circuit
    """
    morph_dir = Path(circuit.config['components']['morphologies_dir'])
    shutil.rmtree(morph_dir)
    morph_dir.mkdir()
    for morphology_path in morph_paths:
        shutil.move(str(morphology_path), morph_dir)


def _overwrite_biophys(biophys_paths: Iterable[Path], circuit: Circuit):
    """Moves reduced biophysics from their tmp dir to the circuit's 'biophysical_neuron_models_dir'

    Args:
        biophys_paths: iterable of tmp biophysics paths
        circuit: sonata circuit
    """
    biophys_dir = Path(circuit.config['components']['biophysical_neuron_models_dir'])
    shutil.rmtree(biophys_dir)
    biophys_dir.mkdir()
    for biophys_path in biophys_paths:
        shutil.move(str(biophys_path), biophys_dir)


def reduce_population(population: NodePopulation, circuit_config_file: Path, **reduce_kwargs):
    """ Reduces node population.

    Args:
        population: node population
        circuit_config_file: reduced sonata circuit config filepath
        **reduce_kwargs: arguments to pass to the underlying call of
            ``neuron_reduce.subtree_reductor`` like ``reduction_frequency``.
    """
    try:
        ids = _get_biophys_node_ids(population)
    except RuntimeError:
        warnings.warn(
            'Can\'t get node ids of "{}" population. Is it virtual?'.format(population.name))
        return
    if len(ids) <= 0:
        return

    with Pool(min(os.cpu_count(), 8)) as pool, TemporaryDirectory() as tmp_dirpath:
        tmp_dirpath = Path(tmp_dirpath)
        reduced_dirs = [tmp_dirpath / str(id) for id in ids]
        pool.starmap(partial(
            reduce_node,
            node_population_name=population.name,
            circuit_config_file=circuit_config_file,
            **reduce_kwargs),
            zip(ids, reduced_dirs))

        circuit = Circuit(str(circuit_config_file))
        _overwrite_nodes(tmp_dirpath.rglob('node/*.json'), population.name, circuit)
        _overwrite_edges(tmp_dirpath.rglob('edges/*.json'), circuit)
        _overwrite_morphologies(tmp_dirpath.rglob('morphology/*.*'), circuit)
        _overwrite_biophys(tmp_dirpath.rglob('biophys/*.*'), circuit)


def reduce_network(circuit_config_file: Path, reduced_dir: Path, **reduce_kwargs):
    """ Reduces the network represented by ``circuit_config_filepath`` param.

    Assumed that the circuit is represented by the parent directory of ``circuit_config_filepath``.
    The reduced network is saved to ``out_circuit_dir``.

    Args:
        circuit_config_file: path to Sonata circuit config file
        reduced_dir: path to a directory where to save the reduced network.
        **reduce_kwargs: arguments to pass to the underlying call of
            ``neuron_reduce.subtree_reductor`` like ``reduction_frequency``.
    """
    if reduced_dir.exists():
        raise ValueError('{} must not exist. Please delete it.'.format(reduced_dir))
    shutil.copytree(str(circuit_config_file.parent), str(reduced_dir))

    original_circuit = Circuit(str(circuit_config_file))
    reduced_circuit_config_file = reduced_dir / circuit_config_file.name
    for population in original_circuit.nodes.values():
        reduce_population(population, reduced_circuit_config_file, **reduce_kwargs)
