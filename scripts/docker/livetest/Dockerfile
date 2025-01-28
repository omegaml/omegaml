ARG pyver=3.9
FROM jupyter/datascience-notebook:python-${pyver}
# chrome debug port https://developers.google.com/web/updates/2017/04/headless-chrome#frontend
EXPOSE 9222/tcp
ARG  pypi="https://pypi.org/simple"
ENV  pypi=$pypi
USER root
WORKDIR /app
COPY ./packages /var/packages
RUN  pip install --upgrade pip -q
RUN  pip install $(find /var/packages -type f -name "*.whl") -i $pypi --extra-index-url https://pypi.org/simple --progress-bar off --pre omegaml[dev]
RUN  ln -fs $(find / -type d -wholename '*/omegaml/tests/features') /app/features && \
     ln -fs $(find /  -name omegaml-tutorial.ipynb 2>/dev/null | head -n1 | xargs dirname) /app/docs
#ensure PYTHONUSERBASE is created
USER jovyan
RUN pip install --ignore-installed --user -U six
RUN jupyter lab build
