#!/bin/sh

set -e

INSTALL_DIR=$1

if [ ! -e ${INSTALL_DIR}/.install_finished ]
then
    echo 'Neurodamus was not fully installed in previous build, installing ...'
    mkdir -p ${INSTALL_DIR}
    cd ${INSTALL_DIR}

    echo "Downloading neurodamus core ..."
    rm -rf neurodamus-core
    git clone --depth 1 ssh://bbpcode.epfl.ch/sim/neurodamus-core

    touch -f .install_finished
    echo "Neurodamus successfully installed"
else
    echo 'Neurodamus was successfully installed in previous build, not rebuilding'
fi
