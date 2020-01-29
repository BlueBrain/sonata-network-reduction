#!/usr/bin/env python

import imp
import sys

from setuptools import setup, find_packages

if sys.version_info < (3,):
    sys.exit("Sorry, Python < 3 is not supported")

VERSION = imp.load_source("", "sonata_network_reduction/version.py").__version__

setup(
    name="sonata-network-reduction",
    author="BlueBrain NSE",
    author_email="aleksei.sanin@epfl.ch",
    version=VERSION,
    description="TODO: write something meaningful here",
    url="https://bbpteam.epfl.ch/documentation/projects/sonata-network-reduction",
    project_urls={
        "Tracker": "https://bbpteam.epfl.ch/project/issues/projects/NSETM/issues",
        "Source": "ssh://bbpcode.epfl.ch/nse/sonata-network-reduction",
    },
    entry_points={
        'console_scripts': ['sonata-network-reduction=sonata_network_reduction.cli:cli']},
    license="BBP-internal-confidential",
    install_requires=[
        'numpy>=1.17',
        'h5py>=2.9',
        'pandas>=0.25',
        'lxml>=4.3.4',
        'tqdm>=4.34',
        'bluepyopt>=1.8.68',
        'bglibpy>=4.2',
        'bluepysnap==0.1.2',
        'neuron_reduce @ git+https://git@github.com/orena1/neuron_reduce.git@master#egg=neuron_reduce',
        'morphio>=2.3',
        'click>=6.7',
        'aibs-circuit-converter',
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
