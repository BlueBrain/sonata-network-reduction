import shutil
import tempfile
from pathlib import Path

import neurom
from bluepysnap import Circuit
from neuron import h

from helpers import utils
from sonata_network_reduction.node_reduction import _get_morphology_filepath, _get_biophys_filepath
from sonata_network_reduction.network_reduction import reduce_network


def _get_node_section_map(node_population_name, sonata_circuit):
    node_section_map = {}
    node_population = sonata_circuit.nodes[node_population_name]
    for node_id in node_population.ids():
        node = node_population.get(node_id)
        morphology_filepath = _get_morphology_filepath(node, sonata_circuit)
        m = neurom.load_neuron(str(morphology_filepath))
        node_section_map[node_id] = neurom.get('number_of_sections', m)[0]
    return node_section_map


class Test9CellsClass:

    @classmethod
    def setup_class(cls):
        current_dirpath = Path(__file__).resolve().parent
        config_dirpath = current_dirpath.joinpath('data', '9cells')
        cls.circuit_config_filepath = config_dirpath.joinpath('bglibpy_circuit_config.json')
        cls.sonata_circuit = Circuit(str(cls.circuit_config_filepath))
        # load mod files for tests
        mod_dirpath = Path(cls.sonata_circuit.config['components']['mechanisms_dir'], 'modfiles')
        cls._compiled_mod_dirpath, compiled_mod_filepath = \
            utils.compile_mod_files(current_dirpath, mod_dirpath)
        h.nrn_load_dll(compiled_mod_filepath)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls._compiled_mod_dirpath)

    def test_reduce_network(self):
        node_population_name = 'cortex'

        original_node_sections = _get_node_section_map(node_population_name, self.sonata_circuit)

        with tempfile.TemporaryDirectory() as out_dirpath:
            out_dirpath = Path(out_dirpath)

            reduce_network(self.circuit_config_filepath, str(out_dirpath), reduction_frequency=0)
            reduced_sonata_circuit = Circuit(
                str(out_dirpath.joinpath(self.circuit_config_filepath.name)))
            reduced_node_sections = _get_node_section_map(
                node_population_name, reduced_sonata_circuit)
            for node_id, sections_num in original_node_sections.items():
                assert sections_num > reduced_node_sections[node_id]

            node_population = reduced_sonata_circuit.nodes[node_population_name]
            for node_id in node_population.ids():
                node = node_population.get(node_id)
                morphology_filepath = _get_morphology_filepath(node, reduced_sonata_circuit)
                assert morphology_filepath.is_file()
                biophys_filepath = _get_biophys_filepath(node, reduced_sonata_circuit)
                assert biophys_filepath.is_file()

                if not hasattr(h, biophys_filepath.stem):
                    h.load_file(str(biophys_filepath))
                biophys_class = getattr(h, biophys_filepath.stem)
                biophys_class(0, str(morphology_filepath.parent), morphology_filepath.name)

                for _, edge_population in reduced_sonata_circuit.edges.items():
                    edges = edge_population.afferent_edges(node_id, 'morpho_section_id_post')
                    assert edges.le(reduced_node_sections[node_id]).all()
