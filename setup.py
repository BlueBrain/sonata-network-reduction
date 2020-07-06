#!/usr/bin/env python

import imp

from setuptools import setup, find_packages

VERSION = imp.load_source("", "sonata_network_reduction/version.py").__version__

setup(
    name="sonata-network-reduction",
    author="bbp-ou-nse,Alexsei Sanin",
    author_email="bbp-ou-nse@groupes.epfl.ch",
    version=VERSION,
    description="Reduces neuron morphologies from SONATA circuits by the algorithm: "
                "https://github.com/orena1/neuron_reduce",
    url="https://bbpteam.epfl.ch/documentation/projects/sonata-network-reduction",
    project_urls={
        "Tracker": "https://bbpteam.epfl.ch/project/issues/projects/NSETM/issues",
        "Source": "ssh://bbpcode.epfl.ch/nse/sonata-network-reduction",
    },
    entry_points={
        'console_scripts': ['sonata-network-reduction=sonata_network_reduction.cli:cli']},
    license="BBP-internal-confidential",
    python_requires='>=3.6',
    install_requires=[
        'numpy>=1.14',
        'h5py>=2.10',
        'pandas>=0.25',
        'lxml>=4.3.4',
        'tqdm>=4.34',
        'joblib>=0.14',
        'bluepyopt>=1.8.68',
        'bglibpy>=4.2',
        'bluepysnap>=0.5.1',
        'neuron_reduce @ git+https://git@github.com/orena1/neuron_reduce.git@master#egg=neuron_reduce',
        'morphio>=2.3.9',
        'click>=6.7',
        'aibs-circuit-converter>=0.0.3',
    ],
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'sonata_network_reduction': ['sonata_network_reduction/templates/*.*'],
    },
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
)
