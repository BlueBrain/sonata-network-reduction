"""Module that is responsible for single node reduction."""
from collections import OrderedDict
from typing import List

import pandas as pd
from bglibpy import Cell, Synapse
from bluepysnap import Circuit
from neuron import h

from sonata_network_reduction.morphology import CurrentNeuronMorphology

EDGES_INDEX_POPULATION = 'population'
EDGES_INDEX_AFFERENT = 'afferent'


def get_edges(sonata_circuit: Circuit, node_population_name: str, node_id: int):
    """Gets all edges for a given node

    Args:
        sonata_circuit: sonata circuit
        node_population_name: node population name
        node_id: node id

    Returns:
        pandas DataFrame of edges where columns are edge properties and index is
        (edge population name, is edge afferent or not, edge idx).
    """
    edges_list = []
    for name, population in sonata_circuit.edges.items():
        properties = list(population.property_names)
        if population.target.name == node_population_name:
            edges_list.append((name, True, population.afferent_edges(node_id, properties)))
        # For now we ignore efferent connections
        # if population.source.name == node_population_name:
        #     edges_list.append((name, False, population.efferent_edges(node_id, properties)))
    if len(edges_list) == 0:
        return pd.DataFrame()
    return pd.concat(
        [item[2] for item in edges_list],
        keys=[(item[0], item[1]) for item in edges_list],
        names=[EDGES_INDEX_POPULATION, EDGES_INDEX_AFFERENT, 'idx'])


def instantiate_edges_sonata(edges: pd.DataFrame):
    """Deprecated for now. Instantiates edges in NEURON.

    Args:
        edges: edges Dataframe

    Returns:
        list of synapses corresponding to edges.
    """
    # pylint: disable=too-many-locals, import-outside-toplevel
    from bluepysnap.edges import DYNAMICS_PREFIX
    morphology = CurrentNeuronMorphology()
    dynamics_cols_idx = edges.columns.str.startswith(DYNAMICS_PREFIX)
    synapses = []
    for i in range(len(edges.index)):
        edge = edges.iloc[i]
        synapse_classname = edge['model_template']
        section_x = edge['afferent_section_pos']
        section_id = edge['afferent_section_id']

        synapse_class = getattr(h, synapse_classname)
        section = morphology.get_section(section_id)
        synapse = synapse_class(section(section_x))
        edge_dynamics = edge.loc[dynamics_cols_idx]
        for k, v in edge_dynamics.items():
            setattr(synapse, k.replace(DYNAMICS_PREFIX, ''), v)
        synapses.append(synapse)
    return synapses


def instantiate_edges_bglibpy(edges: pd.DataFrame, bglibpy_cell: Cell):
    """Instantiates edges in NEURON.

    Args:
        edges: edges
        bglibpy_cell: edges cell in BGLibPy

    Returns:
        list of synapses and dict of netcons corresponding to edges.
    """
    synapses = []
    netcons_map = OrderedDict()
    for edge in edges.itertuples():
        is_afferent = edge.Index[1]
        syn_description = [
            0,  # 0 mock of `pre_gid`
            edge.delay,  # 1
            edge.morpho_section_id_post if is_afferent else edge.morpho_section_id_pre,  # 2
            edge.morpho_segment_id_post if is_afferent else edge.morpho_segment_id_pre,  # 3
            edge.morpho_offset_segment_post if is_afferent else edge.morpho_offset_segment_pre,  # 4
            None,  # 5
            None,  # 6
            None,  # 7
            None,  # 8 weight
            edge.u_syn,  # 9
            edge.depression_time,  # 10
            edge.facilitation_time,  # 11
            edge.decay_time,  # 12
            edge.syn_type_id,  # 13
            None,  # 14
            None,  # 15
            None,  # 16
            edge.n_rrp_vesicles,  # 17
        ]
        location = bglibpy_cell.synlocation_to_segx(
            syn_description[2], syn_description[3], syn_description[4])
        synapse = Synapse(
            bglibpy_cell,
            location,
            ('', 0),  # mock of `syn_id`
            syn_description,
            [],  # mock of `connection_parameters`
            None,  # mock of `base_seed`
        )
        synapses.append(synapse.hsynapse)
        if is_afferent:
            netcons_map[edge.Index] = h.NetCon(None, synapse.hsynapse)
        else:
            netcons_map[edge.Index] = h.NetCon(synapse.hsynapse, None)
    return synapses, netcons_map


def update_reduced_edges(reduced_netcons: List, netcons_map: OrderedDict, edges: pd.DataFrame,
                         morphology: CurrentNeuronMorphology):
    """Update edges Dataframe inplace with new reduced properties.

    Args:
        reduced_netcons: reduced cell netcons
        netcons_map: original map between netcons and edges
        edges: edges
        morphology: reduced cell morphology
    """
    for (edge_index, netcon), reduced_netcon in zip(iter(netcons_map.items()), reduced_netcons):
        if netcon != reduced_netcon:
            raise RuntimeError('Reduce Algorithm changed. Please revise `reduce` method.')
        is_afferent = edge_index[1]
        if is_afferent:
            syn = reduced_netcon.syn()
        else:
            syn = reduced_netcon.pre()
        seg = syn.get_segment()
        sec = seg.sec
        segments = list(sec)
        ipt = segments.index(seg) + 1
        # half_seg_len = h.distance(sec(0), sec(1. / len(segments) * .5))
        sec_id = morphology.get_section_id(sec)
        edges.at[edge_index,
                 'morpho_section_id_post' if is_afferent else 'morpho_section_id_pre'] = sec_id
        edges.at[edge_index,
                 'morpho_segment_id_post' if is_afferent else 'morpho_segment_id_pre'] = ipt
        edges.at[edge_index,
                 'morpho_offset_segment_post' if is_afferent else 'morpho_offset_segment_pre'] = 0
