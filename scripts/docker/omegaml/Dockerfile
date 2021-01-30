FROM jupyter/scipy-notebook:703d8b2dcb88
ARG  pypi="https://pypi.org/simple"
ENV  pypi=$pypi
USER root
COPY . /app
RUN pip install --upgrade pip -q
RUN pip install -f /app/packages -i $pypi --extra-index-url https://pypi.org/simple/ --pre -U omegaml[all]
RUN /app/scripts/setupnb.sh
#ensure PYTHONUSERBASE is created
USER jovyan
RUN pip install --user -U six


