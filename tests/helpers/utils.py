import os
import subprocess
import tempfile


def compile_mod_files(tests_dirpath, mod_dirpath):
    """
    Compiles mod files. It is very IMPORTANT to have `tests_dirpath` because we need compile mod files relative
    to `tests_dirpath`. If `mod_dirpath` is absolute then `nrnivmodl` fails to compile.
    :param tests_dirpath: directory of tests
    :param mod_dirpath: directory with mod files
    :return: (path to directory with compiled mod files, path to `libnrnmech.so` file)
    """
    compiled_mod_dirpath = tempfile.mkdtemp(dir=tests_dirpath)
    rel_compiled_mod_dirpath = os.path.relpath(mod_dirpath, start=compiled_mod_dirpath)
    process = subprocess.Popen(
        ['nrnivmodl', rel_compiled_mod_dirpath],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=compiled_mod_dirpath,
    )
    stdout, stderr = process.communicate()
    only_child_dir = os.listdir(compiled_mod_dirpath)[0]
    compiled_mod_filepath = os.path.join(compiled_mod_dirpath, only_child_dir, '.libs', 'libnrnmech.so')
    if not os.path.isfile(compiled_mod_filepath):
        raise RuntimeError("Couldn't compile mod files", compiled_mod_filepath, stdout, stderr)
    return compiled_mod_dirpath, compiled_mod_filepath
