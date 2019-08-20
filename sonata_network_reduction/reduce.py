import neuron_reduce
from sonata_network_reduction.hoc_cell import BiophysCell


def reduce_biophys_cell(biophys_cell, *args, **kwargs):
    reduced_hoc, reduced_synapse_hoc_list, reduced_netcon_hoc_list = neuron_reduce.subtree_reductor(
        biophys_cell.get_hoc(),
        biophys_cell.get_synapse_hoc_list(),
        biophys_cell.get_netcon_hoc_list(),
        *args,
        *kwargs,
    )
    reduced_biophys_cell = BiophysCell.from_hoc(
        reduced_hoc, reduced_synapse_hoc_list, reduced_netcon_hoc_list)
    return reduced_biophys_cell
