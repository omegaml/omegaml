FROM jupyter/base-notebook
# https://jupyter-docker-stacks.readthedocs.io/en/latest/using/common.html
ENV GRANT_SUDO=yes
# install additional software
# -- switching to root to avoid having to sudo on every command
USER root
RUN apt-get update -y && \
    apt-get install -y --fix-missing python3-dev default-libmysqlclient-dev build-essential  && \
    apt-get install -y procps htop curl && \
    apt-get clean
# add omegaml software, fix permissions according to above URL
# -- adding /app requires root permission, however /app must belong to $NB_USER
ADD . /app
RUN mkdir -p /app/pylib && \
    fix-permissions "/app" && \
    start.sh
# -- set the user back to original setting
USER $NB_USER
# -- run install according to
#    https://jupyter-docker-stacks.readthedocs.io/en/latest/using/recipes.html#using-mamba-install-or-pip-install-in-a-child-docker-image
RUN conda install -y --file /app/conda-requirements.txt && \
    conda clean --all
RUN cd /app && \
    ls -1 *whl > /app/requirements.whl && \
    sed -i -r 's/^(landing.*|omegaml.*|omegaee.*)/\1\[all\]/g' /app/requirements.whl && \
    pip install -U --no-cache-dir -r /app/requirements.whl && \
    rm *whl && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"
