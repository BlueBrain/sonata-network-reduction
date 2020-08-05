"""Module that is responsible for single node reduction."""
from pathlib import Path
from collections import OrderedDict
from typing import List, Tuple

import pandas as pd
from bglibpy import Cell, Synapse
from bluepysnap import Circuit
from neuron import h

from sonata_network_reduction.morphology import ReducedNeuronMorphology

EDGES_INDEX_POPULATION = 'population'
EDGES_INDEX_AFFERENT = 'afferent'


def get_edges(sonata_circuit: Circuit, node_population_name: str, node_id: int) -> pd.DataFrame:
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


def instantiate_edges(edges: pd.DataFrame, bglibpy_cell: Cell) -> Tuple[List, OrderedDict]:
    """Instantiates edges in NEURON.

    Args:
        edges: edges
        bglibpy_cell: edges cell as bglibpy.Cell

    Returns:
        Tuple of the synapses list and the netcons dict corresponding to edges.
    """
    synapses = []
    netcons_map = OrderedDict()
    for edge in edges.itertuples():
        is_afferent = edge.Index[1]
        syn_description = [
            0,  # 0 mock of `pre_gid`
            edge.delay,  # 1
            edge.afferent_section_id if is_afferent else edge.efferent_section_id,  # 2
            edge.afferent_segment_id if is_afferent else edge.efferent_segment_id,  # 3
            edge.afferent_segment_offset if is_afferent else edge.efferent_segment_offset,  # 4
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
            None,  # 18 u_hill_coefficient
            None,  # 19 conductance_ratio
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


def _get_segment_id_and_offset(hsection: h.Section, x: float) -> Tuple[int, float]:
    """Calculates section location's corresponding segment id and offset

    Args:
        hsection: NEURON section
        x: location on ``hsection`` as a fraction of its pathlength. A number in the [0, 1]
        interval.

    Returns:
        Segment ID and offset
    """
    assert 0 <= x <= 1, '`x` must be in the interval [0, 1]'
    section_len = x * hsection.L
    id_ = 0
    offset = 0
    for i in range(hsection.n3d()):
        if hsection.arc3d(i) >= section_len:
            id_ = max(i - 1, id_)
            offset = section_len - hsection.arc3d(id_)
            break
    return id_, offset


def update_reduced_edges(reduced_netcons: List, netcons_map: OrderedDict, edges: pd.DataFrame,
                         morphology: ReducedNeuronMorphology):
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
        segment_id, segment_offset = _get_segment_id_and_offset(sec, seg.x)
        # +1 because Morphio section indexes start from -1 but edges start from 0
        sec_id = morphology.get_section_id(sec) + 1
        edges.at[edge_index,
                 'afferent_section_id' if is_afferent else 'efferent_section_id'] = sec_id
        edges.at[edge_index,
                 'afferent_section_pos' if is_afferent else 'efferent_section_pos'] = seg.x
        edges.at[edge_index,
                 'afferent_segment_id' if is_afferent else 'efferent_segment_id'] = segment_id
        column = 'afferent_segment_offset' if is_afferent else 'efferent_segment_offset'
        edges.at[edge_index, column] = segment_offset


def save_edges(edges_path: Path, edges: pd.DataFrame):
    """Saves edges to `<edge_population_name>.json` files in `edges_path`.

    Args:
        edges_path: dir where to save
        edges: edges to save
    """
    edges_path.mkdir(exist_ok=True)
    saved_columns = ['afferent_section_id', 'afferent_section_pos',
                     'afferent_segment_id', 'afferent_segment_offset',
                     'efferent_section_id', 'efferent_section_pos',
                     'efferent_segment_id', 'efferent_segment_offset']
    edges = edges.loc[:, edges.columns.isin(saved_columns)]
    for (edges_pop_name, _), edges_pop_df in edges.groupby(
            level=[EDGES_INDEX_POPULATION, EDGES_INDEX_AFFERENT]):
        edges_pop_df = edges_pop_df. \
            reset_index(level=[EDGES_INDEX_POPULATION, EDGES_INDEX_AFFERENT], drop=True). \
            dropna(axis=1, how='all')
        edges_pop_df.to_json(edges_path / (edges_pop_name + '.json'))
