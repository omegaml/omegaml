import glob

import os
from setuptools import setup, find_namespace_packages

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()
version = open(os.path.join(os.path.dirname(__file__), 'omegaml', 'VERSION')).readlines()[0]

# extras
tables = ['tables>=3.7']
graph_deps = ['matplotlib>=3.5', 'seaborn>=0.11']
dashserve_deps = ['dash>=2.9', 'plotly']
snowflake_deps = ['snowflake-sqlalchemy']
jupyter_deps = ['jupyterlab', 'jupyterhub', 'notebook', 'nbclassic']
mlflow_deps = ['mlflow-skinny>=1.2']
tf_deps = ['tensorflow>2,<2.16']  # due to 2.16 dropping support for tf-estimators
dev_deps = ['pytest', 'twine', 'flake8', 'mock', 'behave', 'splinter[selenium]', 'ipdb', 'bumpversion', 'pip-tools']
# required to avoid backtracking (falling below some versions)
backtracking_deps = [
    'json5>0.9',
    'google_auth_oauthlib>=1',
    'filelock>=3.0.0',
    'gitdb>4.0',
    'debugpy>=1.7',
    'cryptography>=41.0',
    'Babel>2.13',
    'attrs>=21.4.0',
    'asttokens>=2.4',
    'anyio>=3.7',
    'tomli>=2.0.0',
]
# required based on github dependency advisories
sec_deps = [
    'dnspython>=2.6.1',  # https://github.com/advisories/GHSA-3rq5-2g8h-59hc
    'idna>=3.7',  # https://github.com/advisories/GHSA-jjg7-2v4v-x38h
    'pymongo>=4.10',  # https://github.com/advisories/GHSA-cr6f-gf5w-vhrc
]
test_deps = (tables + graph_deps + dashserve_deps + jupyter_deps + mlflow_deps + tf_deps + backtracking_deps)
client_deps = (tables + dashserve_deps)
install_deps = [
    'celery>5,<6.0',
    'joblib>=0.9.4',
    'jupyter-client>=4.1.1',
    'ipython>=8.0',  # required for cli shell
    'mongoengine>=0.29',
    'pandas>=2.0.0,<2.2',  # due to https://github.com/pandas-dev/pandas/issues/57049
    'numpy>=1.16.4',
    'scipy>=0.17.0',
    'scikit-learn>=1.2',
    'PyYAML>=3.12',
    'flask-restx>=1.1.0',
    'Flask>3.0',  # due to https://github.com/python-restx/flask-restx/issues/566
    'Flask-Session',
    'croniter>=0.3.30',
    'nbformat>=4.0.1',
    'nbconvert>=6.4.0',
    'dill>0.3.6',
    'callable-pip>=1.0.0',
    'appdirs>=1.4.3',
    'cron-descriptor>=1.2.31',
    'docopt>=0.6.2',
    'requests>=2.20.0',
    'tqdm>=4.32.2',
    'yaspin',
    'honcho>=1.0.1',  # not strictly required, but used in docker compose
    'tabulate>=0.8.2',  # required in cli
    'smart_open',  # required in cli
    'imageio>=2.3.0',  # require to store images
    'psutil>=5.8',  # required for profiling tracker
    'cachetools>=5.0.0',  # required for session caching
    'apispec>=5.2.2',  # required for openapi generation
    'marshmallow>=3.17.0',  # required for openapi generation
    'sqlalchemy<2',  # currently no support for sqlalchemy 2
    'minibatch[omegaml]',  # required for streaming
    'validators',  # required for sec validations
]
setup(
    name='omegaml',
    version=version,
    packages=find_namespace_packages(),
    include_package_data=True,
    data_files=[
        ('omegaml/docs', glob.glob('./docs/source/nb/*.ipynb')),
        ('omegaml/runtimes/rsystem', glob.glob('./runtimes/rsystem/*.R')),
    ],
    scripts=glob.glob('./scripts/runtime/*'),
    license='Apache 2.0 + "No Sell, Consulting Yes" License Condition',
    description='An open source DataOps, MLOps platform for humans',
    long_description=README,
    long_description_content_type='text/x-rst',
    url='https://omegaml.io/',
    project_urls={
        "Documentation": "https://omegaml.github.io/omegaml/",
        "Issues": "https://github.com/omegaml/omegaml/issues",
        "Source": "https://github.com/omegaml/omegaml",
    },
    author='Patrick Senti',
    author_email='patrick.senti@omegaml.io',
    classifiers=[
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: Implementation :: CPython',
        'Development Status :: 4 - Beta',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Topic :: Software Development',
        'Operating System :: POSIX :: Linux',
        'License :: OSI Approved :: Apache Software License',
    ],
    install_requires=install_deps + sec_deps,
    extras_require={
        'all': test_deps,
        'client': client_deps,
        'dev': dev_deps,
    },
    entry_points={
        'console_scripts': ['om=omegaml.client.cli:climain'],
    }
)
