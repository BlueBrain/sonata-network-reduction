Sonata Network Reduction
========================
Project that allows to apply `neuron_reduce <https://github.com/orena1/neuron_reduce>`__ algorithm to
a `Sonata network <https://github.com/AllenInstitute/sonata>`__.

Docker
------

The project can be used via docker container. There are 2 containers now:

- A general container for any circuit, ``make docker_build_general``.
- A container with precompiled mods for Hippocampus circuits, ``make docker_build_hippo``.

To prepare one do in the project's root:

.. code:: bash

    make docker_build_general

Further you can use a make target to run the docker but be sure to check mount points of it:

.. code:: bash

    make docker_run_dev

Or do it manually:

.. code:: bash

    docker run -v $HOME:/home/your_mounted_home -it sonata-reduction:<put version here> /bin/bash

After you should end up in :file:`/home/sonata-reduction` of the docker container. Here you should
be able to run a shell command (see an example below). **Don't forget that for a general container,
you must compile your mods before doing reduction.** Also don't forget that they must be
compiled with a relative path. For example, you mount your :file:`$HOME/mods` directory to docker's
:file:`/mods` directory:

.. code:: bash

    docker run -v $HOME/mods:/mods -it sonata-reduction:<put version here> /bin/bash

Mods files now are in :file:`/mods`. From :file:`/home/sonata-reduction` inside the docker you need to:

.. code:: bash

    nrnivmodl ../../mods

After that you should be able to run reduction with your mods from :file:`/home/sonata-reduction`.

Installation
------------

In a fresh virtualenv:

.. code:: bash

    pip install --index-url https://bbpteam.epfl.ch/repository/devpi/bbprelman/dev/+simple/ sonata-network-reduction

Usage
-----
Python
~~~~~~

.. code:: python

    from sonata_network_reduction.network_reduction import reduce_network

    reduce_network('/circuit_config_filepath.json', '/reduced_network_dir', reduction_frequency=0)

Shell
~~~~~

.. code:: bash

    sonata-network-reduction /circuit_config_filepath.json /reduced_network_dir

In bash you can use the following ``neuron_reduce`` arguments: ``reduction_frequency``,
``model_filename``, ``total_segments_manual``, ``mapping_type``. An example:

.. code:: bash

    sonata-network-reduction /circuit_config_filepath.json /reduced_network_dir --reduction-frequency 0.5 --total_segments_manual 0.1

As the result :file:`/reduced_network_dir` must contain the copy of sonata network by
:file:`/circuit_config_filepath.json` where all 'biophysical' neurons have been replaced with their
reduced versions. That means their morphologies have been reduced and their edges are updated with
new sections ids and positions.

BB5
~~~
There is a corresponding module for using this project on BB5. Please type:

.. code:: bash

    module load neurodamus-<circuit>/<version>
    module load py-sonata-network-reduction/<version>

The first command loads necessary Neuron files for the type of circuit you want to reduce. The
second command loads this project's module. After that you have ``sonata-network-reduction``
in your shell. Please refer to the above **Shell** section for its details.
A concrete example for hippocampus circuits:

.. code:: bash

    module load neurodamus-hippocampus/0.4
    module load py-sonata-network-reduction/0.0.5

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