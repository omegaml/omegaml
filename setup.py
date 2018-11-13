import os
from setuptools import setup, find_packages

README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='omegaml',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    license='commercial',  # example license
    description='online machine learning environment for scikit-learn',
    long_description=README,
    url='http://www.shrebo.com/',
    author='Patrick Senti',
    author_email='patrick.senti@shrebo.ch',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: Commercial',  # example license
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        # replace these appropriately if you are using Python 3
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    install_requires=[
        'Django>=1.8,<1.9',
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
        'croniter>=0.3.12',
        'PyYAML>=3.11',
        'nbformat>=4.0.1',
    ],
    dependency_links=[
    ]
)
