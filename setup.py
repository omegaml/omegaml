import glob

import os
import sys
from setuptools import setup, find_packages

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()
version = open(os.path.join(os.path.dirname(__file__), 'omegaml', 'VERSION')).read()

# extras
hdf_deps = ['tables>=3.2.2']
graph_deps = ['matplotlib>=3.1.0', 'seaborn>=0.9.0', 'imageio>=2.6.1', 'plotext>=1.0.11']
dashserve_deps = ['dashserve']
sql_deps = ['sqlalchemy', 'ipython-sql']
snowflake_deps = ['snowflake-sqlalchemy==1.2.3']
iotools_deps = ['smart_open', 'boto>=2.49.0']
streaming_deps = ['minibatch[all]']
jupyter_deps = ['jupyterlab', 'jupyterhub==1.0.0']  # jupyterhub-0.11 has breaking changes
dev_deps = ['nose', 'twine', 'flake8', 'mock', 'behave', 'splinter', 'ipdb', 'bumpversion']

# -- tensorflow specifics
tf_version = os.environ.get('TF_VERSION') or '2.3.1'
tf_match = os.environ.get('TF_VERSION_MATCH', '==')
if tf_version.startswith('1.15'):
    assert sys.version_info <= (3, 7), "TF < 2.x requires Python <= 3.7"
    tf_deps = ['tensorflow=={}'.format(tf_version)]
    tf_deps = tf_deps + ['tensorflow-gpu==1.15.0', 'h5py==2.10.0']
    keras_deps = ['keras==2.2.4']
elif (3, 8) <= sys.version_info < (3, 9) :
    major, minor, *_ = (int(v) for v in tf_version.split('.'))
    assert (major, minor) >= (2, 2), "Python version 3.8 only supported by TF >= 2.2"
    tf_deps = ['tensorflow{}{}'.format(tf_match, tf_version)]
    keras_deps = ['keras>=2.4.3']
elif sys.version_info >= (3, 9):
    major, minor, *_ = (int(v) for v in tf_version.split('.'))
    assert (major, minor) <= (2, 4), "Python version 3.9 only supported by TF < 2.4"
    assert (major, minor) >= (2, 2), "Python version 3.9 only supported by TF >= 2.2"
    tf_deps = ['tensorflow{}{}'.format(tf_match, tf_version)]
    keras_deps = ['keras>=2.4.3']
else:
    tf_deps = ['tensorflow{}{}'.format(tf_match, tf_version)]
    keras_deps = ['keras>=2.4.3']

# all deps
all_deps = (hdf_deps + tf_deps + keras_deps + graph_deps + dashserve_deps
            + sql_deps + iotools_deps + streaming_deps + jupyter_deps + snowflake_deps)
all_client_deps = (hdf_deps + dashserve_deps + sql_deps + iotools_deps + streaming_deps)

setup(
    name='omegaml',
    version=version,
    packages=find_packages(),
    include_package_data=True,
    data_files=[
        ('omegaml/docs/', glob.glob('./docs/source/nb/*.ipynb')),
    ],
    scripts=glob.glob('./scripts/runtime/*'),
    license='Apache 2.0',
    description='An open source DataOps, MLOps platform for humans',
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
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Development Status :: 4 - Beta',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Topic :: Software Development',
        'Operating System :: POSIX :: Linux',
        'License :: OSI Approved :: Apache Software License',
    ],
    install_requires=[
        'celery==4.2.1',
        'joblib>=0.9.4',
        'jupyter-client>=4.1.1',
        'pymongo>=3.2.2',
        'mongoengine>=0.18.2,<0.19',
        'pandas>=0.17.1,<1.1',  # 1.1 fails on storing multi-indexes
        'numpy>=1.16.4',
        'scipy>=0.17.0',
        'scikit-learn>=0.21',
        'PyYAML>=5.1',
        'flask-restplus>=0.12.1',
        'werkzeug<1.0.0',  # https://github.com/noirbizarre/flask-restplus/issues/777#issuecomment-584365577
        'six>=1.11.0',
        'croniter>=0.3.30',
        'nbformat>=4.0.1',
        'nbconvert>=5.4.1',
        'dill>=0.3.2',
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
        'honcho>=1.0.1',  # not strictly required, but used in docker compose
        'tabulate>=0.8.2',  # required in cli
    ],
    extras_require={
        'graph': graph_deps,
        'hdf': hdf_deps,
        'tensorflow': tf_deps,
        'keras': keras_deps,
        'dashserve': dashserve_deps,
        'sql': sql_deps,
        'snowflake': snowflake_deps,
        'iotools': iotools_deps,
        'streaming': streaming_deps,
        'all': all_deps,
        'all-client': all_client_deps,
        'dev': dev_deps,
    },
    entry_points={
        'console_scripts': ['om=omegaml.client.cli:climain'],
    }
)
