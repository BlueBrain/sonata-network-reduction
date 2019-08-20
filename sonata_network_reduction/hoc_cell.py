import os
from abc import ABCMeta, abstractmethod

import h5py
from neuron import h

from sonata_network_reduction import hoc_utils, utils


class HocCell(metaclass=ABCMeta):

    @abstractmethod
    def get_hoc(self):
        pass

    @abstractmethod
    def instantiate(self):
        pass


class BiophysCell(HocCell):
    def __init__(self, biophys_filepath=None, morphology_filepath=None):
        self._biophys_filepath = biophys_filepath
        self._morphology_filepath = morphology_filepath

        self._hoc = None
        self._synapse_hoc_list = []
        self._netcon_hoc_list = []

    @classmethod
    def from_hoc(cls, hoc, hoc_synapse_list, hoc_netcon_list):
        cell = BiophysCell()
        cell._hoc = hoc
        cell._synapse_hoc_list = hoc_synapse_list
        cell._netcon_hoc_list = hoc_netcon_list
        return cell

    @property
    def template_name(self):
        template_filename = os.path.basename(self._biophys_filepath)
        morphology_filename = os.path.basename(self._morphology_filepath)
        template_filename_no_ext = os.path.splitext(template_filename)[0]
        morphology_filename_no_ext = os.path.splitext(morphology_filename)[0]
        return '{}_{}'.format(
            utils.to_valid_var_name(template_filename_no_ext),
            utils.to_valid_var_name(morphology_filename_no_ext))

    def get_hoc(self):
        return self._hoc

    def get_section_list(self):
        # We use `wholetree()` instead of `self._hoc.all` in order to get the cell's section list,
        # because `.all` reference is not guaranteed to be in hoc template.
        return self._hoc.soma[0].wholetree()

    def get_synapse_hoc_list(self):
        return self._synapse_hoc_list

    def get_netcon_hoc_list(self):
        return self._netcon_hoc_list

    def instantiate(self):
        if not hasattr(h, self.template_name):
            template_text = hoc_utils.create_hoc_template(
                self.template_name,
                self._biophys_filepath,
                self._morphology_filepath)
            hoc_utils.execute_hoc_template(template_text)

        template_classname = getattr(h, self.template_name)
        # because we passed the full morphology filepath for generating `template_text`,
        # we don't need to specify it for `template_classname()`.
        morphology_dirpath = ''
        self._hoc = template_classname(morphology_dirpath)

    def attach_synapses(self, synapse_list):
        cell_section_list = self.get_section_list()
        for synapse in synapse_list:
            edge = synapse.sonata_edge
            synapse_classname = edge['model_template']
            synapse_weight = edge['syn_weight']
            section_x = edge['sec_x']
            section_id = edge['sec_id']
            delay = edge['delay']

            synapse_class = getattr(h, synapse_classname)
            section = cell_section_list[section_id]
            synapse_hoc = synapse_class(section(section_x))

            for k, v in synapse.dynamics_params.items():
                setattr(synapse_hoc, k, v)
            self._synapse_hoc_list.append(synapse_hoc)

            source_cell_hoc = synapse.get_source_cell_hoc()
            if 'efferent_section_id' in edge:
                # find this section on source_cell
                pass
            netcon_hoc = h.NetCon(source_cell_hoc, synapse_hoc)
            netcon_hoc.delay = delay
            netcon_hoc.weight[0] = synapse_weight
            self._netcon_hoc_list.append(netcon_hoc)


class VirtualCell(HocCell):
    def __init__(self, input_filepath, node_id):
        self._hoc = None
        with h5py.File(input_filepath, 'r') as f:
            gids = f['/spikes/gids']
            timestamps = f['/spikes/timestamps']
            time_units = timestamps.attrs['units']
            if time_units and time_units != 'ms':
                raise ValueError(
                    'Invalid time units for virtual cells in {}'.format(input_filepath))
            idx = gids[:] == node_id
            self._timestamp_list = timestamps[idx]

    def get_hoc(self):
        return self._hoc

    def instantiate(self):
        time_vector_hoc = h.Vector(self._timestamp_list)
        self._hoc = h.VecStim()
        self._hoc.play(time_vector_hoc)
