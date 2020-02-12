import tempfile
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner

from sonata_network_reduction.cli import cli

current_dir = Path(__file__).resolve().parent
circuit_dir = current_dir / 'data' / '9cells'
circuit_config_file = circuit_dir / 'bglibpy_circuit_config.json'


def test_cli_default():
    with tempfile.TemporaryDirectory() as tmpdirname:
        with patch('sonata_network_reduction.cli.reduce_network') as reduce_network_mock:
            reduce_network_mock.return_value = 0
            runner = CliRunner()
            result = runner.invoke(cli, [str(circuit_config_file), tmpdirname])
            assert reduce_network_mock.call_count == 1
            assert result.exit_code == 0
            args = reduce_network_mock.call_args[0]
            assert args == (Path(circuit_config_file), Path(tmpdirname))
            kwargs = reduce_network_mock.call_args[1]
            assert kwargs == {
                'reduction_frequency': 0,
                'total_segments_manual': -1,
                'return_seg_to_seg': False,
            }


def test_cli_convert():
    with tempfile.TemporaryDirectory() as tmpdirname:
        with patch('sonata_network_reduction.cli.reduce_network') as reduce_network_mock:
            reduce_network_mock.return_value = 0
            runner = CliRunner()
            runner.invoke(cli, [
                str(circuit_config_file), tmpdirname,
                '--reduction_frequency', '0.5',
                '--total_segments_manual', '10',
                '--return_seg_to_seg', 'True',
            ])
            kwargs = reduce_network_mock.call_args[1]
            assert kwargs == {
                'reduction_frequency': 0.5,
                'total_segments_manual': 10,
                'return_seg_to_seg': True,
            }
