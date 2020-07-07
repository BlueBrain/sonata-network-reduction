"""Main API"""
import shutil
import traceback
import warnings
from functools import partial
from multiprocessing import Value
from pathlib import Path
from subprocess import CalledProcessError
from tempfile import TemporaryDirectory
import numpy as np

from bluepysnap.circuit import Circuit
from bluepysnap.nodes import NodePopulation
from bluepysnap import circuit_validation
from joblib import Parallel, delayed, parallel_backend
from tqdm import tqdm

from sonata_network_reduction.exceptions import ReductionError
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
    biophys_props = {'morphology', 'model_template'}
    if not biophys_props <= population.property_names:
        return np.empty(shape=0)
    df = population.get(properties=biophys_props)
    return df.dropna().index


def _reduce_node_proxy(
        node_id: int,
        reduced_dir: Path,
        node_population_name: str,
        circuit_config_file: Path,
        failed_nodes_counter: Value,
        **reduce_kwargs):
    """Proxy for `reduce_node` function that catches all its Exceptions and emits warnings
    of them."""
    try:
        reduce_node(node_id, node_population_name, circuit_config_file, reduced_dir / str(node_id),
                    **reduce_kwargs)
    except (CalledProcessError, RuntimeError) as e:
        e_text = traceback.format_exc()
        warnings.warn('reduction of node {} failed:\n{}'.format(node_id, e_text))
        with failed_nodes_counter.get_lock():
            failed_nodes_counter.value -= 1
            if failed_nodes_counter.value == 0:
                raise ReductionError('Reached max number of failed reduced nodes. Aborting.') from e


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
    failed_nodes_counter = Value('i', 5)
    with parallel_backend('threading'), TemporaryDirectory() as tmp_dirpath:
        tmp_dirpath = Path(tmp_dirpath)
        Parallel()(delayed(partial(
            _reduce_node_proxy,
            node_population_name=population.name,
            circuit_config_file=original_circuit_config_file,
            reduced_dir=tmp_dirpath,
            failed_nodes_counter=failed_nodes_counter,
            **reduce_kwargs))(id) for id in tqdm(ids))
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
    errors = circuit_validation.validate(str(circuit_config_file), True)
    errors = [err for err in errors if err.level == circuit_validation.Error.FATAL]
    if len(errors) > 0:
        raise ReductionError(
            f'{circuit_config_file} is invalid SONATA circuit. Fix FATAL errors above.')
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
