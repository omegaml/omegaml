.PHONY: dist image help
test: export CURRENT_USER=omegadev

clean:
	rm -rf ./dist/*
	rm -rf ./build/*

bumppatch:
	pip install bumpversion
	bumpversion patch ${BUMPARGS}

bumpminor:
	pip install bumpversion
	bumpversion minor ${BUMPARGS}

bumpbuild:
	pip install bumpversion
	bumpversion build ${BUMPARGS} --allow-dirty --no-commit

dist-prod: clean
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

test: bumpbuild
	-docker-compose up -d || echo "assuming docker-compose environment already running"
	scripts/rundev.sh --docker --cmd "python manage.py test --debug-config --verbosity=2 --exe"

shell:
	scripts/rundev.sh --docker --shell

shellbuild:
	scripts/rundev.sh --docker --shell --clean

requirements:
	# https://stackoverflow.com/a/62886215/890242
	scripts/rundev.sh --docker --cmd "pip list --format=freeze --exclude-editable | grep -f nonrequirements.txt -v > pip-requirements.txt "

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
	@cat /home/patrick/.omegaml/behave.yml | grep -A3 -E "localhost|snowflake" | sed '/^--$$/d' | base64 -w0 | xargs -l1 echo BEHAVE_YML
	@cat /home/patrick/.pypirc | base64 -w0 | xargs -l1 echo PYPIRC_INI
