"""
Example code to show complete use case.
"""
import os

from bluepysnap.config import Config
from sonata.io import File

from sonata_network_reduction.hoc_cell import BiophysCell, VirtualCell
from sonata_network_reduction.synapse import Synapse


class SonataFacade:
    """
    """

    @staticmethod
    def get_node_key(population_name, node_id):
        return '{}_{}'.format(population_name, node_id)

    def __init__(self, circuit_config_filepath, simulation_config_filepath):
        self.circuit_config = Config.parse(circuit_config_filepath)
        self.simulation_config = Config.parse(simulation_config_filepath)

        # This is temporary. We should switch completely to Snap as soon as
        # it has the merging of node and node_type.
        data_files = []
        data_type_files = []
        for item in self.circuit_config['networks']['nodes']:
            data_files.append(item['nodes_file'])
            data_type_files.append(item['node_types_file'])
        for item in self.circuit_config['networks']['edges']:
            data_files.append(item['edges_file'])
            data_type_files.append(item['edge_types_file'])
        self._network = File(data_files, data_type_files)

        # TODO Keeping lots of virtual cells in virtual_hoc_cache is bad idea.
        # Especially for huge networks. We need somehow to extract virtual hoc
        # from NEURON by some reference.
        self._virtual_cell_cache = {}

    def instantiate_hoc_cell(self, population_name, gid):
        node = self.get_node(population_name, gid)
        if node['model_type'] == 'biophysical':
            return self._instantiate_biophys_cell(population_name, gid)
        elif node['model_type'] == 'virtual':
            return self._instantiate_virtual_cell(population_name, gid)
        raise ValueError('Unknown model_type ' + node['model_type'])

    def get_node(self, population_name, gid):
        nodes = self._network.nodes[population_name]
        return nodes.get_node_id(gid)

    def _instantiate_biophys_cell(self, population_name, gid):
        node = self.get_node(population_name, gid)

        biophys_dir_path = self.circuit_config['components']['biophysical_neuron_models_dir']
        _, biophys_relative_path = node['model_template'].split(':')
        biophys_filepath = os.path.join(biophys_dir_path, biophys_relative_path)

        morphology_filepath = os.path.join(
            self.circuit_config['components']['morphologies_dir'],
            node['morphology'] + '.swc'
        )

        biophys_cell = BiophysCell(biophys_filepath, morphology_filepath)
        biophys_cell.instantiate()
        biophys_cell.attach_synapses(self._collect_synapses(population_name, gid))
        return biophys_cell

    def _get_virtual_cell(self, population_name, node_id):
        node_key = SonataFacade.get_node_key(population_name, node_id)
        if node_key not in self._virtual_cell_cache:
            self._virtual_cell_cache[node_key] = \
                self._instantiate_virtual_cell(population_name, node_id)
        return self._virtual_cell_cache[node_key]

    def _instantiate_virtual_cell(self, population_name, node_id):
        virtual_cell = None
        for _, params in self.simulation_config['inputs'].items():
            if params['node_set'] == population_name:
                virtual_cell = VirtualCell(params['input_file'], node_id)
                virtual_cell.instantiate()
                break
        if virtual_cell is None:
            raise ValueError('Virtual cell in {} {} does not have an input'.
                             format(population_name, node_id))
        return virtual_cell

    def _collect_synapses(self, population_name, gid):
        """
        TODO switch to iter mechanism possibly? I think for the parallel case it must be done.
        :param population_name:
        :param gid:
        :return:
        """
        synapse_list = []
        for edge_population_name in self._network.edges.population_names:
            edge_population = self._network.edges[edge_population_name]
            if population_name == edge_population.source_population:
                synapse_list += self._collect_outcome_synapses(edge_population.get_targets(gid))
            elif population_name == edge_population.target_population:
                synapse_list += self._collect_income_synapses(edge_population.get_target(gid))
        return synapse_list

    def _collect_outcome_synapses(self, outcome_edge_list):
        import inspect
        method_name = inspect.stack()[0][3]
        raise NotImplementedError(method_name + ' is not implemented yet')

    def _collect_income_synapses(self, income_edge_list):
        synapse_list = []
        for edge in income_edge_list:
            synapse = Synapse(edge, self.circuit_config['components']['synaptic_models_dir'])
            source_node = self.get_node(edge.source_population, edge.source_node_id)
            if source_node['model_type'] == 'virtual':
                source_cell = self._get_virtual_cell(edge.source_population, edge.source_node_id)
                synapse.set_source_cell_hoc(source_cell.get_hoc())
            synapse_list.append(synapse)
        return synapse_list
