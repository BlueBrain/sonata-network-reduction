"""Utilities"""
import re
from bluepysnap import Circuit


def to_valid_nrn_name(var_name: str) -> str:
    """
    Args:
        var_name: variable name
    Returns:
        ``var_name`` acceptable for NEURON
    """
    return re.sub(r'\W|^(?=\d)', '_', var_name)


def close_sonata_circuit(circuit: Circuit):
    """Close h5 file handles opened by SONATA circuit

    Temporary function until https://github.com/BlueBrain/snap/pull/42 is resolved.
    Args:
        circuit: SONATA circuit
    """

    def _close_context(pop):
        """Close the h5 context for population."""
        if "_population" in pop.__dict__:
            del pop.__dict__["_population"]

    if circuit.nodes:
        for population in circuit.nodes.values():
            _close_context(population)

    if circuit.edges:
        for population in circuit.edges.values():
            _close_context(population)

    del circuit
