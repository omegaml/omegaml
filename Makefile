.PHONY: dist image help
VERSION=$(shell cat omegaml/VERSION)

test:
	unset DJANGO_SETTINGS_MODULE && nosetests -v

sanity:
	# quick sanity check -- avoid easy mistakes
	unset DJANGO_SETTINGS_MODULE && python -m omegaml.client.cli cloud config

dist:
	: "run setup.py sdist bdist_wheel"
	rm -rf ./dist/*
	rm -rf ./build/*
	python setup.py sdist bdist_wheel
	twine check dist/*.whl

livetest: dist
	scripts/livetest.sh --local --build

devtest:
	scripts/devtest.sh --headless

image:
	: "run docker build"
	scripts/livetest.sh --build

release-test: dist sanity
	: "twine upload to pypi test"
	# see https://packaging.python.org/tutorials/packaging-projects/
	# config is in $HOME/.pypirc
	twine upload --repository testpypi dist/*gz dist/*whl
	sleep 5
	scripts/livetest.sh --testpypi --build

release-prod: test dist sanity
	: "upload to pypi prod and dockerhub"
	# see https://packaging.python.org/tutorials/packaging-projects/
	# config is in $HOME/.pypirc
	scripts/livetest.sh --local --build --tag ${VERSION}
	docker tag omegaml/omegaml:${VERSION} omegaml/latest
	docker push omegaml/omegaml:${VERSION}
	docker push omegaml/omegaml:latest
	twine upload --repository pypi dist/*gz dist/*whl
	sleep 5
	scripts/livetest.sh

candidate-docker: sanity dist
	scripts/distrelease.sh --distname omegaml --version ${VERSION}
	docker push omegaml/omegaml:${VERSION}

thirdparty:
	: "create THIRDPARTY & THIRDPARTY-LICENSES"
	pip-licenses > THIRDPARTY
	python -m pylicenses

release-tensorflow: dist
	scripts/distrelease.sh --distname omegaml-tensorflow --version ${VERSION}-gpu-jupyter --push

release-pytorch: dist
	scripts/distrelease.sh --distname omegaml-pytorch --version ${VERSION}-gpu-jupyter --push

old:
	rm -rf dist/staging && mkdir -p dist/staging
	cp -r scripts/docker/tensorflow-gpu dist/staging
	cp scripts/runtime dist/staging/docker/tensorflow-gpu/scripts
	cp dist/*whl dist/staging/tensorflow-gpu/packages
	cd dist/staging/tensorflow-gpu && docker build -t omegaml/omegaml-tf:${VERSION} .
	docker push omegaml/omegaml-tf:${VERSION}

bumppatch:
	bumpversion patch

bumpminor:
	bumpversion minor

bumpbuild:
	bumpversion build

bumpfinal:
	bumpversion release

help:
		@echo -n "Common make targets"
		@echo ":"
		@cat Makefile | grep -A1 -E -e ".*:.*"
