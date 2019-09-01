import os
from abc import ABCMeta, abstractmethod

import h5py
import neuron
import neuron_reduce
from aibs_circuit_converter import convert_to_hoc
from bluepyopt.ephys import create_hoc
from bluepyopt.ephys.models import CellModel, HocCellModel
from bluepyopt.ephys.morphologies import NrnFileMorphology
from hoc2swc import neuron2swc
from neuron import h

from biophysics import extract
from sonata_network_reduction import utils
from sonata_network_reduction.node_population import NodePopulation
from sonata_network_reduction.nrn_synapse import NrnIncomingSynapses


class NrnCell(metaclass=ABCMeta):

    def __init__(self, node_id, population: NodePopulation):
        self.node_id = node_id
        self.population = population
        self.node = self.population.get_node(self.node_id)
        self.nrn = None

    @abstractmethod
    def instantiate(self):
        pass


class BiophysCell(NrnCell):

    def __init__(self, node_id, population: NodePopulation):
        super().__init__(node_id, population)
        self._ephys_model = None
        self.incoming_synapses = NrnIncomingSynapses(self, population.get_incoming_edges(node_id))

    @property
    def morphology_filename(self):
        return self.node['morphology'] + '.swc'

    @property
    def morphology_filepath(self):
        return os.path.join(
            self.population.get_circuit_component('morphologies_dir'),
            self.morphology_filename
        )

    @property
    def biophys_filename(self):
        return os.path.basename(self.biophys_filepath)

    @property
    def biophys_filepath(self):
        biophys_dir_path = self.population.get_circuit_component(
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

    def instantiate(self):
        self._instantiate_nrn_cell()
        self.incoming_synapses.instantiate()

    def _instantiate_nrn_cell(self):
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
        self.nrn = self._ephys_model.icell

    def reduce(self, *args, **kwargs):
        self.nrn, reduced_synapse_list, reduced_netcon_list = neuron_reduce.subtree_reductor(
            self.nrn,
            self.incoming_synapses.synapses,
            self.incoming_synapses.netcons,
            *args,
            *kwargs, )

        # reduced model always saved in .hoc
        if '.nml' in self.node['model_template']:
            self.node.at['model_template'] = self.node['model_template'].replace('.nml', '.hoc')
        self.incoming_synapses.reduce(reduced_synapse_list, reduced_netcon_list)

    def write_node(self, output_dirpath):
        filepath = os.path.join(output_dirpath, str(self.node_id) + '.json')
        self.node.to_json(filepath)

    def write_morphology(self, filepath):
        # assume here that only our cell is loaded in Neuron
        if not os.path.exists(filepath):
            neuron2swc(filepath)

    def write_biophysics(self, filepath):
        mechanisms, parameters = extract(self.get_section_list())
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


class VirtualCell(NrnCell):

    def _get_input_filepath(self):
        simulation_input = self.population.get_simulation_input()
        if simulation_input is None:
            raise ValueError('No input for population {}'.format(self.population.name))
        return simulation_input['input_file']

    def instantiate(self):
        input_filepath = self._get_input_filepath()
        with h5py.File(input_filepath, 'r') as f:
            gids = f['/spikes/gids']
            timestamps = f['/spikes/timestamps']
            time_units = timestamps.attrs['units']
            if time_units and time_units != 'ms':
                raise ValueError(
                    'Invalid time units for virtual cells in {}'.format(input_filepath))
            idx = gids[:] == self.node_id
            self._timestamp_list = timestamps[idx]

        time_vector = h.Vector(self._timestamp_list)
        self.nrn = h.VecStim()
        self.nrn.play(time_vector)
