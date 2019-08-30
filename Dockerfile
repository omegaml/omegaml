FROM omegaml/omegaml-base

ADD . /app
RUN conda install -y --file /app/conda-requirements.txt && \
    conda clean --all
RUN pip install --no-cache-dir -q -r /app/requirements.txt
RUN mkdir -p ~/.jupyter && \
    cp /app/omegaml/notebook/jupyter/*py ~/.jupyter && \
    cd /app && pip install .[all]
CMD ["jupyter", '--config-dir', '/app/.jupyter']