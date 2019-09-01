import re
import os


def to_valid_nrn_name(var_name):
    return re.sub(r'\W|^(?=\d)', '_', var_name)


def filename(filepath):
    return os.path.splitext(os.path.basename(filepath))[0]
