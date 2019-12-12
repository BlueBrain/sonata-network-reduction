"""Utilities"""
import re


def to_valid_nrn_name(var_name: str) -> str:
    """
    Args:
        var_name: variable name
    Returns:
        ``var_name`` acceptable for NEURON
    """
    return re.sub(r'\W|^(?=\d)', '_', var_name)
