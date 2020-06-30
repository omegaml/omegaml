FROM joyzoursky/python-chromedriver:3.7-selenium
# chrome debug port https://developers.google.com/web/updates/2017/04/headless-chrome#frontend
EXPOSE 9222/tcp
ARG  pypi="https://pypi.org/simple"
ENV  pypi=$pypi
WORKDIR /root
COPY ./packages /var/packages
RUN  pip install --upgrade pip -q
RUN  pip install --ignore-installed six -f /var/packages -i $pypi --extra-index-url https://pypi.org/simple/ --pre -U omegaml[all] && \
     pip install behave splinter ipdb

