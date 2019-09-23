Sonata Network Reduction
========================
Project that allows to apply `neuron_reduce <https://github.com/orena1/neuron_reduce>`__ algorithm to
a `Sonata network <https://github.com/AllenInstitute/sonata>`__.

Installation
------------

In a fresh virtualenv:

.. code:: bash

    pip install --index-url https://bbpteam.epfl.ch/repository/devpi/bbprelman/dev/+simple/ sonata-network-reduction

Usage
-----
**Python**

.. code:: python

    from sonata_network_reduction.network_reduction import reduce_network
    from sonata_network_reduction.sonata_api import SonataApi

    sonata_api = SonataApi('/circuit_config_filepath.json', '/simulation_config_filepath.json')
    reduce_network(sonata_api, '/reduced_network_dir')

**Shell**

.. code:: bash

    sonata-network-reduction /circuit_config_filepath.json /simulation_config_filepath.json /reduced_network_dir

As the result ``/reduced_network_dir`` must contain the copy of ``sonata_api``'s sonata network
where all 'biophysical' neurons are replaced with their reduced versions. That means their
morphologies are reduced and their edges are updated with new sections ids and positions.

Notes
-----
- Your python must be enabled with NEURON simulator. For that please read documentation on
  `NEURON's site <https://www.neuron.yale.edu/neuron/>`__ or run 'install_neuron.sh' in this
  directory. The latter works only for Linux.
- Currently we don't support synapses for outcome connections
- In case you want to run reduced network manually. Please do not forget to apply
  ``run_params['dL']/['spike_treshold']`` to instantiated neurons in order to obtain the same
  results from running.
- Tests must be run in forked mode because NEURON must be reset between tests. For example
  ``python -m pytest -s -v --forked``.
- Sonata specification does not fully cover how sections id are enumerated. This might be a problem.