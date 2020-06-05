SONATA network reduction
========================

SONATA network reduction applies the `neuron_reduce <https://github.com/orena1/neuron_reduce>`__ algorithm to
a `SONATA circuit <https://github.com/AllenInstitute/sonata>`__. For the specification of SONATA circuit,
refer to the `SONATA developer guide <https://github.com/AllenInstitute/sonata/blob/master/docs/SONATA_DEVELOPER_GUIDE.md>`__.

The project can be installed via ``docker`` or ``pip``. On BB5 the project is already installed and
available via ``modules``. Python and shell APIs are available. For either method,
the circuit for simplification must be self-contained, which means:

- The circuit's :file:`config.json` must not contain absolute filepaths.
- The circuit's :file:`config.json` must be in a folder that contains all the circuit's parts. No
  circuit's parts can be outside of this folder.

Install
-------

Docker
~~~~~~

There are two possible containers to use:

- A general container that can be used to reduce any circuit, *docker_build_general*.
- A container that can be used to reduce Hippocampus circuits, *docker_build_hippo*.

For example to prepare the first, do in the project's root:

.. code:: bash

    make docker_build_general

Further you can use a make target to run the docker but be sure to check mount points of it:

.. code:: bash

    make docker_run_dev

Or do it manually:

.. code:: bash

    docker run -v $HOME:/home/your_mounted_home -it sonata-reduction:<put version here> /bin/bash

After that your shell changes directory to :file:`/home/sonata-reduction` of the docker container.
Here you should be able to run a shell command (see an example below). **Don't forget that for a
general container, you must compile your ``.mod`` mechanism files before doing reduction.** Also
don't forget that they must be compiled with a relative path. For example, you mount your
:file:`$HOME/mods` directory to docker's :file:`/mods` directory:

.. code:: bash

    docker run -v $HOME/mods:/mods -it sonata-reduction:<put version here> /bin/bash

Mods files now are in :file:`/mods`. From :file:`/home/sonata-reduction` inside the docker you need to:

.. code:: bash

    nrnivmodl ../../mods

After that you should be able to run reduction with your mods from :file:`/home/sonata-reduction`.

pip
~~~

In a Python virtualenv:

.. code:: bash

    pip install --index-url https://bbpteam.epfl.ch/repository/devpi/bbprelman/dev/+simple/ sonata-network-reduction

NEURON
^^^^^^
Ensure your virtualenv's Python is enabled with NEURON simulator. For that
read documentation on `NEURON's site <https://www.neuron.yale.edu/neuron/>`__ or run
:code:`sh .install_neuron.sh` from the project's root folder. Unfortunately the latter works only in
Linux.

Neurodamus
^^^^^^^^^^
Install Neurodamus by cloning its repo, and declaring :code:`HOC_LIBRARY_PATH`:

.. code:: bash

    git clone https://<your_login>@bbpcode.epfl.ch/code/a/sim/neurodamus-core
    export HOC_LIBRARY_PATH=/the/path/where/you/cloned/neurodamus-core/hoc


Usage
-----
Before using the program make sure you have :code:`HOC_LIBRARY_PATH` environment variable set and
your Python has NEURON simulator enabled. On BB5 and ``docker`` those are enabled automatically.

Python
~~~~~~

.. code:: python

    from sonata_network_reduction.network_reduction import reduce_network

    reduce_network('/circuit_config_filepath.json', '/reduced_network_dir', reduction_frequency=0)

Shell
~~~~~
In bash you can use the following ``neuron_reduce`` arguments: ``reduction_frequency``,
``model_filename``, ``total_segments_manual``, ``mapping_type``. An example:

.. code:: bash

    # entire network reduction
    sonata-network-reduction network .circuit_config_filepath.json ./reduced_network_dir --reduction_frequency 0.5 --total_segments_manual 0.1


As the result :file:`./reduced_network_dir` must contain the copy of the SONATA network described by
:file:`.circuit_config_filepath.json` where all 'biophysical' neurons have been replaced with their
reduced versions. That means their morphologies have been reduced and their edges are updated with
new sections ids and positions.

.. code:: bash

    # single node inplace reduction. Node id is '3' and node population is 'cortex'.
    sonata-network-reduction node 3 cortex /circuit_config_filepath.json --reduction_frequency 0.5


As the result the SONATA network of :file:`/circuit_config_filepath.json` must have its node with
id ``3`` in node population ``cortex`` to be reduced along with its corresponding edges.

.. code:: bash

    # single node reduction. Node id is '3' and node population is 'cortex'.
    sonata-network-reduction node 3 cortex /circuit_config_filepath.json ./reduced_node_3 --reduction_frequency 0.5


As the result the reduced node with id ``3`` will be saved in :file:`./reduced_node_3`. The circuit
won't be affected and will keep the original node with id ``3``.

BB5
~~~
There is a corresponding module for using this project on BB5:

.. code:: bash

    module load py-sonata-network-reduction/<version>
    module load neurodamus-<circuit>/<version>

The first command loads necessary NEURON files for the type of circuit you want to reduce. The
second command loads this project's module. After that you have ``sonata-network-reduction``
in your shell. Refer to the above shell section for its details. If these commands are not
available run :code:`module load unstable` first.

A concrete example for hippocampus circuits:

.. code:: bash

    module load py-sonata-network-reduction/0.0.5
    module load neurodamus-hippocampus/0.4

Tests
~~~~~
Tests must be run in the forked mode because NEURON must be reset between tests.

.. code:: bash

    python -m pytest -s -v --forked

Notes
-----
- Currently we don't support synapses for outcome connections e.g. only afferent edges are reduced.
- In case you want to run reduced network manually. Do not forget to apply
  ``run_params['dL']/['spike_treshold']`` to instantiated neurons in order to obtain the same
  results from running.
