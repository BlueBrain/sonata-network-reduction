Application of neuron_reduce algorithm to a Sonata network.

- Currently a single cell reduction can be done only.
- We use outdated edge specification without afferent/efferent separation like ``afferent_section_id``.
- You must have python API of Neuron simulator for your python.
- Currently we don't support synapses for outcome connections
- Remove ``virtual_hoc_cache`` from ``SonataApi``. Access somehow cells from NEURON and don't store in our code.
- We need to apply ``run_params['dL']/['spike_treshold']`` to instantiated neurons in order to obtain the same results from running.
- Tests must be run in forked mode because I couldn't manage how to reset Neuron between tests. For example ``python -m pytest -s -v --forked``.
- Section identification isn't completely specified. We have to think through it for now.