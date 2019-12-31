FROM omegaml/omegaml-base

ADD . /app
RUN cd /app && \
    ls -1 *whl > /app/requirements.whl && \
    sed -i -r 's/^(landing.*)/\1\[all\]/g' /app/requirements.whl && \
    pip install --no-cache-dir -r /app/requirements.whl && \
    echo rm *whl &&  \
    /app/scripts/omegajobs.sh --installonly
RUN ln -fs /opt/conda/lib/python3.6/site-packages/app /app/app && \
    ln -fs /opt/conda/lib/python3.6/site-packages/config /app/config

    