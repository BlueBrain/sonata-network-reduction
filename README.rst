Sonata Network Reduction
========================
Project that allows to apply `neuron_reduce <https://github.com/orena1/neuron_reduce>`__ algorithm to
a `Sonata network <https://github.com/AllenInstitute/sonata>`__.

Docker
------------

The project can be used via docker container. To prepare one please do in the project's root:

.. code:: bash

    make docker_build_latest

Further you can use a make target again but be sure to check mount points of it:

.. code:: bash

    make docker_run_dev

Or do it manually:

.. code:: bash

    docker run -v $HOME:/home/your_mounted_home -it sonata-reduction /bin/bash

After you should end up in `/opt/sonata-reduction` of the docker container. Here you should be
able to run a shell command (see example below).

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

    reduce_network('/circuit_config_filepath.json', '/reduced_network_dir', reduction_frequency=0)

**Shell**

.. code:: bash

    sonata-network-reduction /circuit_config_filepath.json /reduced_network_dir

You can use any of **neuron_reduce** arguments.

.. code:: bash

    sonata-network-reduction /circuit_config_filepath.json /reduced_network_dir --reduction-frequency 0.5 --total_segments_manual 0.1

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