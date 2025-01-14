import os
import logging
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from distutils.dir_util import copy_tree
from pathlib import Path

from bluepysnap import Circuit
from neuron import h

os.environ.setdefault('LOGLEVEL', 'DEBUG')
logging.basicConfig(level=os.environ.get('LOGLEVEL'))
TEST_DATA_DIR = Path(__file__).resolve().parent / 'data'


@contextmanager
def copy_circuit(circuit_config_file):
    """Copies test/data circuit to a temp directory.

    Returns:
        yields a path to the copied circuit dir and circuit config file
    """
    with tempfile.TemporaryDirectory() as copied_circuit_dir:
        copy_tree(str(circuit_config_file.parent), copied_circuit_dir)
        copied_circuit_dir = Path(copied_circuit_dir)
        yield copied_circuit_dir, copied_circuit_dir / circuit_config_file.name


@contextmanager
def compile_circuit_mod_files(circuit):
    """Compiles circuit's mod files.

    IMPORTANT! It changes the current working dir to a temporary directory with compiled mods
    during its execution. Restores it back when finishes.
    Args:
        circuit(Circuit): instance of Circuit

    Returns:
        Nothing. It is a context manager. Upon exiting the compiled mod files will be deleted.
    """
    mod_dirpath = Path(circuit.config['components']['mechanisms_dir'], 'modfiles')
    compiled_mod_dirpath, compiled_mod_filepath = _compile_mod_files(mod_dirpath)
    h.nrn_load_dll(compiled_mod_filepath)
    original_cwd = os.getcwd()
    try:
        os.chdir(compiled_mod_dirpath)
        yield
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(compiled_mod_dirpath)


def _compile_mod_files(mod_dirpath: Path):
    """Compiles mod files relative to ``TEST_DATA_DIR``. Compiling relative is necessary
     otherwise `nrnivmodl` fails to compile.

    Args:
        mod_dirpath: directory with mod files

    Returns:
        Tuple of (path to directory with compiled mod files, path to `libnrnmech.so` file)
    """
    compiled_mod_dirpath = tempfile.mkdtemp(dir=TEST_DATA_DIR)
    rel_compiled_mod_dirpath = os.path.relpath(str(mod_dirpath), start=compiled_mod_dirpath)
    process = subprocess.Popen(
        ['nrnivmodl', rel_compiled_mod_dirpath],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=compiled_mod_dirpath,
    )
    stdout, stderr = process.communicate()
    only_child_dir = os.listdir(compiled_mod_dirpath)[0]
    compiled_mod_filepath = os.path.join(
        compiled_mod_dirpath, only_child_dir, '.libs', 'libnrnmech.so')
    if not os.path.isfile(compiled_mod_filepath):
        raise RuntimeError("Couldn't compile mod files", compiled_mod_filepath, stdout, stderr)
    return compiled_mod_dirpath, compiled_mod_filepath
