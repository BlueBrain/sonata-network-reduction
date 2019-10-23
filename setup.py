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
        'numpy',
        'h5py',
        'pandas',
        'lxml',
        'tqdm',
        'bluepyopt',
        'bluepysnap>=0.1.2',
        'neuron_reduce>=0.0.6',
        'click>=6.7',
        'aibs-circuit-converter',
        'hoc2swc @ git+https://git@github.com/JustasB/hoc2swc.git@master#egg=hoc2swc',
    ],
    packages=find_packages(),
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
)
