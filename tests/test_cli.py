import tempfile
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner

from sonata_network_reduction.cli import network, node
from utils import TEST_DATA_DIR

circuit_config_file = TEST_DATA_DIR / '9cells' / 'bglibpy_circuit_config.json'


def test_cli_network_default():
    with tempfile.TemporaryDirectory() as tmpdirname:
        with patch('sonata_network_reduction.cli.reduce_network') as reduce_network_mock:
            reduce_network_mock.return_value = 0
            runner = CliRunner()
            result = runner.invoke(network, [str(circuit_config_file), tmpdirname])
            assert reduce_network_mock.call_count == 1
            assert result.exit_code == 0
            args = reduce_network_mock.call_args[0]
            assert args == (Path(circuit_config_file), Path(tmpdirname))
            kwargs = reduce_network_mock.call_args[1]
            assert kwargs == {
                'reduction_frequency': 0,
                'mapping_type': 'impedance',
                'model_filename': 'model.hoc',
                'total_segments_manual': -1.0
            }


def test_cli_network_kwargs():
    with tempfile.TemporaryDirectory() as tmpdirname:
        with patch('sonata_network_reduction.cli.reduce_network') as reduce_network_mock:
            reduce_network_mock.return_value = 0
            runner = CliRunner()
            result = runner.invoke(
                network, [str(circuit_config_file), tmpdirname, '--reduction_frequency', '5'])
            assert reduce_network_mock.call_count == 1
            assert result.exit_code == 0
            args = reduce_network_mock.call_args[0]
            assert args == (Path(circuit_config_file), Path(tmpdirname))
            kwargs = reduce_network_mock.call_args[1]
            assert kwargs == {
                'reduction_frequency': 5.0,
                'mapping_type': 'impedance',
                'model_filename': 'model.hoc',
                'total_segments_manual': -1.0
            }


def test_cli_node():
    with tempfile.TemporaryDirectory() as tmpdirname:
        with patch('sonata_network_reduction.cli._reduce_node_same_process') as reduce_node_mock:
            reduce_node_mock.return_value = 0
            runner = CliRunner()
            result = runner.invoke(node, ['0', 'cortex', str(circuit_config_file), tmpdirname])
            assert reduce_node_mock.call_count == 1
            assert result.exit_code == 0
            args = reduce_node_mock.call_args[0]
            assert args == (0, 'cortex', Path(circuit_config_file), Path(tmpdirname))
            kwargs = reduce_node_mock.call_args[1]
            assert kwargs == {
                'reduction_frequency': 0,
                'mapping_type': 'impedance',
                'model_filename': 'model.hoc',
                'total_segments_manual': -1.0
            }


def test_cli_node_inplace():
    with tempfile.TemporaryDirectory():
        with patch('sonata_network_reduction.cli._reduce_node_same_process') as reduce_node_mock:
            reduce_node_mock.return_value = 0
            runner = CliRunner()
            result = runner.invoke(node, ['0', 'cortex', str(circuit_config_file)], 'y')
            assert reduce_node_mock.call_count == 1
            assert result.exit_code == 0
            args = reduce_node_mock.call_args[0]
            assert args == (0, 'cortex', Path(circuit_config_file), None)
            kwargs = reduce_node_mock.call_args[1]
            assert kwargs == {
                'reduction_frequency': 0,
                'mapping_type': 'impedance',
                'model_filename': 'model.hoc',
                'total_segments_manual': -1.0
            }
