"""Module that is responsible for single node reduction."""
import shutil
from pathlib import Path

import neuron_reduce
from bluepyopt.ephys import create_hoc
from bluepyopt.ephys import models
from bluepyopt.ephys.morphologies import NrnFileMorphology
from aibs_circuit_converter import convert_to_hoc
from hoc2swc import neuron2swc
import neuron

from sonata_network_reduction.biophysics import get_mechanisms_and_params
from sonata_network_reduction import utils
from sonata_network_reduction.network_reduction import NodePopulationReduction
from sonata_network_reduction.edge_reduction import IncomingEdgesReduction


class HocCellModel(models.HocCellModel):
    """
    For neurodamus templates. For an example see 'cell_template_neurodamus.jinja2' from BluePyMM.
    """

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


class BiophysNodeReduction:
    """Wrapper around node for reduction"""

    def __init__(self, node_id: int, population_reduction: NodePopulationReduction):
        self.node_id = node_id
        self.edges_reduction = IncomingEdgesReduction(
            self, population_reduction.get_incoming_edges(node_id))
        self._node = population_reduction.get_node(self.node_id)
        self._population_reduction = population_reduction
        self._ephys_model = None
        self._is_reduced = False
        self._instantiate()

    @property
    def morphology_filepath(self) -> Path:
        """
        Returns:
            absolute filepath to node's morphology file
        """
        return Path(
            self._population_reduction.get_circuit_component('morphologies_dir'),
            self._node['morphology'] + '.swc'
        )

    @property
    def biophys_filepath(self) -> Path:
        """
        Returns:
            absolute filepath to node's biophys file
        """
        biophys_dir_path = self._population_reduction.get_circuit_component(
            'biophysical_neuron_models_dir')
        if ':' in self._node['model_template']:
            biophys_type, biophys_filename = self._node['model_template'].split(':')
            if '.' not in biophys_filename:
                biophys_filename = biophys_filename + '.' + biophys_type
        else:
            biophys_filename = self._node['model_template']
        return Path(biophys_dir_path, biophys_filename)

    @property
    def template_name(self) -> str:
        """
        Returns:
            name of template for this node in NEURON
        """
        return utils.to_valid_nrn_name(self.biophys_filepath.stem)

    def get_section_list(self):
        """
        Returns:
            List of all sections of ``self.nrn``.
        """
        return self._ephys_model.icell.soma[0].wholetree()

    def _instantiate(self):
        """Instantiates itself in NEURON"""
        self._instantiate_node()
        self.edges_reduction.instantiate()

    def _instantiate_node(self):
        """Instantiates only node without synapses in NEURON"""
        if self.biophys_filepath.suffix == '.nml':
            biophysics = convert_to_hoc.load_neuroml(str(self.biophys_filepath))
            mechanisms = convert_to_hoc.define_mechanisms(biophysics)
            parameters = convert_to_hoc.define_parameters(biophysics)
            self._ephys_model = models.CellModel(
                self.template_name,
                NrnFileMorphology(str(self.morphology_filepath)),
                mechanisms,
                parameters,
                self.node_id
            )
        elif self.biophys_filepath.suffix == '.hoc':
            self._ephys_model = HocCellModel(
                self.template_name,
                self.morphology_filepath,
                str(self.biophys_filepath),
                gid=self.node_id
            )
        else:
            raise ValueError('Unsupported biophysics file {}'.format(self.biophys_filepath))
        self._ephys_model.instantiate(neuron)

    def reduce(self, **kwargs):
        """Performs the node reduction. It can not be ran twice on the same instance.

        Args:
            **kwargs: arguments to pass to the underlying call of ``neuron_reduce.subtree_reductor``
        """
        if self._is_reduced:
            raise RuntimeError('Reduction can be done only once and it is irreversible')
        self._ephys_model.icell, reduced_synapse_list, reduced_netcon_list = \
            neuron_reduce.subtree_reductor(
                self._ephys_model.icell,
                self.edges_reduction.synapses,
                self.edges_reduction.netcons,
                **kwargs, )

        self.edges_reduction.reduce(reduced_synapse_list, reduced_netcon_list)
        self._is_reduced = True

    def write_node(self, output_dirpath: Path):
        """Save node as a json file.

        Args:
            output_dirpath: filepath to a directory where the json is saved
        """
        filepath = output_dirpath.joinpath(str(self.node_id) + '.json')
        self._node.to_json(filepath)

    def write_morphology(self, filepath: Path):  # pylint: disable=no-self-use
        """Save node's instantiated NEURON morphology as an '.swc' file.

        Args:
            filepath: path to a file where to save the morphology
        """
        neuron2swc(str(filepath))

    def write_biophysics(self, filepath: Path, keep_original=True):
        """Save node's instantiated NEURON biophysics as a '.hoc' template from BluePyOpt.

        The current preferred way is to save the original biophysics file as the reduction
        does not change biophysics because each section list has uniform biophysics.
        The another way is to extract all mechanisms and params, and create a '.hoc' biophysics
        from them. This way is very rudimentary because it drops the previous cell details like
        `do_replace_axon` or any other custom code that was presented in the original biophysics
        '.hoc'. Although such details shouldn't be presented in the original '.hoc'. There should be
        only biophysics spec.

        Args:
            filepath: path to a file where to save the morphology
            keep_original: whether to keep the original biophysics file
        """
        if keep_original or self.biophys_filepath.suffix == '.hoc':
            shutil.copyfile(str(self.biophys_filepath), str(filepath))
        elif not keep_original and self.biophys_filepath.suffix == '.nml':
            self._node.at['model_template'] = self._node['model_template'].replace('.nml', '.hoc')
            mechanisms, parameters = get_mechanisms_and_params(self.get_section_list())
            biophysics = create_hoc.create_hoc(
                mechs=mechanisms,
                parameters=parameters,
                morphology=self.morphology_filepath.name,
                template_name=self.template_name)

            with filepath.open('w') as f:
                f.write(biophysics)
