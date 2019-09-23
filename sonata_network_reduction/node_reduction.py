import os

import neuron
import neuron_reduce
from aibs_circuit_converter import convert_to_hoc
from bluepyopt.ephys import create_hoc
from bluepyopt.ephys.models import CellModel, HocCellModel
from bluepyopt.ephys.morphologies import NrnFileMorphology
from hoc2swc import neuron2swc

from biophysics import get_mechanisms_and_params
from sonata_network_reduction import utils
from sonata_network_reduction.network_reduction import NodePopulationReduction
from sonata_network_reduction.edge_reduction import IncomingEdgesReduction


class BiophysNodeReduction:

    def __init__(self, node_id, population_reduction: NodePopulationReduction):
        self.node_id = node_id
        self.population_reduction = population_reduction
        self.node = self.population_reduction.get_node(self.node_id)
        self.edges_reduction = IncomingEdgesReduction(
            self, population_reduction.get_incoming_edges(node_id))
        self._ephys_model = None
        self._is_reduced = False

    @property
    def morphology_filename(self):
        return self.node['morphology'] + '.swc'

    @property
    def morphology_filepath(self):
        return os.path.join(
            self.population_reduction.get_circuit_component('morphologies_dir'),
            self.morphology_filename
        )

    @property
    def biophys_filename(self):
        return os.path.basename(self.biophys_filepath)

    @property
    def biophys_filepath(self):
        biophys_dir_path = self.population_reduction.get_circuit_component(
            'biophysical_neuron_models_dir')
        if ':' in self.node['model_template']:
            # this ':' is an artifact from official Sonata example networks
            _, biophys_filename = self.node['model_template'].split(':')
        else:
            biophys_filename = self.node['model_template']
        return os.path.join(biophys_dir_path, biophys_filename)

    @property
    def template_name(self):
        biophys_name = os.path.splitext(self.biophys_filename)[0]
        morphology_name = os.path.splitext(self.morphology_filename)[0]
        return '{}_{}'.format(
            utils.to_valid_nrn_name(biophys_name),
            utils.to_valid_nrn_name(morphology_name))

    def get_section_list(self):
        return self.nrn.soma[0].wholetree()

    @property
    def nrn(self):
        model = self._ephys_model
        if not model:
            return None
        return model.icell

    def _instantiate(self):
        self._instantiate_node()
        self.edges_reduction.instantiate()

    def _instantiate_node(self):
        biophys_filename = self.biophys_filename.lower()
        if biophys_filename.endswith('.nml'):
            biophysics = convert_to_hoc.load_neuroml(self.biophys_filepath)
            mechanisms = convert_to_hoc.define_mechanisms(biophysics)
            parameters = convert_to_hoc.define_parameters(biophysics)
            self._ephys_model = CellModel(
                self.template_name,
                NrnFileMorphology(self.morphology_filepath),
                mechanisms,
                parameters,
                self.node_id
            )
        elif biophys_filename.endswith('.hoc'):
            self._ephys_model = HocCellModel(
                self.template_name,
                self.morphology_filepath,
                self.biophys_filepath
            )
            self._ephys_model.morphology = NrnFileMorphology(self.morphology_filepath)
        else:
            raise ValueError('Unsupported biophysics file {}'.format(self.biophys_filepath))
        self._ephys_model.instantiate(neuron)

    def reduce(self, *args, **kwargs):
        if self._is_reduced:
            raise RuntimeError('Reduction can be done only once and it is irreversible')
        if not self.nrn:
            self._instantiate()
        self._ephys_model.icell, reduced_synapse_list, reduced_netcon_list = \
            neuron_reduce.subtree_reductor(
                self.nrn,
                self.edges_reduction.synapses,
                self.edges_reduction.netcons,
                *args,
                *kwargs, )

        # reduced model always saved in .hoc
        if '.nml' in self.node['model_template']:
            self.node.at['model_template'] = self.node['model_template'].replace('.nml', '.hoc')
        self.edges_reduction.reduce(reduced_synapse_list, reduced_netcon_list)
        self._is_reduced = True

    def write_node(self, output_dirpath):
        filepath = os.path.join(output_dirpath, str(self.node_id) + '.json')
        self.node.to_json(filepath)

    def write_morphology(self, filepath):
        neuron2swc(filepath)

    def write_biophysics(self, filepath):
        mechanisms, parameters = get_mechanisms_and_params(self.get_section_list())
        if self._ephys_model.morphology.do_replace_axon:
            replace_axon = self._ephys_model.morphology.replace_axon_hoc
        else:
            replace_axon = None

        biophysics = create_hoc.create_hoc(
            mechs=mechanisms,
            parameters=parameters,
            morphology=self.morphology_filename,
            replace_axon=replace_axon,
            template_name=self.template_name)

        with open(filepath, 'w') as f:
            f.write(biophysics)
