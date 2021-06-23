FROM continuumio/miniconda3
ADD . /app
RUN apt-get update -y && \
    apt-get install -y --fix-missing python3-dev default-libmysqlclient-dev build-essential  && \
    apt-get install -y procps htop curl && \
    apt-get clean
RUN conda install -y conda=4.9.2 && \
    conda update -y python
RUN conda install -y --file /app/conda-requirements.txt && \
    conda clean --all
RUN cd /app && \
    ls -1 *whl > /app/requirements.whl && \
    sed -i -r 's/^(landing.*|minibatch.*|omegaml.*)/\1\[all\]/g' /app/requirements.whl && \
    pip install -U --no-cache-dir -r /app/requirements.whl -r /app/requirements.txt && \
    rm *whl
