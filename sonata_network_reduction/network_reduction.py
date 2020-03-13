"""Main API"""
import shutil
import traceback
import warnings
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np

from bluepysnap.circuit import Circuit
from bluepysnap.nodes import NodePopulation
from joblib import Parallel, delayed, parallel_backend

from sonata_network_reduction.exceptions import SonataReductionError
from sonata_network_reduction.node_reduction import reduce_node
from sonata_network_reduction.write_reduced import write_reduced_to_circuit


def _get_biophys_node_ids(population: NodePopulation) -> np.array:
    """Gets ids of biophysics nodes.

    We use array instead of generator because the first call to ``population.ids`` will create
    a pandas DataFrame for all nodes of population => no point in iterating over ``population.ids``
    Args:
        population: node population

    Returns:
        numpy array: node ids that have biophysics
    """
    biophys_props = {'morphology', 'model_type'}
    if not biophys_props <= population.property_names:
        return np.empty(shape=0)
    df = population.get(properties=biophys_props)
    return (df['model_type'] == 'biophysical').index


def _reduce_node_proxy(
        node_id: int,
        reduced_dir: Path,
        node_population_name: str,
        circuit_config_file: Path,
        **reduce_kwargs):
    """Proxy for `reduce_node` function that catches all its Exceptions and wraps them into
    SonataReductionError."""
    try:
        reduce_node(node_id, node_population_name, circuit_config_file, reduced_dir / str(node_id),
                    **reduce_kwargs)
    except RuntimeError as e:
        raise SonataReductionError('reduction of node {} failed'.format(node_id)) from e


def reduce_population(
        population: NodePopulation,
        original_circuit_config_file: Path,
        reduced_circuit_config_file: Path,
        **reduce_kwargs):
    """ Reduces node population.

    Args:
        population: node population
        original_circuit_config_file: original sonata circuit config filepath
        reduced_circuit_config_file: reduced sonata circuit config filepath
        **reduce_kwargs: arguments to pass to the underlying call of
            ``neuron_reduce.subtree_reductor`` like ``reduction_frequency``.
    """
    ids = _get_biophys_node_ids(population)
    if len(ids) == 0:
        warnings.warn('No biophys nodes in "{}" population. Is it virtual?'.format(population.name))
        return
    with parallel_backend('threading'), TemporaryDirectory() as tmp_dirpath:
        tmp_dirpath = Path(tmp_dirpath)
        try:
            Parallel()(delayed(partial(
                _reduce_node_proxy,
                node_population_name=population.name,
                circuit_config_file=original_circuit_config_file,
                reduced_dir=tmp_dirpath,
                **reduce_kwargs))(id) for id in ids)
        except SonataReductionError:
            e_text = traceback.format_exc()
            warnings.warn(e_text)
        write_reduced_to_circuit(tmp_dirpath, reduced_circuit_config_file, population.name)


def reduce_network(circuit_config_file: Path, reduced_dir: Path, **reduce_kwargs):
    """ Reduces the network represented by ``circuit_config_filepath`` param.

    Assumed that the circuit is represented by the parent directory of ``circuit_config_filepath``.
    The reduced network is saved to ``out_circuit_dir``.

    Args:
        circuit_config_file: path to Sonata circuit config file
        reduced_dir: path to a directory where to save the reduced network.
        **reduce_kwargs: arguments to pass to the underlying call of
            ``neuron_reduce.subtree_reductor`` like ``reduction_frequency``.
    """
    if reduced_dir.exists():
        raise ValueError('{} must not exist. Please delete it.'.format(reduced_dir))
    original_circuit = Circuit(str(circuit_config_file))
    # don't copy morphologies and biophysics dir as they can be quite huge
    ignore_dirs = (
        Path(original_circuit.config['components']['biophysical_neuron_models_dir']).name,
        Path(original_circuit.config['components']['morphologies_dir']).name)
    shutil.copytree(str(circuit_config_file.parent), str(reduced_dir),
                    ignore=shutil.ignore_patterns(*ignore_dirs))

    reduced_circuit_config_file = reduced_dir / circuit_config_file.name
    for population in original_circuit.nodes.values():
        reduce_population(population, circuit_config_file, reduced_circuit_config_file,
                          **reduce_kwargs)
