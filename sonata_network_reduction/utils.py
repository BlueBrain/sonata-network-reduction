import re


def to_valid_var_name(var_name):
    return re.sub(r'\W|^(?=\d)', '_', var_name)
