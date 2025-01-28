ARG pyver=3.10
FROM jupyter/datascience-notebook:python-${pyver}
ARG  pypi="https://pypi.org/simple"
ENV  pypi=$pypi
USER root
COPY . /app
RUN pip install /app/packages/*whl -i $pypi -U --progress-bar off omegaml[all]
RUN /app/scripts/setupnb.sh
RUN /app/scripts/setup-r.sh
#ensure PYTHONUSERBASE is created
USER jovyan
RUN pip install --ignore-installed --user -U six
RUN jupyter lab build


