#!/usr/bin/env bash
##
## TODO: consider using tox-docker instead
##       https://tox-docker.readthedocs.io/en/latest/
##
## run tests in multiple environments
##    @script.name [option]
##
## This runs the project tests by pip installing it in multiple docker images.
## All results are collected, tar'd and summarised in one go.
##
## Options:
##    --specs=VALUE   specs file, defaults to ./docker/test_images.ini
##    --image=VALUE   the image to run tests for
##    --tests=VALUE   the tests to run as package.module
##    --extras=VALUE  extras to install before running
##    --label=VALUE   the label for this test
##    --clean         clean testlogs before starting
##    --shell         enter shell after running tests
##    --rmi           remove images after completion of tests
##    --verbose       print more messages
##    --specid=VALUE  specify the section in ini file
##    --describe      list all specids in file
##
##    Specifying --specs overrides --image, --tests, --extras, --labels.
##    Specifying no option, or --specs, implies --clean.
##    To debug tests with some image, use the --image, --tests, --shell options.
##    The --shell option drops to a bash shell inside the container upon test
##    completion.
##
## Format of the specs file:
##    The specs file is a ini file with the following fields per section.
##    Each section specifies a docker image along with tests to execute. All
##    other fields are optional
##
##    [section]
##    image=<image:tag>
##    tests=<test-spec>
##    extras=<extras>
##    pipreq=<pipreq>
##    pipopts=<pipopts>
##    dockeropts=<docker opts>
##    label=<label>
##
##    image       the account/image:tag
##    test-spec   the names of the tests passed to make install (via TESTS variable)
##    extras      the packages [extras] to be installed, optional, defaults to [dev]
##    pipreq      additional pip requirements, optional
##    pipopts     additional pip options, optional
##    dockeropts  additional docker run options to create the container
##    label       the label for this test, optional. useful if same image listed multiple times
##
## How it works:
##
##    For each image listed in specs file (e.g. --specs test_images.ini),
##
##    1. run the docker container, downloading the image if not cached yet
##    2. install the project (make install)
##    3. install any additional dependencies, if listed for the image
##    4. run the tests (make test)
##    5. freeze pip packages (for reproducing and reference)
##    6. collect test results (creates a tgz for each run)
##
##    Finally, print a test summary and exist with non-zero if any one of the
##    tests failed.
##
## Project requirements:
##
##     1. Provide a setup.py that works
##     2. Create a Makefile that has install and test targets
##        install is called first, then test
##
##     The make file gets passed the following variables
##
##     install:
##         PIPOPTS   options to pass to pip (pipopts field in specs)
##         EXTRAS    extras to install with the package (.[$EXTRAS])
#                    (extras field in specs)
##         PIPREQ    additional pip requirements (pipreq fields in specs)
##
##     test:
##         TESTS     the tests to run (test-spec field in specs)
##
##     Technically, runtests is oblivious to the commands run by the Makefile.
##     Typically you would use something like:
##
##     install:
##         pip install ${PIPOPTS} -e[${EXTRAS}] ${PIPREQ}
##
##     test:
##         python -m unittest ${TESTS}
##
## Output:
##     runtests outputs a summary of all tests and their status. If any of the
##     tests failed it will have exit code 1, else 0.
##
##     In addition, for every test a .tgz file is stored in the $logbase
##     directory. Each tgz contains all output produced by a single test run
##     against a particular docker image. The .tgz files are named by their
##     image + test specs (e.g. jupyter/datascience-notebook:python-3.9.7.tgz)
# script setup to parse options
script_dir=$(dirname "$0")
script_dir=$(realpath $script_dir)
source $script_dir/easyoptions || exit
source $script_dir/read_ini.sh

# location of project source under test (matches in-container $test_base)
sources_dir=$script_dir/..
# all images we want to test, and list of tests
test_images=${specs:-$script_dir/docker/test_images_minimal.ini}
# in-container location of project source under test
test_base=/tmp/runtests/project
# host log files
test_logbase=/tmp/testlogs
# host test rc file
test_logrc=$test_logbase/tests_rc.log

function runimage() {
  # args
  tests=$2
  extras=$3
  pipreq=$4
  pipopts=$5
  dockeropts=$6
  label=$7
  # run
  test_label=${label:-${tests//[^[:alnum:]]/_}}
  echo "INFO runtests: running tests=$tests image=$image extras=>$extras<, pipreq=>$pipreq<, dockeropts=>$dockeropts<"
  # host name of log directory for this test
  test_logdir=$test_logbase/$(dirname $image)/$(basename $image)/$test_label
  # host name of log file
  test_logfn=$test_logdir/$(basename $image).log
  # host name of pip freeze output file
  test_pipfn=$test_logdir/pip-requirements.lst
  # host name of final results tar
  test_logtar=$test_logbase/$(dirname $image)_$(basename $image)_$test_label.tgz
  # start test container
  mkdir -p $test_logdir
  extras=${extras:-dev}
  pipreq=${pipreq:-pip}
  docker rm -f omegaml-test
  if [[ -z $verbose ]]; then
    echo "INFO runtests pulling docker images (quiet)"
    docker pull -q $image
  fi
  echo "INFO runtests starting tests now"
  # docker run arguments
  # --network specifies to use the host network so we can access mongodb, rabbitmq
  # --name name of container, useful for further docker commands
  # --user, --group-add-users specify the jupyter stacks user
  # -dt deamon with tty
  # -v maps the host path to the container
  # -w container working directory
  # jupyter stacks options
  # -- see https://jupyter-docker-stacks.readthedocs.io/en/latest/using/common.html
  #    GRANT_SUDO, allow use of sudo e.g. for apt
  # Makefile options
  # TESTS, EXTRAS, PIPREQ see Makefile:install
  docker run --network host \
             --name omegaml-test \
             --user $(id -u):$(id -g) --group-add users \
             -dt \
             $dockeropts \
             -e RUNTESTS=yes \
             -e GRANT_SUDO=yes \
             -e TESTS="$tests" \
             -e EXTRAS="dev,$extras" \
             -e PIPREQ="$pipreq" \
             -e PIPOPTS="$pipopts" \
             -v $sources_dir:$test_base \
             -w $test_base $image \
             bash
  # run commands, collect results, cleanup
  # -- some images require adding a user explicitly
  #    e.g. on circleci, the user does not exist yet causing downstream errors
  #    solution adopted from https://stackoverflow.com/questions/48527958/docker-error-getting-username-from-password-database
  #    due to https://jupyter-docker-stacks.readthedocs.io/en/latest/using/common.html#user-related-configurations
  #    this may issue a "UID NNN ist not unique" message, not a problem
  docker exec --user root omegaml-test bash -c "useradd -u $(id -u) -g users testuser; chmod 777 $test_base/.."
  # -- some images don't have make installed, e.g. https://github.com/jupyter/docker-stacks/issues/1625
  docker exec --user root omegaml-test bash -c "which make || apt update && apt -y install build-essential"
  docker exec omegaml-test bash -c 'make -e install test; echo $? > /tmp/test.status' 2>&1 | tee -a $test_logfn
  docker exec omegaml-test bash -c "cat /tmp/test.status" | xargs -I RC echo "$test_logdir==RC" >> $test_logrc
  docker exec omegaml-test bash -c "pip list --format freeze" | tee -a ${test_pipfn}
  tar -czf $test_logtar $test_logdir --remove-files
  if [[ ! -z $shell ]]; then
    docker exec -it omegaml-test bash
  fi
  docker kill omegaml-test
  echo "INFO runtests tests completed."
}

function runauto_csv() {
  # run tests from image specs in csv file
  # images to test against
  while IFS=';' read -r image tests extras pipreq pipopts dockeropts label; do
    runimage "$image" "$tests" "$extras" "$pipreq" "$pipopts" "$dockeropts" "$label"
    [[ ! -z $rmi ]] && docker rmi --force $image
  done < <(cat $test_images | grep -v "#")
}


function runauto() {
  # see https://github.com/rudimeier/bash_ini_parser
  read_ini $test_images
  if [[ ! -z $describe ]]; then
    echo $INI__ALL_SECTIONS
    exit 0
  fi
  [[ ! -z $specid ]] && INI__ALL_SECTIONS=$specid
  for section in $INI__ALL_SECTIONS; do
    declare -n v="INI__${section}__image";image="${v}"
    declare -n v="INI__${section}__tests";tests="${v}"
    declare -n v="INI__${section}__extras";extras="${v}"
    declare -n v="INI__${section}__pipreq";pipreq="${v}"
    declare -n v="INI__${section}__pipopts";pipopts="${v}"
    declare -n v="INI__${section}__dockeropts";dockeropts="${v}"
    declare -n v="INI__${section}__label";label="${v}"
    runimage "$image" "$tests" "$extras" "$pipreq" "$pipopts" "$dockeropts" "$label"
    [[ ! -z $rmi ]] && docker rmi --force $image
  done
}

function clean() {
  # start clean
  rm -rf $sources_dir/build
  rm -rf $sources_dir/dist
  rm -rf $test_logbase
  mkdir -p $test_logbase
}

function summary() {
  # print summary
  echo "All Tests Summary (==return code)"
  echo "================="
  cat $test_logrc
  echo "-----------------"
  # man grep: exit status is 0 if a line is selected, 1 if no lines were selected
  # -- if at least one line does not have ==0 => grep rc 0 => return rc 1
  rc=$([[ ! $(grep -v "==0" $test_logrc) ]])
  exit $rc
}

function main() {
  if [ ! -z $clean ]; then
    clean
  fi
  if [ ! -z $image ]; then
    runimage "$image" "$tests" "$extras" "$pipreq" "$pipopts" "$dockeropts" "$label"
    summary
  else
    clean
    runauto
    summary
  fi
}

main

