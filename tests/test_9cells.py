import os
import shutil

import numpy as np
from neuron import h

import helpers.utils as utils
from sonata_network_reduction import SonataFacade
from sonata_network_reduction.hoc_cell import BiophysCell
from sonata_network_reduction.reduce import reduce_biophys_cell


class Test9CellsClass:

    @classmethod
    def setup_class(cls):
        current_dirpath = os.path.dirname(os.path.abspath(__file__))
        config_dirpath = os.path.join(current_dirpath, 'data', '9cells')
        circuit_config_filepath = os.path.join(config_dirpath, 'circuit_config.json')
        simulation_config_filepath = os.path.join(config_dirpath, 'simulation_config.json')
        cls.facade = SonataFacade(circuit_config_filepath, simulation_config_filepath)

        # load mod files for tests
        mod_dirpath = os.path.join(
            cls.facade.circuit_config['components']['mechanisms_dir'],
            'modfiles')
        tests_dirpath = os.path.dirname(os.path.abspath(__file__))
        cls._compiled_mod_dirpath, compiled_mod_filepath = utils.compile_mod_files(tests_dirpath, mod_dirpath)
        h.nrn_load_dll(compiled_mod_filepath)

    def teardown_class(cls):
        shutil.rmtree(cls._compiled_mod_dirpath)

    def test_instantiate_cortex_gid_0(self):
        population_name, gid = 'cortex', 0
        biophys_cell = self.facade.instantiate_hoc_cell(population_name, gid)
        assert isinstance(biophys_cell, BiophysCell)
        assert hasattr(h, biophys_cell.template_name)
        assert len(biophys_cell.get_section_list()) == 123
        assert len(biophys_cell.get_synapse_hoc_list()) == 143
        assert len(biophys_cell.get_netcon_hoc_list()) == 143

    def test_instantiate_cortex_gid_4(self):
        population_name, gid = 'cortex', 4
        biophys_cell = self.facade.instantiate_hoc_cell(population_name, gid)
        assert isinstance(biophys_cell, BiophysCell)
        assert hasattr(h, biophys_cell.template_name)
        assert len(biophys_cell.get_section_list()) == 64
        assert len(biophys_cell.get_synapse_hoc_list()) == 144
        assert len(biophys_cell.get_netcon_hoc_list()) == 144

    def test_instantiate_cortex_gid_7(self):
        population_name, gid = 'cortex', 7
        biophys_cell = self.facade.instantiate_hoc_cell(population_name, gid)
        assert isinstance(biophys_cell, BiophysCell)
        assert hasattr(h, biophys_cell.template_name)
        assert len(biophys_cell.get_section_list()) == 38
        assert len(biophys_cell.get_synapse_hoc_list()) == 139
        assert len(biophys_cell.get_netcon_hoc_list()) == 139

    def test_reduce_cortex_gid_0(self):
        population_name, gid = 'cortex', 0
        biophys_cell = self.facade.instantiate_hoc_cell(population_name, gid)
        original_sections_len = len(biophys_cell.get_section_list())
        run_params = self.facade.simulation_config['run']
        h.dt = run_params['dt']
        h.tstop = run_params['tstop']

        soma_v = h.Vector()
        soma_v.record(biophys_cell.get_hoc().soma[0](0.5)._ref_v)
        h.run()

        reduced_biophys_cell = reduce_biophys_cell(biophys_cell, 0)
        reduced_sections_len = len(reduced_biophys_cell.get_section_list())
        reduced_soma_v = h.Vector()
        reduced_soma_v.record(reduced_biophys_cell.get_hoc().soma[0](0.5)._ref_v)
        h.run()

        assert original_sections_len > reduced_sections_len
        assert np.allclose(soma_v, reduced_soma_v, 1e-5)
