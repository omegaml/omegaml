import os
from setuptools import setup, find_packages

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()

dev_deps = [
    'django-nose==1.4.5',
    'mock==3.0.5',
    'behave==1.2.6',
    'jupyterhub',
    'selenium==3.141.0',
    'splinter==0.11.0',
    'ipdb==0.13.2',
    'jupyterhub-simplespawner==0.1',
    'gil',
]

web_deps = [
   'Django>=1.8,<1.9',
   'honcho==1.0.1',
   'gunicorn==19.7.1',
   'pyrabbit2==1.0.7',
]

jupyter_deps = [
    'jupyterhub-kubespawner==0.12.0', # required or only dev
    'jupyterhub>1.0',  # required or only dev?
    'notebook==5.7.6',  # required or only dev?
    'jupyter-client>=4.1.1',
]

airbrake_deps = [
    'pybrake',
]

all_deps = web_deps + jupyter_deps + dev_deps + airbrake_deps

from omegaee._version import version

setup(
    name='omegamlee',
    version=version,
    packages=find_packages(),
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
        'omegaml>=0.13.4',
        'croniter>=0.3.30',
        'appdirs==1.4.3',
        'cron-descriptor==1.2.24',
        'cachetools',
        'celery>4,<=4.2.1',
        'dj_database_url',
        'six',
    ],
    dependency_links=[
    ],
    extras_require={
        'dev': dev_deps,
        'all': all_deps,
    },

)
