"""Module that writes results ``node_reduction.reduce_node`` to SONATA circuit"""
import json
import shutil
from pathlib import Path
from typing import Iterable, Dict

import h5py
import numpy as np
import pandas as pd
from bluepysnap import Config
from bluepysnap.edges import DYNAMICS_PREFIX as EDGES_DYNAMICS_PREFIX
from bluepysnap.nodes import DYNAMICS_PREFIX as NODES_DYNAMICS_PREFIX


def _find_node_population_file(population_name: str, circuit_config: Dict):
    for nodes in circuit_config['networks']['nodes']:
        with h5py.File(nodes['nodes_file'], 'r') as h5f:
            if population_name in h5f['/nodes']:
                return nodes['nodes_file']
    return None


def _find_edge_population_file(population_name: str, circuit_config: Dict):
    for edges in circuit_config['networks']['edges']:
        with h5py.File(edges['edges_file'], 'r') as h5f:
            if population_name in h5f['/edges']:
                return edges['edges_file']
    return None


def _overwrite_nodes(node_paths: Iterable[Path], node_population_name: str, circuit_config: Dict):
    """Writes reduced nodes to their corresponding h5 files in circuit_config.

    Args:
        node_paths: iterable of tmp node .json files that contain reduced nodes
        node_population_name: name of node population
        circuit_config: sonata circuit config
    """
    # pylint: disable=too-many-locals
    nodes_filepath = _find_node_population_file(node_population_name, circuit_config)
    with h5py.File(nodes_filepath, 'r+') as h5f:
        nodes_grp = h5f['/nodes/{}/0'.format(node_population_name)]
        for node_path in node_paths:
            node_id = int(node_path.stem)
            with node_path.open() as f:
                node = json.load(f)
            for name in node.keys():
                if name.startswith(NODES_DYNAMICS_PREFIX):
                    # plain dynamics node value
                    h5name = name.split(NODES_DYNAMICS_PREFIX)[1]
                    nodes_grp['dynamics_params/' + h5name][node_id] = node[name]
                else:
                    if '@library' in nodes_grp and name in nodes_grp['@library']:
                        # enum node value
                        library = nodes_grp['@library']
                        enum_name_indices = np.argwhere(library[name][:] == node[name])
                        if len(enum_name_indices) > 0:
                            nodes_grp[name][node_id] = enum_name_indices[0][0]
                        else:
                            enum_values = library[name][:]
                            enum_dtype = library[name].dtype
                            del library[name]
                            new_enum_values = np.append(enum_values, node[name])
                            library.create_dataset(name, dtype=enum_dtype, data=new_enum_values)
                            # because we append `node[name]` as the last enum value
                            enum_name_idx = len(new_enum_values) - 1
                            nodes_grp[name][node_id] = enum_name_idx
                    else:
                        # plain node value
                        nodes_grp[name][node_id] = node[name]


def _overwrite_edges(edges_paths: Iterable[Path], circuit_config: Dict):
    """Writes reduced edges to their corresponding h5 files in circuit_config.

    Args:
        edges_paths: iterable of tmp edge .json files that contain reduced edges
        circuit_config: sonata circuit config
    """
    for edges_path in edges_paths:
        edge_population_name = edges_path.stem
        edge_population_filepath = _find_edge_population_file(edge_population_name, circuit_config)

        with h5py.File(edge_population_filepath, 'r+') as h5f:
            edges_h5ref = h5f['/edges/{}/0'.format(edge_population_name)]
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


def _overwrite_morphologies(morph_paths: Iterable[Path], circuit_config: Dict):
    """Moves reduced morphologies from their tmp dir to the circuit_config's 'morphologies_dir'

    Args:
        morph_paths: iterable of tmp morphology paths
        circuit_config: sonata circuit config
    """
    morph_dir = Path(circuit_config['components']['morphologies_dir'])
    morph_dir.mkdir(exist_ok=True)
    for morphology_path in morph_paths:
        shutil.move(str(morphology_path), morph_dir)


def _overwrite_biophys(biophys_paths: Iterable[Path], circuit_config: Dict):
    """Moves reduced biophysics from their tmp dir to the circuit's 'biophysical_neuron_models_dir'

    Args:
        biophys_paths: iterable of tmp biophysics paths
        circuit_config: sonata circuit config
    """
    biophys_dir = Path(circuit_config['components']['biophysical_neuron_models_dir'])
    biophys_dir.mkdir(exist_ok=True)
    for biophys_path in biophys_paths:
        shutil.move(str(biophys_path), biophys_dir)


def write_reduced_to_circuit(
        reduced_node_dirpath: Path,
        circuit_config_file: Path,
        node_population_name: str):
    """Updates the circuit_config with the content of reduced node.

    Args:
        reduced_node_dirpath: dir that was used as ``reduced_dir`` for
        ``node_reduction.reduce_node``
        circuit_config_file: SONATA circuit_config config filepath
        node_population_name: node population name
    """
    config = Config(str(circuit_config_file)).resolve()
    _overwrite_nodes(reduced_node_dirpath.rglob('node/*.json'), node_population_name, config)
    _overwrite_edges(reduced_node_dirpath.rglob('edges/*.json'), config)
    _overwrite_morphologies(reduced_node_dirpath.rglob('morphology/*.*'), config)
    _overwrite_biophys(reduced_node_dirpath.rglob('biophys/*.*'), config)
