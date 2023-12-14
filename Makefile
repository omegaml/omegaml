.PHONY: dist image help
test: export CURRENT_USER=omegadev
license: export LICENSE_DOCX=/home/patrick/Dropbox/shrebo_mgmt/05_Legal/omegaml/EULA_Q12022-E.docx

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
	-bash -c "docker-compose stop"
	scripts/distrelease.sh --version=`cat omegaee/RELEASE`

dist: clean
	: "build a release"
	-bash -c "docker-compose stop"
	rm -rf ./dist/*
	scripts/distrelease.sh --nominify --version=`cat omegaee/RELEASE`

candidate-dist: clean
	-bash -c "docker-compose stop"
	rm -rf ./dist/*
	scripts/distrelease.sh --nominify --version=`cat omegaee/RELEASE` --nolivetest

test: bumpbuild
	-docker-compose up -d || echo "assuming docker-compose environment already running"
	scripts/rundev.sh --docker --cmd "python manage.py test"

test-local:
	docker-compose up -d mongodb rabbitmq
	scripts/initlocal.sh
	python manage.py test

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

release-docker: bumpbuild dist-prod
	: "docker push image to dockerhub"
	docker push omegaml/omegaml-ee:`cat omegaee/RELEASE`

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

license:
	-rstfromdocx ${LICENSE_DOCX}
	cat $(shell basename -s .docx ${LICENSE_DOCX} )/*.rest > LICENSE
	rm -rf $(shell basename -s .docx ${LICENSE_DOCX})

baseimages:
	docker pull jupyter/datascience-notebook:python-3.11
	docker pull jupyter/datascience-notebook:python-3.10
	docker pull jupyter/datascience-notebook:python-3.9
	docker images | grep jupyter/datascience-notebook | xargs -L1 | cut -d ' ' -f 2 | xargs -I{} docker tag jupyter/datascience-notebook:{} omegaml/datascience-notebook:{}
	docker images | grep jupyter/datascience-notebook | xargs -L1 | cut -d ' ' -f 2 | xargs -I{} docker tag jupyter/datascience-notebook:{} ghcr.io/omegaml/datascience-notebook:{}
	docker images | grep omegaml/datascience-notebook | xargs -L1 | cut -d ' ' -f 1-2 | tr ' ' : | xargs -L1 docker push
