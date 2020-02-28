"""Cli module"""
from pathlib import Path
import click

from sonata_network_reduction.network_reduction import reduce_network
from sonata_network_reduction.node_reduction import _reduce_node_same_process


@click.group()
def cli():
    '''The CLI entry point'''


@cli.command(
    short_help='''Applies neuron reduction algorithm to a sonata network. The reduced network
    is stored in `reduced_network_dir`.''',
)
@click.argument('circuit_config_file', type=click.Path(exists=True, dir_okay=False))
@click.argument('reduced_network_dir', type=click.Path(file_okay=False))
@click.option('--reduction_frequency', required=True, default=0, show_default=True, type=float)
@click.option('--model_filename', type=str, default='model.hoc')
@click.option('--total_segments_manual', type=float, default=-1)
@click.option('--mapping_type', type=str, default='impedance')
def network(circuit_config_file: str, reduced_network_dir: str, **reduced_kwargs):
    """Cli interface to network reduction.

    Args:

        circuit_config_file: path to the sonata circuit config file
        reduced_network_dir: path to the dir that would store the reduced sonata network
    """
    reduce_network(Path(circuit_config_file), Path(reduced_network_dir), **reduced_kwargs)


@cli.command(
    short_help='''Applies neuron reduction algorithm to a node of sonata network. The result is
    stored to `reduced_dir`.''',
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True, )
)
@click.argument('node_id', type=click.INT)
@click.argument('reduced_dir', type=click.Path(file_okay=False))
@click.argument('node_population_name', type=click.STRING)
@click.argument('circuit_config_file', type=click.Path(exists=True, dir_okay=False))
@click.option('--reduction_frequency', required=True, default=0, show_default=True, type=float)
@click.option('--model_filename', type=str, default='model.hoc')
@click.option('--total_segments_manual', type=float, default=-1)
@click.option('--mapping_type', type=str, default='impedance')
def node(node_id: int,
         reduced_dir: str,
         node_population_name: str,
         circuit_config_file: str,
         **reduced_kwargs):
    """Cli interface to node reduction.

    Args:

        node_id: node id
        reduced_dir: path to the dir that would store the reduced node files
        node_population_name: node population name
        circuit_config_file: path to the sonata circuit config file
    """
    _reduce_node_same_process(
        node_id, Path(reduced_dir), node_population_name, Path(circuit_config_file),
        **reduced_kwargs)
