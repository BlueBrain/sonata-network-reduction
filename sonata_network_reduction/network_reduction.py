import glob
import json
import os
import shutil
import tempfile
from functools import partial
from multiprocessing import Pool

import h5py
import pandas as pd
from bluepysnap.edges import DYNAMICS_PREFIX as EDGES_DYNAMICS_PREFIX
from bluepysnap.nodes import DYNAMICS_PREFIX as NODES_DYNAMICS_PREFIX
from cached_property import cached_property

from sonata_network_reduction import utils
from sonata_network_reduction.sonata_api import SonataApi


class ReductionContext:
    def __init__(self, out_circuit_dirpath):
        self.out_circuit_dirpath = out_circuit_dirpath
        self._tmp_dir = tempfile.TemporaryDirectory()

    def create_tmp_dir(self):
        os.makedirs(self.nodes_dirpath)
        os.makedirs(self.edges_dirpath)
        return self._tmp_dir

    @property
    def nodes_dirpath(self):
        return os.path.join(self._tmp_dir.name, 'nodes')

    @property
    def edges_dirpath(self):
        return os.path.join(self._tmp_dir.name, 'edges')


class NodePopulationReduction:
    def __init__(self, population, sonata_api):
        self._population = population
        self._sonata_api = sonata_api

    @cached_property
    def name(self):
        return self._population.name

    def get_node(self, node_id):
        return self._population.get(node_id)

    def is_virtual(self):
        return self.get_simulation_input() is not None

    def get_simulation_input(self):
        return self._sonata_api.get_simulation_input(self.name)

    def get_circuit_component(self, name):
        return self._sonata_api.circuit_config['components'][name]

    def get_biophys_node_ids(self):
        nodes = {node_id: self._population.get(node_id) for node_id in self._population.ids()}
        return [node_id for node_id, node in nodes.items()
                if getattr(node, 'model_type') == 'biophysical']

    def get_incoming_edges(self, node_id):
        def edges_to_df(edges):
            if not edges.keys():
                return pd.DataFrame()
            else:
                return pd.concat(edges.values(), keys=edges.keys(), names=['population', 'idx'])

        incoming_edges = {}
        for name, population in self._sonata_api.circuit.edges.items():
            properties = list(population.property_names)
            if population.target.name == self.name:
                incoming_edges[name] = population.afferent_edges(node_id, properties)

        return edges_to_df(incoming_edges)

    def reduce(self, out_circuit_dirpath):
        context = ReductionContext(out_circuit_dirpath)
        with context.create_tmp_dir():
            with Pool(maxtasksperchild=1) as pool:
                pool.map(
                    partial(self._reduce_node, context=context),
                    self.get_biophys_node_ids())
            self._write_reduced_nodes(context)
            self._write_reduced_edges(context)

    def _reduce_node(self, node_id, context: ReductionContext):
        from sonata_network_reduction.node_reduction import BiophysNodeReduction

        biophys_node = BiophysNodeReduction(node_id, self)
        biophys_node.reduce(0)

        biophys_node.write_node(context.nodes_dirpath)
        edges_dirpath = os.path.join(context.edges_dirpath, str(biophys_node.node_id))
        os.makedirs(edges_dirpath)
        biophys_node.edges_reduction.write(edges_dirpath)

        biophysics_filepath = self._sonata_api.get_output_filepath(
            biophys_node.biophys_filepath, context.out_circuit_dirpath)
        biophys_node.write_biophysics(biophysics_filepath)
        morphology_filepath = self._sonata_api.get_output_filepath(
            biophys_node.morphology_filepath, context.out_circuit_dirpath)
        biophys_node.write_morphology(morphology_filepath)

    def _write_reduced_nodes(self, context: ReductionContext):
        nodes_filepath = self._sonata_api.get_population_output_filepath(
            self._population, context.out_circuit_dirpath)
        with h5py.File(nodes_filepath, 'r+') as nodes_f:
            nodes_h5ref = nodes_f['/nodes/{}/0'.format(self.name)]
            node_files = glob.glob(os.path.join(context.nodes_dirpath, '*.json'))
            for node_file in node_files:
                node_id = int(utils.filename(node_file))
                with open(node_file) as f:
                    node = json.load(f)
                for name in node.keys():
                    if name.startswith(NODES_DYNAMICS_PREFIX):
                        h5name = name.split(NODES_DYNAMICS_PREFIX)[1]
                        nodes_h5ref['dynamics_params/' + h5name][node_id] = node[name]
                    else:
                        nodes_h5ref[name][node_id] = node[name]

    def _write_reduced_edges(self, context: ReductionContext):
        edges_files = glob.glob(os.path.join(context.edges_dirpath, '*/*.json'))
        for edges_file in edges_files:
            edge_population_name = utils.filename(edges_file)
            edge_population = self._sonata_api.circuit.edges[edge_population_name]
            edge_population_filepath = self._sonata_api.get_population_output_filepath(
                edge_population, context.out_circuit_dirpath)

            with h5py.File(edge_population_filepath, 'r+') as f:
                edges_h5ref = f['/edges/{}/0'.format(edge_population_name)]
                edges = pd.read_json(edges_file)
                dynamics_columns_idx = edges.columns.str.startswith(EDGES_DYNAMICS_PREFIX)
                dynamics_columns = edges.columns[dynamics_columns_idx]
                non_dynamics_columns = edges.columns[~dynamics_columns_idx]
                for column in non_dynamics_columns:
                    edges_h5ref[column][edges.index] = edges[column].to_numpy()
                for column in dynamics_columns:
                    h5name = column.split(EDGES_DYNAMICS_PREFIX)[1]
                    edges_h5ref['dynamics_params/' + h5name][edges.index] = edges[column].to_numpy()


def reduce_network(sonata_api: SonataApi, out_circuit_dirpath):
    shutil.rmtree(out_circuit_dirpath, ignore_errors=True)
    shutil.copytree(sonata_api.get_config_dirpath(), out_circuit_dirpath)

    population_reductions = [NodePopulationReduction(population, sonata_api)
                             for population in sonata_api.circuit.nodes.values()]
    population_reductions = [population for population in population_reductions
                             if not population.is_virtual()]
    for population_reduction in population_reductions:
        population_reduction.reduce(out_circuit_dirpath)


