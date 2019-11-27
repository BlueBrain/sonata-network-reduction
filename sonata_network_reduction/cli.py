"""Cli module"""
import click

from sonata_network_reduction import reduce_network


@click.command(short_help='Applies neuron reduction algorithm to a sonata network.'
                          'The result is a new sonata network.')
@click.argument('sonata_circuit_config', type=click.Path(exists=True, dir_okay=False))
@click.argument('reduced_sonata_dir', type=click.Path(file_okay=False))
def cli(sonata_circuit_config: str, reduced_sonata_dir: str):
    """Cli interface to the project.

    Args:
        sonata_circuit_config: path to the sonata circuit config file
        reduced_sonata_dir: path to the dir that would store the reduced sonata network
    """
    reduce_network(sonata_circuit_config, reduced_sonata_dir)
