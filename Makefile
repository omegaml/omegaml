.PHONY: dist image help
VERSION=$(shell cat omegaml/VERSION)

test:
	unset DJANGO_SETTINGS_MODULE && nosetests

dist:
	: "run setup.py sdist bdist_wheel"
	rm -rf ./dist/*
	python setup.py sdist bdist_wheel

livetest: dist
	scripts/livetest.sh --local --build

devtest:
	scripts/devtest.sh

image:
	: "run docker build"
	docker build -t omegaml/omegaml:$(VERSION) .

release-test: dist
	: "twine upload to pypi test"
	# see https://packaging.python.org/tutorials/packaging-projects/
	# config is in $HOME/.pypirc
	twine upload --repository testpypi dist/*
	sleep 5
	scripts/livetest.sh --testpypi

release-prod: test dist
	: "twine upload to pypi prod"
	# see https://packaging.python.org/tutorials/packaging-projects/
	# config is in $HOME/.pypirc
	twine upload --repository pypi dist/*
	sleep 5
	scripts/livetest.sh

release-docker: dist
	: "docker push image sto dockerhub"
	scripts/livetest.sh --local --build --tag ${VERSION}
	docker tag omegaml/omegaml:${VERSION} omegaml/latest
	docker push omegaml/omegaml:${VERSION}
	docker push omegaml/omegaml:latest


thirdparty:
	: "create THIRDPARTY & THIRDPARTY-LICENSES"
	pip-licenses > THIRDPARTY
	python -m pylicenses

help:
		@echo -n "Common make targets"
		@echo ":"
		@cat Makefile | grep -A1 -E -e ".*:.*"