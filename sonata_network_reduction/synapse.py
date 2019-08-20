import json
import os


class Synapse:
    def __init__(self, sonata_edge, dynamics_params_dirpath):
        self.sonata_edge = sonata_edge
        self.dynamics_params = self._collect_dynamics_params(dynamics_params_dirpath)
        self._source_cell_hoc = None

    def _collect_dynamics_params(self, dynamics_params_dirpath):
        dynamics_params_filename = self.sonata_edge['dynamics_params']
        dynamics_params_filepath = os.path.join(dynamics_params_dirpath, dynamics_params_filename)
        with open(dynamics_params_filepath) as f:
            dynamics_params = json.load(f)
        dynamics_params.pop('level_of_detail')
        return dynamics_params

    def set_source_cell_hoc(self, source_cell_hoc):
        self._source_cell_hoc = source_cell_hoc

    def get_source_cell_hoc(self):
        return self._source_cell_hoc
