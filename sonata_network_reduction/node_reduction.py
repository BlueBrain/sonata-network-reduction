"""Module that is responsible for single node reduction."""
import itertools
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Tuple, List, Dict

from bglibpy import Cell, RNGSettings
from bluepyopt.ephys import create_hoc
from bluepyopt.ephys.locations import NrnSeclistLocation
from bluepyopt.ephys.mechanisms import NrnMODMechanism
from bluepyopt.ephys.parameters import NrnSectionParameter
from bluepysnap import Circuit
import pandas as pd
import neuron_reduce
import pkg_resources
from neuron import h

from sonata_network_reduction.edge_reduction import instantiate_edges, get_edges, \
    update_reduced_edges, EDGES_INDEX_POPULATION, EDGES_INDEX_AFFERENT
from sonata_network_reduction import utils
from sonata_network_reduction.biophysics import get_seclist_nsegs, get_mechs_params
from sonata_network_reduction.morphology import copy_soma, ReducedNeuronMorphology
from sonata_network_reduction.write_reduced import write_reduced_to_circuit


def _current_NRN_soma():
    """Gets soma of currently instantiated neuron in NEURON.

    Returns:
        Soma. Throws an error if there are multiple neurons.
    """
    cells = h.SectionList()
    cells.allroots()
    cells = list(cells)
    assert len(cells) == 1
    return cells[0]


def _to_bluepyopt_format(
        mech_names: Dict[str, List],
        uniform_params: Dict[str, Dict[str, float]]) \
        -> Tuple[List[NrnMODMechanism], List[NrnSectionParameter]]:
    mechs = []
    params = []
    for seclist_name in mech_names.keys():
        loc = NrnSeclistLocation(seclist_name, seclist_name)
        mechs += [NrnMODMechanism(mech_name, suffix=mech_name, locations=[loc])
                  for mech_name in mech_names[seclist_name]]
        params += [NrnSectionParameter(
            param_name, param_value, True, param_name=param_name, locations=[loc])
            for param_name, param_value in uniform_params[seclist_name].items()]
    return mechs, params


def _save_biophysics(biophys_filepath: Path, morphology: ReducedNeuronMorphology,
                     morphology_name: str):
    """Saves biophysics of morphology to a file

    Args:
        biophys_filepath: where to save file
        morphology: to get biophysics from
        morphology_name: name of morphology to store in biophysics file
    """
    biophys_filepath.parent.mkdir(exist_ok=True)
    mech_names, uniform_params, nonuniform_params = get_mechs_params(morphology.section_lists)
    mechs, uniform_params = _to_bluepyopt_format(mech_names, uniform_params)
    nonuniform_param_names = set(itertools.chain(*nonuniform_params.values()))
    template_filepath = pkg_resources.resource_filename(
        __name__, 'templates/reduced_cell_template.jinja2')
    biophysics = create_hoc.create_hoc(
        mechs=mechs,
        parameters=uniform_params,
        morphology=morphology_name,
        replace_axon='',
        template_name=utils.to_valid_nrn_name(biophys_filepath.stem),
        template_filename=template_filepath,
        template_dir='',
        custom_jinja_params={
            'nsegs_map': get_seclist_nsegs(morphology.section_lists),
            'nonuniform_params': nonuniform_params,
            'nonuniform_param_names': nonuniform_param_names,
        },
    )

    with biophys_filepath.open('w') as f:
        f.write(biophysics)


def _save_node(node_path: Path, node: pd.Series, node_id: int):
    """Saves node to a `<node_id>.json` file in `node_path`.

    Args:
        node_path: dir where to save
        node: node to save
        node_id: node id
    """
    node_path.mkdir(exist_ok=True)
    node[['morphology', 'model_template']].to_json(node_path / '{}.json'.format(node_id))


def _save_edges(edges_path: Path, edges: pd.DataFrame):
    """Saves edges to `<edge_population_name>.json` files in `edges_path`.

    Args:
        edges_path: dir where to save
        edges: edges to save
    """
    edges_path.mkdir(exist_ok=True)
    for grp_index, grp_edges in edges.groupby(
            level=[EDGES_INDEX_POPULATION, EDGES_INDEX_AFFERENT]):
        grp_edges.reset_index(
            level=[EDGES_INDEX_POPULATION, EDGES_INDEX_AFFERENT], drop=True, inplace=True)
        population_name = grp_index[0]
        grp_edges.to_json(edges_path / (population_name + '.json'))


def _update_reduced_node(node_id: int, node: pd.Series):
    """Updates node data with reduced properties.

    Args:
        node_id: node ID
        node: pandas Series of single node data
    """
    node.at['morphology'] += '_{}'.format(node_id)
    node.at['model_template'] += '_{}'.format(node_id)


def _instantiate_cell(node_id: int, node: pd.Series, circuit: Circuit) -> Cell:
    """Instantiates bglibpy.Cell for node.

    Args:
        node_id: node ID
        node: node data
        circuit: sonata circuit

    Returns:
        instance of bglibpy.Cell
    """
    biophys_filepath = _get_biophys_filepath(node, circuit)
    morphology_filepath = _get_morphology_filepath(node, circuit)
    return Cell(
        str(biophys_filepath),
        morphology_filepath.name,
        node_id,
        template_format='v6',
        morph_dir=str(morphology_filepath.parent),
        extra_values={'holding_current': None, 'threshold_current': None},
        rng_settings=RNGSettings(),
    )


def _get_biophys_filepath(node: pd.Series, circuit: Circuit) -> Path:
    """Gets filepath to node's biophysics file

    Args:
        node: node data
        circuit: sonata circuit

    Returns:
        Filepath
    """
    extension, name = node['model_template'].split(':')
    return Path(
        circuit.config['components']['biophysical_neuron_models_dir'],
        name + '.' + extension
    )


def _get_morphology_filepath(node: pd.Series, circuit: Circuit) -> Path:
    """Gets filepath to node's morphology file

    Args:
        node: node data
        circuit: sonata circuit

    Returns:
        Filepath
    """
    morph_dir = Path(circuit.config['components']['morphologies_dir'])
    if morph_dir.joinpath('ascii').is_dir():
        return morph_dir.joinpath('ascii', node['morphology'] + '.asc')
    else:
        return morph_dir.joinpath(node['morphology'] + '.swc')


def _reduce_node_same_process(
        node_id: int,
        node_population_name: str,
        circuit_config_file: Path,
        reduced_dir: Path = None,
        **reduce_kwargs):
    """Reduces single node in the same as caller's process. Signature is identical to
    `reduce_node`"""
    # pylint: disable=too-many-locals
    circuit = Circuit(str(circuit_config_file))
    node = circuit.nodes[node_population_name].get(node_id)
    original_morphology_filepath = _get_morphology_filepath(node, circuit)
    bglibpy_cell = _instantiate_cell(node_id, node, circuit)
    edges = get_edges(circuit, node_population_name, node_id)
    synapses, netcons_map = instantiate_edges(edges, bglibpy_cell)
    _, _, reduced_netcons = \
        neuron_reduce.subtree_reductor(
            bglibpy_cell.cell,
            synapses,
            list(netcons_map.values()),
            **reduce_kwargs, )
    # 3D is lost after reduction, we need to restore it with h.define_shape()
    h.define_shape()
    morphology = ReducedNeuronMorphology(_current_NRN_soma())
    # Soma might be skewed by NEURON upon loading but reduction should not change it.
    copy_soma(morphology.morph, original_morphology_filepath)
    update_reduced_edges(reduced_netcons, netcons_map, edges, morphology)
    _update_reduced_node(node_id, node)

    inplace = reduced_dir is None
    if inplace:
        tmp_dir = TemporaryDirectory()
        reduced_dir = Path(tmp_dir.name)
    else:
        reduced_dir.mkdir(parents=True, exist_ok=True)
    reduced_morphology_filepath = reduced_dir.joinpath(
        'morphology', _get_morphology_filepath(node, circuit).name)
    biophys_filepath = reduced_dir / 'biophys' / _get_biophys_filepath(node, circuit).name
    morphology.save(reduced_morphology_filepath)
    _save_biophysics(biophys_filepath, morphology, reduced_morphology_filepath.name)
    _save_node(reduced_dir / 'node', node, node_id)
    _save_edges(reduced_dir / 'edges', edges)
    if inplace:
        utils.close_sonata_circuit(circuit)
        write_reduced_to_circuit(reduced_dir, circuit_config_file, node_population_name)


def reduce_node(
        node_id: int,
        node_population_name: str,
        circuit_config_file: Path,
        reduced_dir: Path,
        **reduce_kwargs):
    """Reduces single node.

    Reduction happens in a separate process via `subprocess.run`. If success then the content of
    ``reduced_dir`` should be:
    - `morphology` dir with reduced morphology file
    - `biophys` dir with reduced biophysics file
    - `node` dir with ``node_id``.json file of reduced node
    - `edges` dir with `edge_population`.json files of reduced edges populations

    Args:
        node_id: node id
        node_population_name: node population name
        circuit_config_file: reduced sonata circuit config filepath
        reduced_dir: dir where to save results of reduction. If None then the node will be reduced
        in-place of its circuit.
        **reduce_kwargs: arguments to pass to the underlying call of
            ``neuron_reduce.subtree_reductor`` like ``reduction_frequency``

    Returns:
        Int: exit code of the separate reduction process.
    """
    neuron_reduce_args = list(map(str, itertools.chain(*reduce_kwargs.items())))
    node_id = str(node_id)
    main_args = [node_id, node_population_name, circuit_config_file, reduced_dir]
    # call node reduction via cli.py and separate process
    cmd = ['sonata-network-reduction', 'node'] + main_args + neuron_reduce_args
    process = subprocess.run(cmd, check=True, timeout=60 * 60)
    return process.returncode
