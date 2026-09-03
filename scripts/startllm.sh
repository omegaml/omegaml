#!/bin/env bash
## startllm.sh
##
## How it works
##
## # store the model in omegaml
## omegaml: om.models.put('/path/to/model', 'mymodel')
##
## # start the vllm server
## gpu container: ./startllm.sh mymodel
##
## This starts the appropriate model backend using ramalama
##
# TODO what if model consists of multiple gguf files?
MODELNAME=$1
MODELSPATH=/tmp/models
MODELFILE=$MODELSPATH/$MODELNAME.gguf

SERVER_BINARY_PATH=/home/patrick/projects/ramalama/llama-b8746
export PATH=$SERVER_BINARY_PATH:$PATH

function getmodel() {
  echo "INFO Retrieving model $MODELNAME to $MODELFILE"
  mkdir -p $MODELSPATH
  om models get "$MODELNAME" "$MODELFILE"
}

function servemodel() {
  echo "INFO Starting server for $MODELNAME from $MODELFILE"
  ramalama --nocontainer serve file://$MODELFILE
}

getmodel
servemodel
