import glob
import os
import shutil
import tempfile

import neuron
from bluepyopt.ephys.models import HocCellModel
from neuron import h

import helpers.utils as utils
from network_reduction import NodePopulationReduction, reduce_network
from sonata_network_reduction.node_reduction import BiophysNodeReduction
from sonata_network_reduction.sonata_api import SonataApi


class Test9CellsClass:

    @classmethod
    def setup_class(cls):
        current_dirpath = os.path.dirname(os.path.abspath(__file__))
        config_dirpath = os.path.join(current_dirpath, 'data', '9cells')
        cls.circuit_config_filepath = os.path.join(config_dirpath, 'circuit_config.json')
        cls.simulation_config_filepath = os.path.join(config_dirpath, 'simulation_config.json')
        cls.sonata_api = SonataApi(cls.circuit_config_filepath, cls.simulation_config_filepath)

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

    def _create_node_population_reduction(self, population_name):
        return NodePopulationReduction(
            self.sonata_api.circuit.nodes[population_name], self.sonata_api)

    def _create_node_reduction(self, population_name, node_id):
        population_reduction = self._create_node_population_reduction(population_name)
        return BiophysNodeReduction(node_id, population_reduction)

    def test_instantiate_cortex_gid_0(self):
        biophys_cell = self._create_node_reduction('cortex', 0)
        biophys_cell._instantiate()
        assert hasattr(h, biophys_cell.template_name)
        assert len(biophys_cell.get_section_list()) == 123
        assert len(biophys_cell.edges_reduction) == 143

    def test_instantiate_cortex_gid_4(self):
        biophys_cell = self._create_node_reduction('cortex', 4)
        biophys_cell._instantiate()
        assert hasattr(h, biophys_cell.template_name)
        assert len(biophys_cell.get_section_list()) == 64
        assert len(biophys_cell.edges_reduction) == 144

    def test_instantiate_cortex_gid_7(self):
        biophys_cell = self._create_node_reduction('cortex', 7)
        biophys_cell._instantiate()
        assert hasattr(h, biophys_cell.template_name)
        assert len(biophys_cell.get_section_list()) == 38
        assert len(biophys_cell.edges_reduction) == 139

    def test_reduce_cortex_gid_0(self):
        biophys_cell = self._create_node_reduction('cortex', 0)
        biophys_cell._instantiate()
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
        print(reduced_sections_len)

    def test_reduce_network(self):
        node_expected_sec_len = {0: 13, 1: 13, 2: 13, 3: 7, 4: 7, 5: 7, 6: 7, 7: 7, 8: 7}
        with tempfile.TemporaryDirectory() as out_dirpath:
            reduce_network(self.sonata_api, out_dirpath)

            out_sonata_api = SonataApi(
                os.path.join(out_dirpath, os.path.basename(self.circuit_config_filepath)),
                os.path.join(out_dirpath, os.path.basename(self.simulation_config_filepath)))
            node_population = out_sonata_api.circuit.nodes['cortex']
            for node_id in node_population.ids():
                node = node_population.get(node_id)
                morph_filename = node['morphology'] + '.swc'
                biophys_filename = os.path.basename(node['model_template'])
                morph_filepath = glob.glob(out_dirpath + '/**/' + morph_filename, recursive=True)
                assert len(morph_filepath) == 1
                morph_filepath = morph_filepath[0]
                biophys_filepath = glob.glob(
                    out_dirpath + '/**/' + biophys_filename, recursive=True)
                assert len(biophys_filepath) == 1
                biophys_filepath = biophys_filepath[0]

                model = HocCellModel(
                    'node_' + str(node_id),
                    morph_filepath,
                    biophys_filepath
                )
                model.instantiate(neuron)
                actual_sec_len = len(model.icell.soma[0].wholetree())
                assert actual_sec_len == node_expected_sec_len[node_id]
