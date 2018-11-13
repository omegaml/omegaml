FROM continuumio/miniconda3

ADD . /app
RUN apt-get update -y && \
    apt-get install -y --fix-missing mysql-client && \
    apt-get install -y default-libmysqlclient-dev python-dev build-essential  && \
    apt-get clean
RUN conda install -y conda=4.3 && \
    conda update -y python 
RUN conda install -y --file /app/conda-requirements.txt && \
    conda clean --all
RUN pip install --no-cache-dir -q -r /app/requirements.txt
RUN cd /app && \
    ls -1 *whl > /app/requirements.whl && \ 
    pip install --no-cache-dir -q -r /app/requirements.whl && \
    rm *whl
RUN ln -fs /opt/conda/lib/python3.6/site-packages/app /app/app && \
    ln -fs /opt/conda/lib/python3.6/site-packages/config /app/config && \
    ln -fs /opt/conda/lib/python3.6/site-packages/omegajobs /app/omegajobs 

    