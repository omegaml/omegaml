FROM quay.io/jupyter/base-notebook:ubuntu-22.04
# based on https://jupyter-docker-stacks.readthedocs.io/en/latest/using/common.html
# Ubuntu-20.04 is LTS version, see https://endoflife.date/ubuntu
ENV GRANT_SUDO=yes
# disable humbug reporting
# -- BUGGER_OFF for https://bugout.dev
# -- DO_NOT_TRACK for tools compliant with https://consoledonottrack.com
ENV BUGGER_OFF=true
ENV DO_NOT_TRACK=1
# install additional software
# -- switching to root to avoid having to sudo on every command
USER root
RUN apt-get update -y && \
    apt-get install -y --fix-missing python3-dev default-libmysqlclient-dev build-essential  && \
    apt-get install -y procps htop curl git nano zip && \
    apt-get clean
# enable mssql server support
# adopted from landingpage/getsqlserver.sh
ENV ACCEPT_EULA=Y
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
RUN curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list -o /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    apt-get install -y msodbcsql18 msodbcsql17 unixodbc-dev && \
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
    pip install psycopg2-binary && \
    pip install pyodbc mssql-django && \
    rm *whl && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"
