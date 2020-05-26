# build a jupyterhub launchable tensorflow image
# tensorflow (c) Google Inc, Apache License 2.0
# omegaml (c) one2seven GmbH, Apache License 2.0
# nvidia, cuda distributables (c) NVIDIA Inc, EULA
# see https://github.com/tensorflow/tensorflow
#     https://www.tensorflow.org/install/docker
#     https://docs.nvidia.com/cuda/eula/index.html
#     https://github.com/omegaml/omegaml
FROM tensorflow/tensorflow:2.2.0-gpu-jupyter
ARG  pypi="https://pypi.org/simple"
ENV  pypi=$pypi
ARG  NB_UID=1000
# system install
USER root
COPY . /app
RUN pip install --upgrade pip -q
RUN pip install -f /app/packages -i $pypi --extra-index-url https://pypi.org/simple/ --pre omegaml[all] jupyterhub jupyterlab
RUN /app/scripts/setupnb.sh
USER $NB_UID
