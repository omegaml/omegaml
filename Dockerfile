FROM conda/miniconda3

ADD . /app
RUN apt-get update -y && \
    apt-get install -y python-dev build-essential
RUN conda install -y conda=4.3 && \
    conda update -y python
RUN conda install -y --file /app/conda-requirements.txt && \
    conda clean --all
RUN pip install --no-cache-dir -q -r /app/requirements.txt
RUN mkdir -p ~/.jupyter && \
    cp /app/omegaml/notebook/jupyter/*py ~/.jupyter && \
    cd /app && pip install .
CMD ["jupyter", '--config-dir', '/app/.jupyter']