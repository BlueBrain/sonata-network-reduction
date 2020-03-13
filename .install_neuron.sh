#!/bin/sh
set -e

SRC_DIR=$1
INSTALL_DIR=$2

if [ ! -e ${INSTALL_DIR}/.install_finished ]
then
  echo 'Neuron was not fully installed in previous build, installing ...'
  mkdir -p ${SRC_DIR}
  cd ${SRC_DIR}
    echo "Downloading NEURON ..."
    rm -rf nrn
    git clone --depth 1 https://github.com/neuronsimulator/nrn.git >download.log 2>&1
    cd nrn
      echo "Preparing NEURON ..."
      ./build.sh >prepare.log 2>&1
      echo "Configuring NEURON ..."
      # use `--with-readline=no` on MacOS
      ./configure --prefix=${INSTALL_DIR}/nrn --without-x --with-nrnpython=python --disable-rx3d >configure.log 2>&1
      echo "Building NEURON ..."
      make -j4 >make.log 2>&1
      echo "Installing NEURON ..."
      make -j4 install >install.log 2>&1

      export PATH="${INSTALL_DIR}/nrn/x86_64/bin":${PATH}
      export PYTHONPATH="${INSTALL_DIR}/nrn/lib/python":${PYTHONPATH}

      cd src/nrnpython
      python setup.py install
      cd ../../

  echo "Testing NEURON import ...."
  python -c 'import neuron' >testimport.log 2>&1
  touch -f ${INSTALL_DIR}/.install_finished
  echo "NEURON successfully installed"
else
    echo 'Neuron was successfully installed in previous build, not rebuilding'
    export PATH="${INSTALL_DIR}/nrn/x86_64/bin":${PATH}
    export PYTHONPATH="${INSTALL_DIR}/nrn/lib/python":${PYTHONPATH}
fi
