.PHONY: docker_build_version docker_build_latest help

VERSION?=$(shell grep -Po 'VERSION = "\K.*?(?=")' sonata_network_reduction/version.py)

VENV_DIR:=venv
TMP_DIR:=.tmp
NEURODAMUS_HOC_DIR:=$(TMP_DIR)/neurodamus-hoc
HIPPOCAMPUS_MOD_DIR:=$(TMP_DIR)/hippocampus-mod
HIPPOCAMPUS_REPO:=ssh://bbpcode.epfl.ch/sim/models/hippocampus

define HELPTEXT
Makefile usage
  Targets:
    install_neurodamus            Helper target for docker targets.
    python_build                  Build the python package.
    docker_build_general          Build local docker image for any circuit.
    docker_build_hippo            Build local docker image for a hippocampus circuit.
    docker_run_dev                Run a built docker. Please consider its mount points before usage.
    clean                         Clear tox supplementary files
    toxbinlinks                   Creates links for bin files in tox
endef
export HELPTEXT

help:
	@echo "$$HELPTEXT"

version:
	echo $(VERSION)

$(VENV_DIR):
	python3 -mvenv $(VENV_DIR)

# NEURODAMUS. Clone its repo and copy its hoc files to NEURODAMUS_HOC_DIR
install_neurodamus:
	mkdir -p $(NEURODAMUS_HOC_DIR)
	rm -rf $(TMP_DIR)/neurodamus
	sh .install_neurodamus.sh $(TMP_DIR)/neurodamus
	yes | cp -Lu $(TMP_DIR)/neurodamus/neurodamus-core/hoc/*.hoc $(NEURODAMUS_HOC_DIR)
	rm -rf $(TMP_DIR)/neurodamus

# HIPPOCAMPUS. Clone its repo and copy hoc files to NEURODAMUS_HOC_DIR, mod files to
# HIPPOCAMPUS_MOD_DIR
install_hippocampus: install_neurodamus
	mkdir -p $(HIPPOCAMPUS_MOD_DIR)
	rm -rf $(TMP_DIR)/hippocampus
	git clone --recurse-submodules $(HIPPOCAMPUS_REPO) $(TMP_DIR)/hippocampus
	yes | cp -Lu $(TMP_DIR)/hippocampus/common/hoc/*.hoc $(NEURODAMUS_HOC_DIR)
	yes | cp -Lu $(TMP_DIR)/hippocampus/hoc/*.hoc $(NEURODAMUS_HOC_DIR)
	yes | cp -Lu $(TMP_DIR)/hippocampus/common/mod/*.mod $(HIPPOCAMPUS_MOD_DIR)
	yes | cp -Lu $(TMP_DIR)/hippocampus/mod/*.mod $(HIPPOCAMPUS_MOD_DIR)
	rm -rf $(TMP_DIR)/hippocampus

python_build: | $(VENV_DIR)
	$(VENV_DIR)/bin/python setup.py sdist

docker_build_general: python_build | install_neurodamus
	docker build -t sonata-reduction:$(VERSION) \
		--build-arg=neurodamus_hoc_dir=$(NEURODAMUS_HOC_DIR) \
		--build-arg=python_dist_dir=dist \
		.

docker_build_hippo: python_build | install_hippocampus
	docker build -t sonata-reduction:$(VERSION) \
		--build-arg=mods_dir=$(HIPPOCAMPUS_MOD_DIR) \
		--build-arg=neurodamus_hoc_dir=$(NEURODAMUS_HOC_DIR) \
		--build-arg=python_dist_dir=dist \
		.
	@printf '\n\e[1mThe generated docker container is for HIPPOCAMPUS circuits only.\e[0m\n'

docker_run_dev:
	docker run \
		--rm \
		--user 1000 \
		-it \
		-v $$(pwd)/circuits:/circuits \
		-e DEBUG=True \
		-p 8888:8000 \
		sonata-reduction /bin/bash

clean:
	@find . -name "*.pyc" -exec rm -rf {} \;
	rm -rf *.png
toxbinlinks:
	cd ${TOX_ENVBINDIR}; find $(TOX_NRNBINDIR) -type f -exec ln -sf \{\} . \;
