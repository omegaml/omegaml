#!/usr/bin/env bash
export PORT=8000
export JUPYTER_PARAM="--config ./omegaml/notebook/jupyter/jupyter_notebook_config.py"
export JUPYTER_PASSWORD=sha1:24fa20fec60f:c7cd7e46afa507d484c59abeadbefa05022583b8
honcho start restapi notebook worker
