import os
from setuptools import setup, find_packages
from omegaml._version import version

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='omegaml',
    version=version,
    packages=find_packages(),
    include_package_data=True,
    license='http://www.apache.org/licenses/LICENSE-2.0',
    description='data science platform that scales from laptop to teams to enterprise. Batteries included.',
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
        'celery>=3.1.20,<3.1.24',
        'joblib>=0.9.4',
        'jupyter-client>=4.1.1',
        'pymongo>=3.2.2',
        'mongoengine>=0.10.6',
        'pandas>=0.17.1',
        'numpy>=1.10.4',
        'scipy>=0.17.0',
        'scikit-learn>=0.17.1',
        'tables>=3.2.2',
        'PyYAML>=3.11',
        'flask-restplus==0.12.1',
    ],
    dependency_links=[
    ]
)
