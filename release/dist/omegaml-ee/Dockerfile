FROM jupyter/base-notebook
# based on https://jupyter-docker-stacks.readthedocs.io/en/latest/using/common.html
ENV GRANT_SUDO=yes
# install additional software
# -- switching to root to avoid having to sudo on every command
USER root
RUN apt-get update -y && \
    apt-get install -y --fix-missing python3-dev default-libmysqlclient-dev build-essential  && \
    apt-get install -y procps htop curl git && \
    apt-get clean
# add omegaml software, fix permissions according to above URL
# -- adding /app requires root permission, however /app must belong to $NB_USER
# -- run install according to
#    https://jupyter-docker-stacks.readthedocs.io/en/latest/using/recipes.html#using-mamba-install-or-pip-install-in-a-child-docker-image
ADD . /app
RUN mkdir -p /app/pylib/user && \
    mkdir -p /app/pylib/base && \
    fix-permissions "/app" && \
    start.sh
# -- set the user back to original setting so $NB_USER is permissioned
USER $NB_USER
RUN conda install -y --file /app/conda-requirements.txt && \
    conda clean --all
RUN cd /app && \
    ls -1 *whl > /app/requirements.whl && \
    sed -i -r 's/^(landing.*|omegamlee.*)/\1\[all\]/g' /app/requirements.whl && \
    pip install -U --no-cache-dir -r /app/requirements.whl && \
    rm *whl && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"
