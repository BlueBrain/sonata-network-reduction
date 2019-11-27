"""Module that is responsible for single node reduction."""
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from aibs_circuit_converter import convert_to_hoc
from bglibpy import Cell, RNGSettings
from bluepyopt.ephys import create_hoc, models
from bluepyopt.ephys.morphologies import NrnFileMorphology
from bluepysnap import Circuit
import pandas as pd
import neuron_reduce
import pkg_resources
import neuron
from neuron import h

from sonata_network_reduction.edge_reduction import instantiate_edges_bglibpy, get_edges, \
    update_reduced_edges, EDGES_INDEX_POPULATION, EDGES_INDEX_AFFERENT
from sonata_network_reduction import utils
from sonata_network_reduction.biophysics import get_mechanisms_and_params
from sonata_network_reduction.morphology import CurrentNeuronMorphology


def _save_biophysics(
        biophys_filepath: Path, morphology: CurrentNeuronMorphology, morphology_name: str):
    if biophys_filepath.is_file():
        return
    mechanisms, parameters = get_mechanisms_and_params(morphology.get_section_list())
    template_filepath = pkg_resources.resource_filename(
        __name__, 'templates/reduced_cell_template.jinja2')
    biophysics = create_hoc.create_hoc(
        mechs=mechanisms,
        parameters=parameters,
        morphology=morphology_name,
        replace_axon='',
        template_name=utils.to_valid_nrn_name(biophys_filepath.stem),
        template_filename=template_filepath,
        template_dir='',
    )

    with biophys_filepath.open('w') as f:
        f.write(biophysics)


def _update_reduced_node(node_id: int, node: pd.Series):
    node.at['morphology'] += '_{}_reduced'.format(node_id)
    node.at['model_template'] += '_{}_reduced'.format(node_id)


def _write_result_dir(node: pd.Series, edges: pd.DataFrame, node_id: int):
    def _create_tmp_path(name: str):
        tmp_file = NamedTemporaryFile(delete=False)
        tmp_path = Path(tmp_file.name)
        parent_path = tmp_path.parent.joinpath('reduction', str(node_id))
        parent_path.mkdir(parents=True, exist_ok=True)
        tmp_path = parent_path.joinpath(name)
        os.rename(tmp_file.name, tmp_path)
        return tmp_path

    node_path = _create_tmp_path(str(node_id) + '.json')
    node.to_json(node_path)
    edges_paths = []
    for grp_index, grp_edges in edges.groupby(
            level=[EDGES_INDEX_POPULATION, EDGES_INDEX_AFFERENT]):
        grp_edges.reset_index(
            level=[EDGES_INDEX_POPULATION, EDGES_INDEX_AFFERENT], drop=True, inplace=True)
        population_name = grp_index[0]
        edges_path = _create_tmp_path(population_name + '.json')
        grp_edges.to_json(edges_path)
        edges_paths.append(edges_path)
    return node_path, edges_paths


def _instantiate_cell_bglibpy(node_id: int, node: pd.Series, sonata_circuit: Circuit):
    biophys_filepath = _get_biophys_filepath(node, sonata_circuit)
    morphology_filepath = _get_morphology_filepath(node, sonata_circuit)
    return Cell(
        str(biophys_filepath),
        morphology_filepath.name,
        node_id,
        template_format='v6',
        morph_dir=str(morphology_filepath.parent),
        extra_values={'holding_current': None, 'threshold_current': None},
        rng_settings=RNGSettings(),
    )


def _instantiate_cell_sonata(node_id: int, node: pd.Series, sonata_circuit: Circuit):
    """Deprecated for now. Instantiates node in NEURON with `ephys` module."""

    class _HocCellModel(models.HocCellModel):
        """ For neurodamus templates. For an example see 'cell_template_neurodamus.jinja2'
        from BluePyMM."""

        def __init__(self, name, morphology_path, hoc_path=None, hoc_string=None, gid=0):
            super().__init__(name, morphology_path, hoc_path, hoc_string)
            self.gid = gid

        def instantiate(self, sim=None):
            sim.neuron.h.load_file('stdrun.hoc')
            template_name = self.load_hoc_template(sim, self.hoc_string)
            morph_path = self.morphology.morphology_path
            self.cell = getattr(sim.neuron.h, template_name)(
                self.gid, str(morph_path.parent), morph_path.name)
            self.icell = self.cell.CellRef

    biophys_filepath = _get_biophys_filepath(node, sonata_circuit)
    morphology_filepath = _get_morphology_filepath(node, sonata_circuit)
    template_name = utils.to_valid_nrn_name(biophys_filepath.stem)
    if biophys_filepath.suffix == '.nml':
        biophysics = convert_to_hoc.load_neuroml(str(biophys_filepath))
        mechanisms = convert_to_hoc.define_mechanisms(biophysics)
        parameters = convert_to_hoc.define_parameters(biophysics)
        ephys_cell = models.CellModel(
            template_name,
            NrnFileMorphology(str(morphology_filepath)),
            mechanisms,
            parameters,
            node_id
        )
    elif biophys_filepath.suffix == '.hoc':
        ephys_cell = _HocCellModel(
            template_name,
            str(morphology_filepath),
            str(biophys_filepath),
            gid=node_id
        )
    else:
        raise ValueError('Unsupported biophysics file {}'.format(biophys_filepath))
    ephys_cell.instantiate(neuron)
    return ephys_cell


def _get_biophys_filepath(node, sonata_circuit):
    extension, name = node['model_template'].split(':')
    return Path(
        sonata_circuit.config['components']['biophysical_neuron_models_dir'],
        name + '.' + extension
    )


def _get_morphology_filepath(node, sonata_circuit):
    return Path(
        sonata_circuit.config['components']['morphologies_dir'],
        node['morphology'] + '.swc'
    )


def reduce_node(node_id: int, sonata_circuit: Circuit, node_population_name: str, **reduce_kwargs):
    """Reduces single node.

    Reduced morphology and biophysics are written inplace in corresponding sonata circuit.
    Reduced node and edges properties are written to temporary files.

    Args:
        node_id: node id
        sonata_circuit: sonata circuit
        node_population_name: node population name
        **reduce_kwargs: arguments to pass to the underlying call of
            ``neuron_reduce.subtree_reductor`` like ``reduction_frequency``.

    Returns:
        Tuple of 1. filepath to temporary .json file with new node properties,
        2. list of filepaths to temporary .json files with new edge properties.
    """
    # pylint: disable=too-many-locals
    node = sonata_circuit.nodes[node_population_name].get(node_id)
    bglibpy_cell = _instantiate_cell_bglibpy(node_id, node, sonata_circuit)
    edges = get_edges(sonata_circuit, node_population_name, node_id)
    synapses, netcons_map = instantiate_edges_bglibpy(edges, bglibpy_cell)
    _, _, reduced_netcons = \
        neuron_reduce.subtree_reductor(
            bglibpy_cell.cell,
            synapses,
            list(netcons_map.values()),
            **reduce_kwargs, )
    # 3D is lost after reduction, we need to restore it with h.define_shape()
    h.define_shape()
    morphology = CurrentNeuronMorphology()
    update_reduced_edges(reduced_netcons, netcons_map, edges, morphology)

    _update_reduced_node(node_id, node)
    morphology_filepath = _get_morphology_filepath(node, sonata_circuit)
    biophys_filepath = _get_biophys_filepath(node, sonata_circuit)
    morphology.save(str(morphology_filepath))
    _save_biophysics(biophys_filepath, morphology, morphology_filepath.name)

    return _write_result_dir(node, edges, node_id)
