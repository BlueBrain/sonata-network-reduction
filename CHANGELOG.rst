Changelog
=========

Version 0.0.10
--------------

- Fixed edges reduction when some sonata attributes are not presented at all. Solves the problem
    of projections edges which don't have 'efferent' attributes.

- Fixed BGLibPy==4.3.3 dependency update

Version 0.0.9
-------------

- Changed error handling. Now the reduction of a network population fails if more than 5 of its nodes fail.
- Added circuit validation before starting the reduction.

Version 0.0.8
-------------

- Added better error handing and biophysical neurons detection.
- Changed edge fields to use SONATA values instead of BluePy values.
  Now it expects:
  ``afferent_section_id`` instead of ``morpho_section_id_post``
  ``afferent_segment_id`` instead of ``morpho_segment_id_post``
  ``afferent_segment_offset`` instead of ``morpho_offset_segment_post``
  ``efferent_section_id`` instead of ``morpho_section_id_pre``
  ``efferent_segment_id`` instead of ``morpho_segment_id_pre``
  ``efferent_segment_offset`` instead of ``morpho_offset_segment_pre``
- Changed output to be less verbose. Use ``neuron_reduce`` with logging turned off.
  Disable ``morphio`` warnings. Use tqdm.
- Changed writing of string attributes of reduced nodes to use
  `enum datatypes <https://github.com/AllenInstitute/sonata/blob/master/docs/SONATA_DEVELOPER_GUIDE.md#nodes---enum-datatypes>`__.

Version 0.0.7
-------------

- Added in-place single node reduction NSETM-988.

Version 0.0.6
-------------

- Added better documentation
- Fixed segment id/offset calculation for a border case
