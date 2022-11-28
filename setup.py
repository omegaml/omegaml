import os
from setuptools import setup, find_packages

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()

dev_deps = [
    'django-nose==1.4.7',
    'mock==3.0.5',
    'behave==1.2.6',
    'selenium==3.141.0',
    'splinter[selenium3]',
    'ipdb==0.13.2',
    'gil',
    'sphinx-django-command',
    'bumpversion',
    'sphinx_rtd_theme',
]

jupyter_deps = [
    'jupyterhub-kubespawner==2.0.1', # required or only dev
    'jupyterhub==2.2.1',  # required or only dev?
    'jupyter-client>=7.0.6',
    'jupyterhub-simplespawner==0.1',
    'jupyterlab',
]

all_deps = [] + jupyter_deps

from omegaee._version import version

setup(
    name='omegamlee',
    version=version,
    packages=find_packages(exclude=['app', 'config']),
    include_package_data=True,
    license='commercial',  # example license
    description='Enterprise DataOps, MLOps platform for humans',
    long_description=README,
    url='https://omegaml.io',
    author='Patrick Senti',
    author_email='patrick.senti@omegaml.io',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: Commercial',  # example license
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        # replace these appropriately if you are using Python 3
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    install_requires=[
        'Django~=3.2',
        'honcho>=1.0.1',
        'pyrabbit2==1.0.7',
        'cachetools',
        'dj_database_url',
        'gunicorn>=19.7.1',
        'omegaml>=0.13.4',
        'python-json-logger>=2.0.4'

    ],
    dependency_links=[
    ],
    extras_require={
        'dev': dev_deps,
        'all': all_deps,
    },

)
