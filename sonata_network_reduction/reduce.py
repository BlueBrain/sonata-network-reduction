import shutil

from node_population import NodePopulation
from sonata_network_reduction.sonata_api import SonataApi


def reduce_network(sonata_api: SonataApi, out_circuit_dirpath):
    shutil.rmtree(out_circuit_dirpath, ignore_errors=True)
    shutil.copytree(sonata_api.get_config_dirpath(), out_circuit_dirpath)

    node_populations = [NodePopulation(population, sonata_api)
                        for population in sonata_api.circuit.nodes.values()]
    node_populations = [population for population in node_populations
                        if not population.is_virtual()]
    for node_population in node_populations:
        node_population.reduce(out_circuit_dirpath)


if __name__ == '__main__':
    api = SonataApi(
        '/home/sanin/workspace/sonata-network-reduction/tests/data/9cells/circuit_config.json',
        '/home/sanin/workspace/sonata-network-reduction/tests/data/9cells/simulation_config.json',
    )
    # from sonata_network_reduction.nrn_cell import BiophysCell
    #
    # population_name = 'cortex'
    # population = NodePopulation(api.circuit.nodes[population_name], api)
    # biophys_cell = BiophysCell(0, population)
    # biophys_cell.instantiate()
    # biophys_cell.reduce(0)
    # biophys_cell.write_biophysics('test_biophysics.hoc')

    reduce_network(
        api,
        '/home/sanin/workspace/sonata-network-reduction/tests/reduced_output',
    )
