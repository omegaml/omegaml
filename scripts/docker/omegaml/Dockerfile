FROM omegaml/omegaml-base
ARG  pypi="https://pypi.org/simple"
ENV  pypi=$pypi
USER ROOT
# system install
USER root
COPY . /app
RUN pip install --upgrade pip -q
RUN pip install -f /app/packages -i $pypi --extra-index-url https://pypi.org/simple/ --pre -U omegaml[all] jupyterhub jupyterlab
RUN /app/scripts/setupnb.sh

CMD ["jupyter", '--config-dir', '/app/.jupyter']
