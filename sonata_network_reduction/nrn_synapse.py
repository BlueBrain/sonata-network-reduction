import os

from bluepysnap.edges import DYNAMICS_PREFIX
from neuron import h

AFFERENT_SEC_POS = 'afferent_section_pos'
AFFERENT_SEC_ID = 'afferent_section_id'


class NrnIncomingSynapses:
    def __init__(self, target_cell, edges):
        self._target_cell = target_cell

        self.synapses = []
        self.netcons = []
        self.edges = edges

    def instantiate(self):
        for i in range(len(self.edges.index)):
            edge = self.edges.iloc[i]
            synapse_classname = getattr(edge, 'model_template')
            synapse_weight = getattr(edge, 'syn_weight')
            section_x = getattr(edge, AFFERENT_SEC_POS)
            section_id = getattr(edge, AFFERENT_SEC_ID)
            delay = getattr(edge, 'delay')

            synapse_class = getattr(h, synapse_classname)
            section = self._target_cell.get_section_list()[section_id]
            synapse = synapse_class(section(section_x))
            edge_dynamics = edge.loc[edge.index.str.startswith(DYNAMICS_PREFIX)]
            for k, v in edge_dynamics.items():
                setattr(synapse, k.replace(DYNAMICS_PREFIX, ''), v)
            self.synapses.append(synapse)

            netcon = h.NetCon(None, synapse)
            netcon.delay = delay
            netcon.weight[0] = synapse_weight
            self.netcons.append(netcon)

    def reduce(self, reduced_synapse_list, reduced_netcon_list):
        for reduced_netcon_idx, reduced_netcon in enumerate(reduced_netcon_list):
            postseg = reduced_netcon.postseg()
            pos = postseg.x
            sec = postseg.sec
            sec_id = self._target_cell.get_section_list().index(sec)
            netcon = self.netcons[reduced_netcon_idx]
            if netcon != reduced_netcon:
                raise RuntimeError('Reduce Algorithm changed. Please revise `reduce` method.')
            cols = self.edges.columns
            self.edges.iloc[reduced_netcon_idx, cols.get_loc(AFFERENT_SEC_POS)] = pos
            self.edges.iloc[reduced_netcon_idx, cols.get_loc(AFFERENT_SEC_ID)] = sec_id
        self.synapses = reduced_synapse_list
        self.netcons = reduced_netcon_list

    def write(self, output_dirpath):
        for population_name, edges in self.edges.groupby(level='population'):
            edges.reset_index(level='population', drop=True, inplace=True)
            filepath = os.path.join(output_dirpath, population_name + '.json')
            edges.to_json(filepath)

    def __len__(self):
        return len(self.netcons)
