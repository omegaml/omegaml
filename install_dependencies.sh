# conda buildpack dependency install
# from https://github.com/arose13/conda-buildpack/blob/e9a1f10f84dcc85d8eb8ac2d034817cbfafc77c6/bin/steps/conda_compile

if [ -f conda-requirements.txt ]; then
    puts-step "Installing dependencies using Conda"
    conda install --file conda-requirements.txt --yes | indent
fi

if [ -f requirements.txt ]; then
    puts-step "Installing dependencies using Pip"
    pip install -r requirements.txt  --exists-action=w | indent
fi

if [ -f pip-requirements.extra ]; then
    puts-step "Installing extra requirements using Pip"
    pip install -r pip-requirements.extra --exists-action=w | indent
fi