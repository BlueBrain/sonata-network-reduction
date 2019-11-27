"""Main API"""
import itertools
import json
import warnings
from distutils.dir_util import copy_tree
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from typing import List

import h5py
import pandas as pd
from bluepysnap.circuit import Circuit
from bluepysnap.edges import DYNAMICS_PREFIX as EDGES_DYNAMICS_PREFIX
from bluepysnap.nodes import DYNAMICS_PREFIX as NODES_DYNAMICS_PREFIX, NodePopulation
from sonata_network_reduction.node_reduction import reduce_node


def _get_biophys_node_ids(population: NodePopulation):
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


def _overwrite_nodes(
        node_path_list: List[Path], node_population_name: str, sonata_circuit: Circuit):
    """Writes reduced nodes to their corresponding h5 files in circuit.

    Deletes files from ``node_path_list`` after execution.

    Args:
        node_path_list: list of tmp node files that contain reduced nodes
        node_population_name: name of node population
        sonata_circuit: sonata circuit
    """
    nodes_filepath = _find_node_population_file(node_population_name, sonata_circuit)
    with h5py.File(nodes_filepath, 'r+') as nodes_f:
        nodes_h5ref = nodes_f['/nodes/{}/0'.format(node_population_name)]
        for node_path in node_path_list:
            node_id = int(node_path.stem)
            with node_path.open() as f:
                node = json.load(f)
            for name in node.keys():
                if name.startswith(NODES_DYNAMICS_PREFIX):
                    h5name = name.split(NODES_DYNAMICS_PREFIX)[1]
                    nodes_h5ref['dynamics_params/' + h5name][node_id] = node[name]
                else:
                    nodes_h5ref[name][node_id] = node[name]
            node_path.unlink()


def _overwrite_edges(edges_path_list: List[Path], sonata_circuit: Circuit):
    """Writes reduced edges to their corresponding h5 files in circuit.

    Deletes files from ``edges_path_list`` after execution.

    Args:
        edges_path_list: list of lists of tmp edge files that contain reduced edges
        sonata_circuit: sonata circuit
    """
    for edges_path in itertools.chain.from_iterable(edges_path_list):
        edge_population_name = edges_path.stem
        edge_population_filepath = _find_edge_population_file(edge_population_name, sonata_circuit)

        with h5py.File(edge_population_filepath, 'r+') as f:
            edges_h5ref = f['/edges/{}/0'.format(edge_population_name)]
            edges = pd.read_json(edges_path)
            dynamics_columns_idx = edges.columns.str.startswith(EDGES_DYNAMICS_PREFIX)
            dynamics_columns = edges.columns[dynamics_columns_idx]
            non_dynamics_columns = edges.columns[~dynamics_columns_idx]
            for column in non_dynamics_columns:
                edges_h5ref[column][edges.index] = edges[column].to_numpy()
            for column in dynamics_columns:
                h5name = column.split(EDGES_DYNAMICS_PREFIX)[1]
                edges_h5ref['dynamics_params/' + h5name][edges.index] = edges[column].to_numpy()
        edges_path.unlink()


def reduce_population(population: NodePopulation, sonata_circuit: Circuit, **reduce_kwargs):
    """ Reduces node population.

    Args:
        population: node population
        sonata_circuit: sonata circuit
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

    with Pool(maxtasksperchild=1) as pool:
        reduce_node_results = pool.map(partial(
            reduce_node,
            sonata_circuit=sonata_circuit,
            node_population_name=population.name,
            **reduce_kwargs),
            ids)

    node_list, edges_list = zip(*reduce_node_results)
    _overwrite_nodes(node_list, population.name, sonata_circuit)
    _overwrite_edges(edges_list, sonata_circuit)


def reduce_network(circuit_config_filepath: str, out_circuit_dirpath: str, **reduce_kwargs):
    """ Reduces the network represented by ``circuit_config_filepath`` param.

    The reduced network is saved to ``out_circuit_dirpath``.

    Args:
        circuit_config_filepath: path to Sonata circuit config file
        out_circuit_dirpath: path to a directory where to save the reduced.
        **reduce_kwargs: arguments to pass to the underlying call of
            ``neuron_reduce.subtree_reductor`` like ``reduction_frequency``.
    """
    out_circuit_dirpath = Path(out_circuit_dirpath)
    circuit_config_filepath = Path(circuit_config_filepath)
    if out_circuit_dirpath.exists() and any(out_circuit_dirpath.iterdir()):
        raise ValueError('{} is not empty. It must be empty.'.format(out_circuit_dirpath))
    out_circuit_dirpath.mkdir(exist_ok=True)
    copy_tree(str(circuit_config_filepath.parent), str(out_circuit_dirpath))

    sonata_circuit = Circuit(out_circuit_dirpath.joinpath(circuit_config_filepath.name))
    for population in sonata_circuit.nodes.values():
        reduce_population(population, sonata_circuit, **reduce_kwargs)
