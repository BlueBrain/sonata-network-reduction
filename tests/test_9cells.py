import os
import shutil

import numpy as np
from neuron import h

import helpers.utils as utils
from node_population import NodePopulation
from sonata_network_reduction.sonata_api import SonataApi
from sonata_network_reduction.nrn_cell import BiophysCell


class Test9CellsClass:

    @classmethod
    def setup_class(cls):
        current_dirpath = os.path.dirname(os.path.abspath(__file__))
        config_dirpath = os.path.join(current_dirpath, 'data', '9cells')
        circuit_config_filepath = os.path.join(config_dirpath, 'circuit_config.json')
        simulation_config_filepath = os.path.join(config_dirpath, 'simulation_config.json')
        cls.sonata_api = SonataApi(circuit_config_filepath, simulation_config_filepath)

        # load mod files for tests
        mod_dirpath = os.path.join(
            cls.sonata_api.circuit_config['components']['mechanisms_dir'],
            'modfiles')
        tests_dirpath = os.path.dirname(os.path.abspath(__file__))
        cls._compiled_mod_dirpath, compiled_mod_filepath = \
            utils.compile_mod_files(tests_dirpath, mod_dirpath)
        h.nrn_load_dll(compiled_mod_filepath)

    def teardown_class(cls):
        shutil.rmtree(cls._compiled_mod_dirpath)

    def _create_biophys_cell(self, population_name, node_id):
        node_population = NodePopulation(
                self.sonata_api.circuit.nodes[population_name], self.sonata_api)
        return BiophysCell(node_id, node_population)

    def test_instantiate_cortex_gid_0(self):
        biophys_cell = self._create_biophys_cell('cortex', 0)
        biophys_cell.instantiate()
        assert hasattr(h, biophys_cell.template_name)
        assert len(biophys_cell.get_section_list()) == 123
        assert len(biophys_cell.incoming_synapses) == 143

    def test_instantiate_cortex_gid_4(self):
        biophys_cell = self._create_biophys_cell('cortex', 4)
        biophys_cell.instantiate()
        assert hasattr(h, biophys_cell.template_name)
        assert len(biophys_cell.get_section_list()) == 64
        assert len(biophys_cell.incoming_synapses) == 144

    def test_instantiate_cortex_gid_7(self):
        biophys_cell = self._create_biophys_cell('cortex', 7)
        biophys_cell.instantiate()
        assert hasattr(h, biophys_cell.template_name)
        assert len(biophys_cell.get_section_list()) == 38
        assert len(biophys_cell.incoming_synapses) == 139

    def test_reduce_cortex_gid_0(self):
        biophys_cell = self._create_biophys_cell('cortex', 0)
        biophys_cell.instantiate()
        original_sections_len = len(biophys_cell.get_section_list())
        run_params = self.sonata_api.simulation_config['run']
        h.dt = run_params['dt']
        h.tstop = run_params['tstop']

        soma_v = h.Vector()
        soma_v.record(biophys_cell.nrn.soma[0](0.5)._ref_v)
        h.run()

        biophys_cell.reduce(0)
        reduced_sections_len = len(biophys_cell.get_section_list())
        reduced_soma_v = h.Vector()
        reduced_soma_v.record(biophys_cell.nrn.soma[0](0.5)._ref_v)
        h.run()

        assert original_sections_len > reduced_sections_len
        assert np.allclose(soma_v, reduced_soma_v, 1e-5)
