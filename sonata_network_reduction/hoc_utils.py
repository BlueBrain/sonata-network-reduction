from bluepyopt import ephys
from neuron import h
from aibs_circuit_converter import convert_to_hoc


def create_hoc_template(template_name, neuroml_filepath, morphology_filename):
    biophysics = convert_to_hoc.load_neuroml(neuroml_filepath)
    mechanisms = convert_to_hoc.define_mechanisms(biophysics)
    parameters = convert_to_hoc.define_parameters(biophysics)

    hoc_template_text = ephys.create_hoc.create_hoc(
        mechs=mechanisms,
        parameters=parameters,
        template_name=template_name,
        morphology=morphology_filename)
    return hoc_template_text


def execute_hoc_template(template_text):
    """
    Executes and loads a HOC template into Neuron's namespace `h`
    I couldn't manage `h.execute` to work.
    :param template_text:
    :return:
    """
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w+') as f:
        f.write(template_text)
        f.seek(0)
        h.load_file(f.name)
