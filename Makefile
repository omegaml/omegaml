.PHONY: dist image help
test: export CURRENT_USER=omegadev

clean:
	rm -rf ./dist/*
	rm -rf ./build/*

bumppatch:
	bumpversion patch

bumpminor:
	bumpversion minor

bumpbuild:
	bumpversion build

dist-prod: test clean
	: "build a release"
	-bash -c "docker ps -q | xargs docker kill"
	scripts/distrelease.sh --version=`cat omegaee/RELEASE`

dist: clean
	: "build a release"
	-bash -c "docker ps -q | xargs docker kill"
	rm -rf ./dist/*
	scripts/distrelease.sh --nominify --version=`cat omegaee/RELEASE`

candidate-dist: clean
	-bash -c "docker ps -q | xargs docker kill"
	rm -rf ./dist/*
	scripts/distrelease.sh --nominify --version=`cat omegaee/RELEASE` --nolivetest

test:
	-docker-compose up -d || echo "assuming docker-compose environment already running"
	# note we use --exe to make this work with circleci, where all files are executable due to a uid/gid quirk
	scripts/rundev.sh --docker --cmd "python manage.py test --debug-config --verbosity=2 --exe"
	scripts/rundev.sh --docker --cmd "python manage.py test omegaml --debug-config --verbosity=2 --exe"

devtest:
	scripts/devtest.sh --headless

candidate-docker: bumpbuild candidate-dist
	: "docker push image to dockerhub"
	docker push omegaml/omegaml-ee:`cat omegaee/RELEASE`

release-docker: dist-prod
	: "docker push image to dockerhub"
	docker push omegaml/omegaml-ee:`cat omegaee/RELEASE`
	docker push omegaml/omegaml-ee:latest

thirdparty:
	: "create THIRDPARTY & THIRDPARTY-LICENSES"
	pip-licenses > THIRDPARTY
	python -m pylicenses

help:
		@echo -n "Common make targets"
		@echo ":"
		@cat Makefile | grep -A1 -E -e ".*:.*"

circleci:
	# put this into the BEHAVE_YML env variable to decode in circleci config.yml
	@cat /home/patrick/.omegaml/behave.yml | grep -A3 -E "localhost|snowflake" | sed '/^--$$/d' | base64 -w0 && echo
