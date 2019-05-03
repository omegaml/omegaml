FROM conda/miniconda3
ARG  pypi
ENV  pypi=$pypi
COPY ./packages /var/packages
RUN  pip install --upgrade pip -q
RUN  pip install --ignore-installed six -f /var/packages -i $pypi --extra-index-url https://pypi.org/simple/ omegaml && \
     pip install behave
