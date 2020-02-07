ARG APP_PATH=/opt/sonata-reduction
ARG VENV_PATH=$APP_PATH/venv

######## Temporary building image
FROM python:3.7-slim-stretch as builder
RUN pip install --upgrade pip setuptools
RUN apt-get update && apt-get install -yq \
    wget libx11-6 python-dev git build-essential libncurses-dev

# activate virtualenv
ARG APP_PATH
ARG VENV_PATH
RUN python -m venv $VENV_PATH
ENV PATH="$VENV_PATH/bin:$PATH"

# NEURON simulator
RUN wget https://neuron.yale.edu/ftp/neuron/versions/v7.7/nrn-7.7.tar.gz
RUN tar -xzf nrn-7.7.tar.gz && rm nrn-7.7.tar.gz
WORKDIR /nrn-7.7
RUN ./configure \
  --without-x \
  --disable-rx3d \
  --with-nrnpython=python \
  && make -j4 \
  && make install \
  && cd /nrn-7.7/src/nrnpython \
  && python setup.py install \
  && rm -rf /nrn-7.7

# compile circuit mod files
WORKDIR /mod
ARG mods_dir
COPY $mods_dir/ ./
ENV PATH="/usr/local/nrn/x86_64/bin:${PATH}"
RUN if [ "x$mods_dir" = "x" ] ; then \
    mkdir x86_64 ; \
  else \
    nrnivmodl . ; \
  fi

## install the package
WORKDIR /build
ARG python_dist_dir
COPY $python_dist_dir/* ./
RUN pip install \
    --no-cache-dir \
    -i https://bbpteam.epfl.ch/repository/devpi/simple \
    $(ls -t *.* | head -n 1)

######### Final deployment image
FROM python:3.7-slim-stretch as result
LABEL maintainer="BlueBrain NSE(Neuroscientific Software Engineering)"
RUN apt-get update && apt-get install -yq build-essential libncurses-dev

ARG neurodamus_hoc_dir
ARG APP_PATH
ARG VENV_PATH
WORKDIR $APP_PATH
COPY $neurodamus_hoc_dir/* ./neurodamus_hoc_dir/
COPY --from=builder $VENV_PATH $VENV_PATH
COPY --from=builder /usr/local/nrn /usr/local/nrn

#activate virtualenv with the installed package
ENV PATH="/usr/local/nrn/x86_64/bin:$VENV_PATH/bin:${PATH}"
ENV PYTHONPATH="/usr/local/nrn/lib/python"
ENV HOC_LIBRARY_PATH="$APP_PATH/neurodamus_hoc_dir/"

ENV HOME /home/sonata-network-reduction
WORKDIR $HOME
COPY --from=builder /mod/x86_64/ ./x86_64/

EXPOSE 8000