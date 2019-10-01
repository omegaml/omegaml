import glob
import os
from setuptools import setup, find_packages
from omegaml._version import version

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

# extras
hdf_deps = ['tables>=3.2.2']
tf_deps = ['tensorflow==1.14.0']
keras_deps = ['keras==2.2.4']
graph_deps = ['matplotlib==3.1.0', 'seaborn==0.9.0']

setup(
    name='omegaml',
    version=version,
    packages=find_packages(),
    include_package_data=True,
    data_files=[
        ('omegaml/docs/', glob.glob('./docs/source/nb/*.ipynb'))
    ],
    license='Apache 2.0',
    description='the fastest way to deploy machine learning models',
    long_description=README,
    url='https://omegaml.io/',
    author='Patrick Senti',
    author_email='patrick.senti@omegaml.io',
    classifiers=[
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
    install_requires=[
        'celery==4.2.1',
        'joblib>=0.9.4',
        'jupyter-client>=4.1.1',
        'pymongo>=3.2.2',
        'mongoengine>=0.10.6',
        'pandas>=0.17.1',
        'numpy>=1.10.4',
        'scipy>=0.17.0',
        'scikit-learn>=0.20',
        'PyYAML>=3.11',
        'flask-restplus>=0.12.1',
        'six>=1.11.0',
        'croniter>=0.3.12',
        'nbformat>=4.0.1',
        'nbconvert>=5.4.1',
        'dill==0.2.9',
    ],
    extras_require={
        'graph': graph_deps,
        'hdf': hdf_deps,
        'tensorflow': tf_deps,
        'keras': keras_deps,
        'all': hdf_deps + tf_deps + keras_deps + graph_deps,
    },
)
