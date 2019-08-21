#!/usr/bin/env bash
conda list > local-dev.lst
docker run -v $HOME/projects/omegaml-ce:/mnt/omegaml-ce -it omegaml/omegaml:latest  bash -c "conda list > /mnt/omegaml-ce/omegaml-latest.lst"
meld local-dev.lst omegaml-latest.lst