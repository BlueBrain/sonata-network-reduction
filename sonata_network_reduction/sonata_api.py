import os

from bluepysnap.circuit import Circuit
from bluepysnap.config import Config


class SonataApi:
    @staticmethod
    def get_node_key(population_name, node_id):
        return '{}_{}'.format(population_name, node_id)

    def __init__(self, circuit_config_filepath, simulation_config_filepath):
        self.circuit_config = Config.parse(circuit_config_filepath)
        self.simulation_config = Config.parse(simulation_config_filepath)
        self.circuit = Circuit(circuit_config_filepath)

    def get_population_output_filepath(self, population, output_dirpath):
        return self.get_output_filepath(population._h5_filepath, output_dirpath)

    def get_output_filepath(self, filepath, output_dirpath):
        output_filepath = os.path.relpath(filepath, self.get_config_dirpath())
        return os.path.join(output_dirpath, output_filepath)

    def get_config_dirpath(self):
        return os.path.dirname(self.simulation_config['network'])

    def get_simulation_input(self, population_name):
        inputs = self.simulation_config.get('inputs')
        if not inputs:
            return None
        for _, params in inputs.items():
            if params['node_set'] == population_name:
                return params
        return None
