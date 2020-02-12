"""Cli module"""
from pathlib import Path
import click

from sonata_network_reduction import reduce_network


def _format_reduction_arg(kwargs, arg_name, arg_type, arg_default=None):
    """Formats argument as required by the reduction function ``neuron_reduce.subtree_reductor``

    Formats inplace in ``kwargs``
    Args:
        kwargs: kwargs that will be passed to reduction function
        arg_name: arg name of ``kwargs``
        arg_type: expected type of ``arg_name``
        arg_default: default value of ``arg_name``
    """
    if arg_name in kwargs:
        kwargs[arg_name] = arg_type(kwargs[arg_name])
    elif arg_default is not None:
        kwargs[arg_name] = arg_default


@click.command(
    short_help='''
    Applies neuron reduction algorithm to a sonata network. The result is a new sonata network.''',
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True, )
)
@click.argument('circuit_config_file', type=click.Path(exists=True, dir_okay=False))
@click.argument('reduced_circuit_dir', type=click.Path(file_okay=False))
@click.pass_context
def cli(ctx, circuit_config_file: str, reduced_circuit_dir: str, ):
    """Cli interface to the project.

    Args:
        circuit_config_file: path to the sonata circuit config file
        reduced_circuit_dir: path to the dir that would store the reduced sonata network
        ctx: named options of https://github.com/orena1/neuron_reduce.
        Example ``--reduction_frequency 0``.
    """
    kwargs = {ctx.args[i].strip('-'): ctx.args[i + 1] for i in range(0, len(ctx.args), 2)}
    _format_reduction_arg(kwargs, 'reduction_frequency', float, 0)
    _format_reduction_arg(kwargs, 'total_segments_manual', float, -1)
    _format_reduction_arg(kwargs, 'return_seg_to_seg', bool, False)
    reduce_network(Path(circuit_config_file), Path(reduced_circuit_dir), **kwargs)
