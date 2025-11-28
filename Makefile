.PHONY: dist image help
VERSION=$(shell cat omegaml/VERSION)

# run using make -e to override by env variables
EXTRAS:=dev
PIPREQ:=pip
DISTTAGS:=""

install:
	# in some images pip is outdated, some packages are system-level installed
	# https://stackoverflow.com/questions/49911550/how-to-upgrade-disutils-package-pyyaml
	pip install --ignore-installed -U pip
	pip install -U pytest tox tox-conda tox-run-before
	[ -z "${RUNTESTS}" ] && (pip install gil && gil clone && pip install -r requirements.dev) || echo "env:RUNTESTS set, using packages from pypi only"
	pip install ${PIPOPTS} --progress-bar off -e ".[${EXTRAS}]" "${PIPREQ}" --extra-index-url https://download.pytorch.org/whl/cpu
	(which R && scripts/runtime/setup-r.sh) || echo "R is not installed"
	scripts/install-oras.sh || echo "oras is not installed"

test:
	# add -x to fail on first error
	# PATH is required for tensorflow images
	unset DJANGO_SETTINGS_MODULE; PATH=${HOME}/.local/bin:${PATH} OMEGA_TEST_MODE=1 pytest -v -s --instafail --log-level=DEBUG --tb=native ${TESTS}

freeze:
	echo "Writing pip requirements to requirements.txt"
	pip-compile --output-file requirements.txt

sanity:
	# quick sanity check -- avoid easy mistakes
	unset DJANGO_SETTINGS_MODULE && python -m omegaml.client.cli --version
	unset DJANGO_SETTINGS_MODULE && python -m omegaml.client.cli cloud config

dist: #sanity
	: "run setup.py sdist bdist_wheel"
	rm -rf ./dist/*
	rm -rf ./build/*
	# set DISTTAGS to specify eg --python-tag for bdist
	python -m build --sdist --wheel --config-setting="--build-option=${DISTTAGS}"
	twine check dist/*.whl

livetest: dist
	scripts/livetest.sh --local --build

devtest:
	scripts/devtest.sh --headless

image:
	: "run docker build"
	scripts/livetest.sh --build

runtime-tests: devstart
	# actual specs are in scripts/docker/test_images.txt
	scripts/runtests.sh --rmi --specs scripts/docker/test_images_minimal.ini

release-test: bumpbuild dist
	: "twine upload to pypi test"
	# see https://packaging.python.org/tutorials/packaging-projects/
	# config is in $HOME/.pypirc
	twine upload --skip-existing --repository testpypi-omegaml dist/*gz
	twine upload --repository testpypi-omegaml dist/*whl
	sleep 5
	scripts/livetest.sh --testpypi --build

release-prod: dist livetest
	: "upload to pypi prod and dockerhub"
	# see https://packaging.python.org/tutorials/packaging-projects/
	# config is in $HOME/.pypirc
	twine upload --skip-existing --repository pypi-omegaml dist/*gz dist/*whl

release-docker:
	: "docker push image sto dockerhub"
	scripts/livetest.sh --build --tag ${VERSION}
	# push all images for this version
	docker images | grep -E ".*omegaml/omegaml.*${VERSION}" | xargs -L1 | cut -f 1-2 -d ' ' | tr ' ' : | xargs -L1 docker push
	# tag and push latest
	docker images | grep -E ".*omegaml/omegaml.*${VERSION}" | xargs -L1 | cut -f 1-2 -d ' ' | tr ' ' : | tail -n1 | xargs -I{} docker tag {} omegaml/omegaml:latest
	docker push omegaml/omegaml:latest
	# run livetest to verify the pushed images actually work
	sleep 5
	scripts/livetest.sh

candidate-docker: bumpbuild dist
	scripts/distrelease.sh --distname omegaml --version ${VERSION}
	docker push omegaml/omegaml:${VERSION}

thirdparty:
	: "create THIRDPARTY & THIRDPARTY-LICENSES"
	pip-licenses > THIRDPARTY
	python -m pylicenses

release-tensorflow: bumpbuild dist
	scripts/distrelease.sh --distname omegaml-tensorflow --version ${VERSION}-gpu-jupyter --push

release-pytorch: bumpbuild dist
	scripts/distrelease.sh --distname omegaml-pytorch --version ${VERSION}-gpu-jupyter --push

old:
	rm -rf dist/staging && mkdir -p dist/staging
	cp -r scripts/docker/tensorflow-gpu dist/staging
	cp scripts/runtime dist/staging/docker/tensorflow-gpu/scripts
	cp dist/*whl dist/staging/tensorflow-gpu/packages
	cd dist/staging/tensorflow-gpu && docker build -t omegaml/omegaml-tf:${VERSION} .
	docker push omegaml/omegaml-tf:${VERSION}

# TODO consider https://github.com/semantic-release/semantic-release
bumppatch:
	bumpversion patch

bumpminor:
	bumpversion minor

bumpbuild:
	[ ! -z "${CI_PULL_REQUEST}" ] && echo "CI_PULL_REQUEST is set, not bumping" || bumpversion build

bumpfinal:
	bumpversion release

help:
	@echo -n "Common make targets"
	@echo ":"
	@cat Makefile | grep -A1 -E -e ".*:.*"

devstart:
	docker-compose -f docker-compose-dev.yml up -d --remove-orphans
	cp scripts/mongoinit.js.example scripts/mongoinit.js
	scripts/initlocal.sh

devstop:
	docker-compose -f docker-compose-dev.yml stop

pipsync: freeze
	pip-sync

scan: freeze pipsync
	-snyk test --policy-path=./.snyk > scripts/secdev/.snyk-test.report
	-snyk code test --policy-path=./.snyk > scripts/secdev/.snyk-code-test.report
	mv requirements.txt scripts/secdev/scanned-pipreqs.txt
	cat $(find scripts/secdev/ -name *report)

server-debug:
	# start omegaml server
	export OMEGA_LOCAL_RUNTIME=1; python -m omegaml.server

server:
	OMEGA_LOGLEVEL=DEBUG honcho -f scripts/local/Procfile start server worker

