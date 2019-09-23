"""Cli module"""
import click

from sonata_network_reduction import SonataApi, reduce_network


@click.command(short_help='Applies neuron reduction algorithm to a sonata network.'
                          'The result is a new sonata network.')
@click.argument('sonata_circuit_config', type=click.Path(exists=True, dir_okay=False))
@click.argument('sonata_simulation_config', type=click.Path(exists=True, dir_okay=False))
@click.argument('reduced_sonata_dir', type=click.Path(file_okay=False))
def cli(sonata_circuit_config, sonata_simulation_config, reduced_sonata_dir):
    """Cli interface to the project.

    Args:
        sonata_circuit_config: path to the sonata circuit config file
        sonata_simulation_config: path to the sonata simulation config file
        reduced_sonata_dir: path to the dir that would store the reduced sonata network
    """
    sonata_api = SonataApi(sonata_circuit_config, sonata_simulation_config)
    reduce_network(sonata_api, reduced_sonata_dir)
