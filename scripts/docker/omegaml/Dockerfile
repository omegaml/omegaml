FROM jupyter/datascience-notebook:python-3.9
ARG  pypi="https://pypi.org/simple"
ENV  pypi=$pypi
USER root
COPY . /app
RUN pip install /app/packages/*whl -i $pypi -U --upgrade-strategy eager --progress-bar off omegaml[all]
RUN /app/scripts/setupnb.sh
#ensure PYTHONUSERBASE is created
USER jovyan
RUN pip install --user -U six


