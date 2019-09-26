"""Main API"""
import json
import tempfile
from distutils.dir_util import copy_tree
from functools import partial
from multiprocessing import Pool
from pathlib import Path

import h5py
import pandas as pd
from bluepysnap.edges import DYNAMICS_PREFIX as EDGES_DYNAMICS_PREFIX
from bluepysnap.nodes import DYNAMICS_PREFIX as NODES_DYNAMICS_PREFIX
from cached_property import cached_property

from sonata_network_reduction.sonata_api import SonataApi


class NodePopulationReduction:
    """Wrapper around node population for reduction"""

    def __init__(self, population, sonata_api, out_circuit_dirpath, **kwargs):
        self._population = population
        self._sonata_api = sonata_api
        self._out_circuit_dirpath = out_circuit_dirpath
        self._reduce_kwargs = kwargs

    @cached_property
    def name(self):
        """Returns: name of corresponding node population"""
        return self._population.name

    def get_node(self, node_id: int):
        """
        Args:
            node_id: node id
        Returns:
            Node as pandas.Series
        """
        return self._population.get(node_id)

    def get_circuit_component(self, component: str):
        """
        Args:
            component: name of circuit's component like 'morphologies'.
        Returns:
            Corresponding config value of component
        """
        return self._sonata_api.circuit_config['components'][component]

    def get_biophys_node_ids(self):
        """
        Returns:
            list of node ids that have biophysical model type
        """
        return [node_id for node_id in self._population.ids()
                if self._population.get(node_id).model_type == 'biophysical']

    def get_incoming_edges(self, node_id: int):
        """Delegates to :func:`~sonata_api.SonataApi.get_incoming_edges`.

        Args:
            node_id: node id
        Returns:
            see delegation
        """
        return self._sonata_api.get_incoming_edges(self.name, node_id)

    def reduce(self):
        """ Performs the reduction.

        This action is irreversible and can't be done twice to the same instance.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            nodes_dirpath = Path(tmp_dir, 'nodes')
            nodes_dirpath.mkdir()
            edges_dirpath = Path(tmp_dir, 'edges')
            edges_dirpath.mkdir()

            with Pool(maxtasksperchild=1) as pool:
                pool.map(partial(
                    self._reduce_node,
                    nodes_dirpath=nodes_dirpath,
                    edges_dirpath=edges_dirpath),
                    self.get_biophys_node_ids())
            self._write_reduced_nodes(nodes_dirpath)
            self._write_reduced_edges(edges_dirpath)

    def _reduce_node(self, node_id: int, nodes_dirpath: Path, edges_dirpath: Path):
        """Reduces single node and writes the reduced to temp files.

        Reduced morphology and biophysics are written directly to the new reduced network.
        Args:
            node_id: node id
            nodes_dirpath: Temp dir for serialized nodes
            edges_dirpath: Temp dir for serialized edges
        """
        # pylint: disable=import-outside-toplevel
        from sonata_network_reduction.node_reduction import BiophysNodeReduction

        biophys_node = BiophysNodeReduction(node_id, self)
        biophys_node.reduce(**self._reduce_kwargs)

        biophys_node.write_node(nodes_dirpath)
        edges_dirpath = Path(edges_dirpath, str(biophys_node.node_id))
        edges_dirpath.mkdir(exist_ok=True)
        biophys_node.edges_reduction.write(edges_dirpath)

        biophysics_filepath = self._sonata_api.get_output_filepath(
            biophys_node.biophys_filepath, self._out_circuit_dirpath)
        biophys_node.write_biophysics(biophysics_filepath)
        morphology_filepath = self._sonata_api.get_output_filepath(
            biophys_node.morphology_filepath, self._out_circuit_dirpath)
        biophys_node.write_morphology(morphology_filepath)

    def _write_reduced_nodes(self, nodes_dirpath: Path):
        """Collects all reduced nodes from temp files and write them to the reduced network.

        Args:
            nodes_dirpath: Temp dir with serialized nodes
        """
        nodes_filepath = self._sonata_api.get_population_output_filepath(
            self._population, self._out_circuit_dirpath)
        with h5py.File(nodes_filepath, 'r+') as nodes_f:
            nodes_h5ref = nodes_f['/nodes/{}/0'.format(self.name)]
            for node_file in nodes_dirpath.rglob('*.json'):
                node_id = int(node_file.stem)
                with node_file.open() as f:
                    node = json.load(f)
                for name in node.keys():
                    if name.startswith(NODES_DYNAMICS_PREFIX):
                        h5name = name.split(NODES_DYNAMICS_PREFIX)[1]
                        nodes_h5ref['dynamics_params/' + h5name][node_id] = node[name]
                    else:
                        nodes_h5ref[name][node_id] = node[name]

    def _write_reduced_edges(self, edges_dirpath: Path):  # pylint: disable=too-many-locals
        """Collects all reduced edges from temp files and write them to the reduced network.

        Args:
            edges_dirpath: Temp dir with serialized edges
        """
        for edges_path in edges_dirpath.rglob('*.json'):
            edge_population_name = edges_path.stem
            edge_population = self._sonata_api.circuit.edges[edge_population_name]
            edge_population_filepath = self._sonata_api.get_population_output_filepath(
                edge_population, self._out_circuit_dirpath)

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


def reduce_network(sonata_api: SonataApi, out_circuit_dirpath: str, **reduce_kwargs):
    """ Reduces the network represented by ``sonata_api`` param.

    The reduced network is saved to ``out_circuit_dirpath``.

    Args:
        sonata_api: SonataApi instance of the target
        out_circuit_dirpath: path to a directory where to save the reduced.
        **reduce_kwargs: arguments to pass to the underlying call of
            ``neuron_reduce.subtree_reductor`` like ``reduction_frequency``.
    """
    out_circuit_dirpath = Path(out_circuit_dirpath)
    if out_circuit_dirpath.exists() and any(out_circuit_dirpath.iterdir()):
        raise ValueError('{} is not empty. It must be empty.'.format(out_circuit_dirpath))
    out_circuit_dirpath.mkdir(exist_ok=True)
    copy_tree(str(sonata_api.config_dirpath), str(out_circuit_dirpath))

    population_reductions = [
        NodePopulationReduction(population, sonata_api, out_circuit_dirpath, **reduce_kwargs)
        for population in sonata_api.circuit.nodes.values()
        if not sonata_api.is_virtual_node_population(population.name)]

    for population_reduction in population_reductions:
        population_reduction.reduce()
