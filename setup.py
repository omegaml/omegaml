import glob
import os
from setuptools import setup, find_packages

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()
version = open(os.path.join(os.path.dirname(__file__), 'omegaml', 'VERSION')).read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

# extras
hdf_deps = ['tables>=3.2.2']
tf_deps = ['tensorflow==1.15.0']
keras_deps = ['keras==2.2.4']
graph_deps = ['matplotlib==3.1.0', 'seaborn==0.9.0', 'imageio==2.6.1']

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
    long_description_content_type='text/x-rst',
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
        'mongoengine>=0.18.2,<0.19',
        'pandas>=0.17.1',
        'numpy>=1.16.4,<1.17',
        'scipy>=0.17.0',
        'scikit-learn>=0.20,<0.22',
        'PyYAML>=3.11',
        'flask-restplus>=0.12.1',
        'six>=1.11.0',
        'croniter>=0.3.30',
        'nbformat>=4.0.1',
        'nbconvert>=5.4.1',
        'dill>=0.2.9',
        'tee>=0.0.3',
        'callable-pip>=1.0.0',
        'appdirs>=1.4.3',
        'cron-descriptor>=1.2.24',
        'docopt>=0.6.2',
        'requests>=2.20.0',
        # fix tensorflow pulling wrong version of absl-py,
        # https://github.com/tensorflow/tensorflow/issues/26691#issuecomment-525519742
        'absl-py>=0.8.1',
        'tqdm>=4.32.2',
    ],
    extras_require={
        'graph': graph_deps,
        'hdf': hdf_deps,
        'tensorflow': tf_deps,
        'keras': keras_deps,
        'all': hdf_deps + tf_deps + keras_deps + graph_deps,
    },
    entry_points = {
        'console_scripts': ['om=omegaml.client.cli:climain'],
    }
)
