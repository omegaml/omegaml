.PHONY: dist image help
VERSION=$(shell cat omegaee/VERSION)

dist-prod:
	: "build a release"
	rm -rf ./dist/*
	scripts/distrelease.sh --version=${VERSION}

dist:
	: "build a release"
	rm -rf ./dist/*
	scripts/distrelease.sh --nominify

test:
	DJANGO_SETTINGS_MODULE=app.settings python manage.py test --debug-config --verbosity=2

devtest:
	scripts/devtest.sh --headless

release-docker: dist-prod
	: "docker push image sto dockerhub"
	docker push omegaml/omegaml-ee:${VERSION}
	docker push omegaml/omegaml-ee:latest

thirdparty:
	: "create THIRDPARTY & THIRDPARTY-LICENSES"
	pip-licenses > THIRDPARTY
	python -m pylicenses

help:
		@echo -n "Common make targets"
		@echo ":"
		@cat Makefile | grep -A1 -E -e ".*:.*"