FROM omegaml/omegaml-base

ADD . /app
RUN cd /app && \
    ls -1 *whl > /app/requirements.whl && \
    sed -i -r 's/^(landing.*|minibatch.*|omegaml.*)/\1\[all\]/g' /app/requirements.whl && \
    pip install -U --no-cache-dir -r /app/requirements.whl && \
    rm *whl
RUN ln -fs /opt/conda/lib/python3.6/site-packages/app /app/app && \
    ln -fs /opt/conda/lib/python3.6/site-packages/config /app/config

