"""holds the class SonataApi"""
from pathlib import Path

from cached_property import cached_property
import pandas as pd
from bluepysnap.circuit import Circuit
from bluepysnap.config import Config


class SonataApi:
    """Wrapper around bluepysnap functionality"""

    def __init__(self, circuit_config_filepath: str, simulation_config_filepath: str):
        """
        Args:
            circuit_config_filepath: filepath to a Sonata circuit config
            simulation_config_filepath: filepath to a Sonata simulation config
        """
        self.circuit_config = Config.parse(circuit_config_filepath)
        self.simulation_config = Config.parse(simulation_config_filepath)
        self.circuit = Circuit(circuit_config_filepath)

    def get_population_output_filepath(self, population, output_dirpath: Path) -> Path:
        # pylint: disable=protected-access
        """Gets filepath of ``population`` in ``output_dirpath``.

        Args:
            population: instance of EdgePopulation or NodePopulation
            output_dirpath: path to a directory where this Sonata directory is copied
        Returns:
            ``population`` filepath in ``output_dirpath``
        """
        return self.get_output_filepath(Path(population._h5_filepath), output_dirpath)

    def get_output_filepath(self, filepath: Path, output_dirpath: Path) -> Path:
        """Maps ``filepath`` in Sonata config directory to the same place in ``output_dirpath``.

        This method exists for copying Sonata config directory.
        Args:
            filepath: filepath in this Sonata config directory
            output_dirpath: path to a directory where this Sonata directory is copied
        Returns:
            ``filepath`` that points to ``output_dirpath``
        """
        output_filepath = filepath.relative_to(self.config_dirpath)
        return output_dirpath.joinpath(output_filepath)

    @cached_property
    def config_dirpath(self) -> Path:
        """
        Returns: Path to a directory that holds simulation config. We assume that whole Sonata
            config is in this directory
        """
        return Path(self.simulation_config['network']).parent

    def get_incoming_edges(self, node_population_name: str, node_id: int):
        """
        Args:
            node_population_name: node population name
            node_id: node id
        Returns:
            pandas DataFrame that holds edges where node_id is the edge target.
        """

        def edges_to_df(edges):
            if not edges.keys():
                return pd.DataFrame()
            else:
                return pd.concat(edges.values(), keys=edges.keys(), names=['population', 'idx'])

        incoming_edges = {}
        for name, population in self.circuit.edges.items():
            properties = list(population.property_names)
            if population.target.name == node_population_name:
                incoming_edges[name] = population.afferent_edges(node_id, properties)

        return edges_to_df(incoming_edges)

    def get_simulation_input(self, population_name: str):
        """ Returns a simulated input for the node population if there is any.

        Args:
            population_name: node population name
        Returns:
            dict of simulation input params if there is one otherwise None.
        """
        inputs = self.simulation_config.get('inputs')
        if not inputs:
            return None
        for _, params in inputs.items():
            if params['node_set'] == population_name:
                return params
        return None

    def is_virtual_node_population(self, population_name):
        """
        Returns:
            Whether the corresponding population is virtual, e.g. contains no real nodes.
        """
        return self.get_simulation_input(population_name) is not None
