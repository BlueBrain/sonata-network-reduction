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
    license="BBP-internal-confidential",
    install_requires=[
        'neuron_reduce @ git+https://git@github.com/orena1/neuron_reduce.git@master#egg=neuron_reduce',
        'sonata @ git+https://git@github.com/AllenInstitute/sonata.git@master#egg=sonata&subdirectory=src/pysonata',
        'aibs-circuit-converter @ git+ssh://git@github.com/BlueBrain/aibs-circuit-converter.git@master#egg=aibs-circuit-converter',
        'bluepysnap',
        'lxml',
        'tqdm',
        'bluepyopt',
        'pytest',
        'pytest-xdist',
        'bluepyopt',
    ],
    packages=find_packages(),
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
)
