FROM omegaml/omegaml-base

ADD . /app
RUN cd /app && \
    ls -1 *whl > /app/requirements.whl && \ 
    pip install --no-cache-dir -q -r /app/requirements.whl && \
    rm *whl &&  \
    /app/scripts/omegajobs.sh --installonly
RUN ln -fs /opt/conda/lib/python3.6/site-packages/app /app/app && \
    ln -fs /opt/conda/lib/python3.6/site-packages/config /app/config

    