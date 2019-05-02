.PHONY: dist image help
VERSION=$(shell cat omegaml/VERSION)

test:
	unset DJANGO_SETTINGS_MODULE && nosetests

dist:
	: "run setup.py sdist bdist_wheel"
	rm -rf ./dist/*
	python setup.py sdist bdist_wheel

test: dist
	scripts/livetest.sh --local

image:
	: "run docker build"
	docker build -t omegaml/omegaml:$(VERSION) -t omegaml/omegaml:latest .

release-test: dist
	: "twine upload to pypi test"
	# see https://packaging.python.org/tutorials/packaging-projects/
	# config is in $HOME/.pypirc
	twine upload --repository testpypi dist/*

release-prod: dist
	: "twine upload to pypi prod"
	# see https://packaging.python.org/tutorials/packaging-projects/
	# config is in $HOME/.pypirc
	twine upload --repository pypi dist/*

release-docker:
	: "docker push image sto dockerhub"
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