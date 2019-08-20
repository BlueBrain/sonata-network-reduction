This example has been taken from [Sonata repo](https://github.com/AllenInstitute/sonata/tree/master/examples/9_cells) and adjusted. The changes are:
 - Force unique ids among node types and edge types. Before they used the same ids and because of that Sonata API couldn't read config files.
 - Provide all tags with `id` attribute in nml files.
 - Replace `erev` with `e` in synaptic_models as `Exp2Syn` expects `e` for reversal potential.
 - replace `vecevent.mod` in `mechanisms/modfiles` with the latest from `master` because the previous one was from 2002 with [this error](https://neuron.yale.edu/phpbb/viewtopic.php?f=2&t=2147#p10276). 
 - The old specification of synapses is used. The one with `sec_id`, `sec_x`. See [the previous docu](https://github.com/AllenInstitute/sonata/blob/f6040cd4fdccd9e5536e57322f11e6ce5805e773/docs/SONATA_DEVELOPER_GUIDE.md#neuron_networks_edges) for reference.