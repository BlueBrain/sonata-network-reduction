"""Module that is responsible for edges reduction"""
from pathlib import Path
from typing import List

from bluepysnap.edges import DYNAMICS_PREFIX
from neuron import h  # pylint: disable=E0611

AFFERENT_SEC_POS = 'afferent_section_pos'
AFFERENT_SEC_ID = 'afferent_section_id'


class IncomingEdgesReduction:
    """Wrapper around incoming edges for reduction"""

    def __init__(self, target_node, edges):
        """
        Args:
            target_node (BiophysNodeReduction):
            edges (pandas.DataFrame):
        """
        self._target_node = target_node

        self.synapses = []
        self.netcons = []
        self.edges = edges

    def instantiate(self):  # pylint: disable=too-many-locals
        """Instantiates itself in NEURON"""
        dynamics_cols_idx = self.edges.columns.str.startswith(DYNAMICS_PREFIX)
        for i in range(len(self.edges.index)):
            edge = self.edges.iloc[i]
            synapse_classname = getattr(edge, 'model_template')
            synapse_weight = getattr(edge, 'syn_weight')
            section_x = getattr(edge, AFFERENT_SEC_POS)
            section_id = getattr(edge, AFFERENT_SEC_ID)
            delay = getattr(edge, 'delay')

            synapse_class = getattr(h, synapse_classname)
            section = self._target_node.get_section_list()[section_id]
            synapse = synapse_class(section(section_x))
            edge_dynamics = edge.loc[dynamics_cols_idx]
            for k, v in edge_dynamics.items():
                setattr(synapse, k.replace(DYNAMICS_PREFIX, ''), v)
            self.synapses.append(synapse)

            netcon = h.NetCon(None, synapse)
            netcon.delay = delay
            netcon.weight[0] = synapse_weight
            self.netcons.append(netcon)

    def reduce(self, reduced_synapse_list: List, reduced_netcon_list: List):
        """Updates edges after reduction.

        Args:
            reduced_synapse_list (List[h.Synapse]): list of synapses after reduction
            reduced_netcon_list (List[h.NetCon]): list of netcons after reduction
        """
        cols = self.edges.columns
        for reduced_netcon_idx, reduced_netcon in enumerate(reduced_netcon_list):
            postseg = reduced_netcon.postseg()
            pos = postseg.x
            sec = postseg.sec
            sec_id = self._target_node.get_section_list().index(sec)
            netcon = self.netcons[reduced_netcon_idx]
            if netcon != reduced_netcon:
                raise RuntimeError('Reduce Algorithm changed. Please revise `reduce` method.')
            self.edges.iloc[reduced_netcon_idx, cols.get_loc(AFFERENT_SEC_POS)] = pos
            self.edges.iloc[reduced_netcon_idx, cols.get_loc(AFFERENT_SEC_ID)] = sec_id
        self.synapses = reduced_synapse_list
        self.netcons = reduced_netcon_list

    def write(self, output_dirpath: Path):
        """Writes edges as a set of '.json'.

        Each '.json' file contains all edges from the same edge population.

        Args:
            output_dirpath: path to a dir where to save '.json' files
        """
        for population_name, edges in self.edges.groupby(level='population'):
            edges.reset_index(level='population', drop=True, inplace=True)
            filepath = output_dirpath.joinpath(output_dirpath, population_name + '.json')
            edges.to_json(filepath)

    def __len__(self):
        return len(self.netcons)
